#!/usr/bin/env python3
"""Create read-only visual review sheets and exact-hash snapshots (requires Pillow).

Examples:
  python3 scripts/byr-review-sheet.py byr_em_017 byr_em_018 byr_em_021
  python3 scripts/byr-review-sheet.py --pending --output /private/tmp/byr-pending.png

Every panel compares original frame 0, the AI master, and a 160 px AVIF delivery.
If a matching published delivery does not exist, encode a quality-85 preview in
memory. Originals, masters, sidecars, and review decisions are never modified.
"""

import argparse
from datetime import datetime, timezone
import hashlib
import io
import json
from pathlib import Path
import re

from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parents[1]


def read_json(path):
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


def digest(data):
    return hashlib.sha256(data).hexdigest()


def load_record(identity, published):
    group = identity.rsplit("_", 1)[0]
    source = ROOT / "origins" / group / (identity + ".gif")
    master = ROOT / "enhanced" / group / (identity + ".png")
    source_data, master_data = source.read_bytes(), master.read_bytes()
    with Image.open(io.BytesIO(source_data)) as image:
        image.seek(0)
        source_image = image.convert("RGBA")
    with Image.open(io.BytesIO(master_data)) as image:
        master_image = image.convert("RGBA")
    record = {
        "id": identity, "source": source.relative_to(ROOT).as_posix(),
        "source_sha256": digest(source_data), "source_frame": 0,
        "source_size": list(source_image.size),
        "master": master.relative_to(ROOT).as_posix(),
        "master_sha256": digest(master_data), "master_size": list(master_image.size),
    }
    publication = published.get(identity, {})
    delivery_path = publication.get("static_companion", publication.get("output"))
    delivery_data = None
    if publication.get("master_sha256") == record["master_sha256"] and delivery_path:
        candidate = ROOT / delivery_path
        if candidate.is_file() and candidate.suffix.lower() == ".avif":
            candidate_data = candidate.read_bytes()
            expected_hash = publication.get("static_companion_sha256", publication.get("output_sha256"))
            if digest(candidate_data) == expected_hash:
                with Image.open(io.BytesIO(candidate_data)) as image:
                    if max(image.size) == 160:
                        delivery_data = candidate_data
                        record.update({"delivery_kind": "published", "delivery": delivery_path})
    if delivery_data is None:
        preview = master_image.copy()
        preview.thumbnail((160, 160), Image.Resampling.LANCZOS)
        buffer = io.BytesIO()
        preview.save(buffer, format="AVIF", quality=85)
        delivery_data = buffer.getvalue()
        record.update({"delivery_kind": "preview-in-memory", "delivery": None})
    record["delivery_sha256"] = digest(delivery_data)
    with Image.open(io.BytesIO(delivery_data)) as image:
        delivery_image = image.convert("RGBA")
    record["delivery_size"] = list(delivery_image.size)
    return record, (source_image, master_image, delivery_image)


def draw_sheet(items, columns):
    width, height = 552, 236
    rows = (len(items) + columns - 1) // columns
    sheet = Image.new("RGB", (columns * width, rows * height), "#edf0f4")
    draw = ImageDraw.Draw(sheet)
    for position, (record, images) in enumerate(items):
        x, y = (position % columns) * width, (position // columns) * height
        draw.text((x + 8, y + 4), record["id"], fill="black")
        draw.text((x + 8, y + 19), "source " + record["source_sha256"][:12] + "  master " + record["master_sha256"][:12], fill="#34404d")
        titles = ("Original frame 0", "AI master", "160px AVIF " + record["delivery_kind"].split("-")[0])
        for index, (title, image) in enumerate(zip(titles, images)):
            left, top = x + index * 184 + 8, y + 53
            draw.text((left, y + 36), title, fill="black")
            for tx in range(0, 160, 10):
                for ty in range(0, 160, 10):
                    color = "#ffffff" if (tx + ty) % 20 == 0 else "#dde2e9"
                    draw.rectangle((left + tx, top + ty, left + tx + 9, top + ty + 9), fill=color)
            preview = image.copy()
            scale = min(160 / preview.width, 160 / preview.height)
            if index != 0:
                scale = min(1, scale)
            size = (max(1, round(preview.width * scale)), max(1, round(preview.height * scale)))
            preview = preview.resize(size, Image.Resampling.NEAREST if index == 0 else Image.Resampling.LANCZOS)
            sheet.paste(preview, (left + (160 - preview.width) // 2, top + (160 - preview.height) // 2), preview)
        draw.line((x, y + height - 1, x + width, y + height - 1), fill="#adb7c4")
    return sheet


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("ids", nargs="*")
    parser.add_argument("--pending", action="store_true", help="Select masters without a decision for the current source/master hashes")
    parser.add_argument("--output", type=Path, default=Path("/private/tmp/uniemoji-byr-review.png"))
    parser.add_argument("--columns", type=int, default=2)
    parser.add_argument("--per-page", type=int, default=12)
    args = parser.parse_args()
    if bool(args.ids) == args.pending:
        parser.error("Supply either one or more IDs, or --pending")
    if not 1 <= args.columns <= 4 or not 1 <= args.per_page <= 24:
        parser.error("--columns must be 1..4 and --per-page must be 1..24")
    if args.output.suffix.lower() != ".png":
        parser.error("--output must end in .png")
    # A review helper must not overwrite the collection or its delivery assets.
    for directory in ("origins", "enhanced", "output"):
        if args.output.resolve().is_relative_to(ROOT / directory):
            parser.error("Review output must be outside origins/, enhanced/, and output/")
    reviewed = read_json(ROOT / "docs/byr-ai-review.json").get("results", {})
    published = {item["id"]: item for item in read_json(ROOT / "docs/byr-processing.json").get("images", [])}
    identities = sorted(p.stem for p in (ROOT / "enhanced").glob("byr_*/*.png")) if args.pending else list(dict.fromkeys(args.ids))
    if any(not re.fullmatch(r"byr_em[abc]?_\d{3}", identity) for identity in identities):
        parser.error("IDs must look like byr_em_017 or byr_ema_001")
    items = []
    for identity in identities:
        record, images = load_record(identity, published)
        old = reviewed.get(identity, {})
        if args.pending and old.get("review") in ("accepted", "rejected") and all(
            old.get(field) == record[field] for field in ("source_sha256", "master_sha256")
        ):
            continue
        items.append((record, images))
    if not items:
        print("No pending masters; no output written.")
        return
    pages = (len(items) + args.per_page - 1) // args.per_page
    args.output.parent.mkdir(parents=True, exist_ok=True)
    for page in range(pages):
        output = args.output if pages == 1 else args.output.with_name(f"{args.output.stem}-{page + 1:02d}.png")
        batch = items[page * args.per_page:(page + 1) * args.per_page]
        draw_sheet(batch, min(args.columns, len(batch))).save(output)
        snapshot = {
            "schema_version": 1, "created_at": datetime.now(timezone.utc).isoformat(),
            "contact_sheet": str(output.resolve()), "items": [record for record, _ in batch],
        }
        output.with_suffix(".json").write_text(json.dumps(snapshot, indent=2) + "\n", encoding="utf-8")
        print(f"{output.resolve()} ({len(batch)} items; hashes in {output.with_suffix('.json').resolve()})")


if __name__ == "__main__":
    main()
