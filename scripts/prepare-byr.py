#!/usr/bin/env python3
"""Publish audited BYR originals and accepted image_gen masters. Requires Pillow.

This script never generates or upscales artwork. image_gen creates the masters;
this script only encodes small delivery copies and assembles metadata.
"""
import argparse
import hashlib
import json
import shutil
from pathlib import Path

from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
GROUPS = ("em", "ema", "emb", "emc")


def read_json(path):
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path, data):
    text = json.dumps(data, ensure_ascii=False, indent=2) + "\n"
    temp = path.with_suffix(path.suffix + ".tmp")
    temp.write_text(text, encoding="utf-8")
    temp.replace(path)


def sha256(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def validate_sources(sources):
    index_groups = sources.get("index", {}).get("groups", [])
    if len(index_groups) != len(GROUPS) or {g["group"] for g in index_groups} != set(GROUPS):
        raise ValueError("Collection index must contain each requested BYR group exactly once")
    expected = {
        f"byr_{group['group']}_{number:03d}"
        for group in index_groups
        for number in range(group["start"], group["stop_exclusive"])
    }
    records = sources.get("images", [])
    identities = [source["id"] for source in records]
    summary = sources.get("summary", {})
    if (sources.get("failures") or sources.get("pending_ids")
            or summary.get("complete") is not True
            or summary.get("pending", 0) != 0
            or summary.get("expected") != len(expected)
            or summary.get("downloaded") != len(expected)
            or len(identities) != len(expected) or set(identities) != expected):
        raise ValueError("Complete and validate every indexed original before publishing")


def validate_input(source, annotations, allow_pending):
    source_path = ROOT / source["path"]
    expected_source = ROOT / "origins" / ("byr_" + source["group"]) / (source["id"] + ".gif")
    if source_path != expected_source or sha256(source_path) != source["sha256"]:
        raise ValueError(f"Original path or hash mismatch: {source['id']}")
    with Image.open(source_path) as image:
        if (image.format != "GIF" or image.n_frames != source["frames"]
                or (image.n_frames > 1) != source["animated"]):
            raise ValueError(f"Original format or frame count mismatch: {source['id']}")
        for frame in range(image.n_frames):
            image.seek(frame)
            image.load()
    item = annotations.get(source["id"])
    if not item or not isinstance(item.get("name"), str) or not item["name"].strip():
        raise ValueError(f"Missing semantic annotation: {source['id']}")
    if any(not isinstance(item.get(key), list) or not item[key]
           or not all(isinstance(v, str) and v for v in item[key])
           for key in ("tags", "keywords")):
        raise ValueError(f"Invalid semantic annotation: {source['id']}")
    sidecar_path = ROOT / "enhanced" / ("byr_" + source["group"]) / (source["id"] + ".json")
    sidecar = read_json(sidecar_path) if sidecar_path.exists() else None
    accepted = sidecar and sidecar.get("review") == "accepted"
    if not accepted:
        if not allow_pending and not source["animated"]:
            raise ValueError(f"Static AI master not accepted: {source['id']}")
        return sidecar_path, sidecar, None
    if (sidecar.get("source_id") != source["id"]
            or sidecar.get("source_path") != source["path"]
            or sidecar.get("source_sha256", source["sha256"]) != source["sha256"]):
        raise ValueError(f"AI master belongs to another source: {source['id']}")
    expected_kind = "static-companion" if source["animated"] else "static-restoration"
    if sidecar.get("kind") != expected_kind or not isinstance(sidecar.get("master"), str):
        raise ValueError(f"Invalid accepted AI master metadata: {source['id']}")
    master = ROOT / sidecar["master"]
    enhanced = (ROOT / "enhanced" / ("byr_" + source["group"])).resolve()
    if not master.resolve().is_relative_to(enhanced):
        raise ValueError(f"AI master must remain in its enhanced group: {source['id']}")
    if sidecar.get("reviewed_sha256") != sha256(master):
        raise ValueError(f"AI master differs from its accepted review; review it again: {source['id']}")
    with Image.open(master) as image:
        if getattr(image, "n_frames", 1) != 1:
            raise ValueError(f"AI master must be a static image: {source['id']}")
        image.load()
    return sidecar_path, sidecar, master


def merge_groups(existing_text, new_groups):
    """Keep existing platforms byte-for-byte internally, including compact arrays."""
    decoder = json.JSONDecoder()
    cursor = existing_text.index("[") + 1
    chunks = []
    while True:
        while existing_text[cursor] in " \r\n\t,":
            cursor += 1
        if existing_text[cursor] == "]":
            break
        item, end = decoder.raw_decode(existing_text, cursor)
        if item["platform"] not in {"byr_" + g for g in GROUPS}:
            chunks.append(existing_text[cursor:end])
        cursor = end
    chunks.extend(json.dumps(group, ensure_ascii=False, indent=2).replace("\n", "\n  ") for group in new_groups)
    return "[\n  " + ",\n  ".join(chunks) + "\n]\n"


def publication(source, master, sidecar, size):
    source_path = ROOT / source["path"]
    directory = ROOT / "output" / ("byr_" + source["group"])
    directory.mkdir(parents=True, exist_ok=True)
    if master is None:
        target = directory / source_path.name
        temporary = target.with_suffix(target.suffix + ".tmp")
        shutil.copyfile(source_path, temporary)
        if sha256(temporary) != source["sha256"]:
            temporary.unlink()
            raise ValueError(f"Copied original hash mismatch: {source['id']}")
        temporary.replace(target)
        return target, "original-gif"
    suffix = "_hd" if source["animated"] else ""
    target = directory / (source["id"] + suffix + ".avif")
    with Image.open(master) as image:
        image = image.convert("RGBA")
        # No upscaling. Fit the entire composition without changing aspect ratio.
        image.thumbnail((size, size), Image.Resampling.LANCZOS)
        temporary = target.with_suffix(target.suffix + ".tmp")
        image.save(temporary, format="AVIF", quality=85)
        temporary.replace(target)
    return target, sidecar["kind"]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--size", type=int, default=160, help="Longest delivery edge (default: 160)")
    parser.add_argument("--allow-pending", action="store_true", help="Preview with originals while AI masters are under review")
    args = parser.parse_args()
    if not 60 <= args.size <= 512:
        parser.error("--size must be between 60 and 512")
    sources = read_json(ROOT / "docs/byr-sources.json")
    validate_sources(sources)
    annotations = {}
    for group in GROUPS:
        annotations.update(read_json(ROOT / f"docs/byr-annotations-{group}.json"))
    existing_text = (ROOT / "emoji.json").read_text(encoding="utf-8")
    groups = {group: [] for group in GROUPS}
    processing = []
    expected_files = set()

    # Decode every original and accepted master before replacing any delivery.
    validated = {
        source["id"]: validate_input(source, annotations, args.allow_pending)
        for source in sources["images"]
    }
    Image.init()
    if any(master for _, _, master in validated.values()) and "AVIF" not in Image.SAVE:
        raise ValueError("Pillow requires AVIF encoding support to publish AI masters")

    for source in sources["images"]:
        label = annotations[source["id"]]
        sidecar_path, sidecar, master = validated[source["id"]]
        # Every animated original remains the primary item; never silently freeze it.
        primary_master = master if not source["animated"] else None
        target, method = publication(source, primary_master, sidecar, args.size)
        url = target.relative_to(ROOT).as_posix()
        expected_files.add(target)
        groups[source["group"]].append({"url": url, **label})
        record = {"id": source["id"], "source": source["path"], "source_sha256": source["sha256"], "output": url, "method": method, "animated": source["animated"], "output_sha256": sha256(target)}
        if master:
            record.update({"master": master.relative_to(ROOT).as_posix(), "master_sha256": sha256(master), "generation_record": sidecar_path.relative_to(ROOT).as_posix()})
        if source["animated"] and master:
            companion, _ = publication(source, master, sidecar, args.size)
            expected_files.add(companion)
            companion_url = companion.relative_to(ROOT).as_posix()
            groups[source["group"]].append({"url": companion_url, "name": label["name"] + " · 高清静态", "tags": list(label["tags"]), "keywords": list(dict.fromkeys(label["keywords"] + ["高清", "AI修复", "静态"]))})
            record["static_companion"] = companion_url
            record["static_companion_sha256"] = sha256(companion)
        processing.append(record)

    # Preserve stale files until both new metadata files are replaced. A failed
    # metadata write must not leave the previous emoji.json with broken URLs.
    previous_path = ROOT / "docs/byr-processing.json"
    previous = read_json(previous_path) if previous_path.exists() else {}
    result = [{"platform": "byr_" + group, "emojis": groups[group]} for group in GROUPS]
    (ROOT / "emoji.json.tmp").write_text(merge_groups(existing_text, result), encoding="utf-8")
    (ROOT / "emoji.json.tmp").replace(ROOT / "emoji.json")
    summary = {"originals": len(processing), "animated_originals_preserved": sum(i["animated"] for i in processing), "static_ai_restorations": sum(i["method"] == "static-restoration" for i in processing), "static_originals_pending": sum(not i["animated"] and i["method"] == "original-gif" for i in processing), "animated_static_companions": sum("static_companion" in i for i in processing), "published_items": sum(map(len, groups.values()))}
    write_json(previous_path, {"schema_version": 1, "tool": "image_gen (built-in)", "delivery_long_edge": args.size, "delivery_quality": 85, "animation_policy": "Preserve original GIF bytes; AI static companions explicitly labeled. No AI animation restoration is claimed.", "summary": summary, "images": processing})
    # Remove only stale BYR deliveries known to the previous processing manifest.
    for record in previous.get("images", []):
        for key in ("output", "static_companion"):
            old = ROOT / record.get(key, "")
            allowed = any(old.parent == ROOT / "output" / ("byr_" + g) for g in GROUPS)
            if allowed and old.is_file() and old not in expected_files:
                old.unlink()
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
