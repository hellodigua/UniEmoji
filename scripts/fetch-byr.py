#!/usr/bin/env python3
"""Download BYR's indexed emoji sets without converting the original GIFs.

Requires Python 3.10+, Pillow, and curl. Example:
    python3 scripts/fetch-byr.py
    python3 scripts/fetch-byr.py --offline

The forum's own UBB picker declares each range as [start, num), where num
is an exclusive stop, not an item count. We fetch only these indexed URLs.
Existing valid GIFs are reused only when they match any saved checksum;
failures never count as a missing/end index.
"""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import io
import json
from pathlib import Path
import re
import subprocess
import tempfile
import time
from urllib.parse import urljoin, urlparse

from PIL import Image, UnidentifiedImageError


ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / "docs/byr-sources.json"
BASE = "https://bbs.byr.cn"
GROUPS = ("em", "ema", "emb", "emc")


def timestamp(value: float | None = None) -> str:
    return datetime.fromtimestamp(value or time.time(), timezone.utc).isoformat()


def atomic_json(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".part")
    temporary.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    temporary.replace(path)


def fetch(url: str, interval: float, attempts: int = 3) -> tuple[bytes, dict]:
    """Use curl's OS trust store; retry transport/429/5xx, never treat as 404."""
    parsed = urlparse(url)
    if parsed.scheme != "https" or parsed.netloc != "bbs.byr.cn":
        raise ValueError(f"Unexpected source URL: {url}")
    last_error = ""
    for attempt in range(attempts):
        time.sleep(interval)
        with tempfile.TemporaryDirectory(prefix="uniemoji-byr-") as folder:
            body = Path(folder) / "body"
            result = subprocess.run(
                ["curl", "--silent", "--show-error", "--proto", "=https",
                 "--connect-timeout", "10", "--max-time", "35",
                 "--output", str(body), "--write-out", "%{http_code}\n%{content_type}",
                 url], capture_output=True, text=True,
            )
            parts = result.stdout.split("\n", 1)
            status = int(parts[0]) if parts and parts[0].isdigit() else 0
            content_type = parts[1] if len(parts) > 1 else ""
            if result.returncode == 0 and status == 200:
                return body.read_bytes(), {
                    "http_status": status, "content_type": content_type,
                    "fetched_at": timestamp(),
                }
            last_error = f"curl={result.returncode}, HTTP={status}, {result.stderr.strip()}"
            if result.returncode == 0 and status != 429 and not 500 <= status <= 599:
                break
        if attempt + 1 < attempts:
            time.sleep(2 ** attempt)
    raise RuntimeError(f"{url}: {last_error}")


def discover_index(interval: float, local_script: Path | None, script_url: str) -> dict:
    if local_script:
        script = local_script.read_bytes()
        fetched_at = timestamp(local_script.stat().st_mtime)
    else:
        page, _ = fetch(BASE + "/", interval)
        urls = re.findall(rb'<script[^>]+src=[\'\"]([^\'\"]+)', page)
        pack = next((u.decode() for u in urls if b"/js/pack_" in u), None)
        if not pack:
            raise RuntimeError("Official homepage has no pack script; cannot infer ranges")
        script_url = urljoin(BASE + "/", pack)
        script, response = fetch(script_url, interval)
        fetched_at = response["fetched_at"]
    content = script.decode("gb18030")
    config = re.search(r"ubb_em_img:\s*\[(.*?)\]", content)
    loop = re.search(r"for\(var i=start;i<num;i\+\+\)", content)
    if not config or not loop:
        raise RuntimeError("Cannot verify the official index's exclusive upper bound")
    items = re.findall(
        r"\{name:'([^']+)',path:'([^']+)',start:(\d+),num:(\d+)\}", config.group(1)
    )
    ranges = [
        {"group": group, "label": label, "start": int(start), "stop_exclusive": int(stop)}
        for label, group, start, stop in items if group in GROUPS
    ]
    if {item["group"] for item in ranges} != set(GROUPS):
        raise RuntimeError("Official configuration does not contain all four requested sets")
    if any(not 0 <= item["start"] < item["stop_exclusive"] <= 1000 for item in ranges):
        raise RuntimeError("Unexpected range size; inspect the official index before downloading")
    return {
        "url": script_url, "fetched_at": fetched_at,
        "sha256": hashlib.sha256(script).hexdigest(),
        "configuration": config.group(0), "iteration": loop.group(0),
        "boundary_confidence": "official_picker_index",
        "scope": "All entries advertised by the official UBB picker; unlisted server files are not enumerated.",
        "groups": ranges,
    }


def gif_metadata(data: bytes) -> dict:
    if data[:6] not in (b"GIF87a", b"GIF89a"):
        raise ValueError("Response does not have a GIF87a/GIF89a header")
    with Image.open(io.BytesIO(data)) as gif:
        if gif.format != "GIF":
            raise ValueError("Image decoder did not identify a GIF")
        width, height = gif.size
        loop = gif.info.get("loop")
        durations = []
        transparency = False
        for frame in range(gif.n_frames):
            gif.seek(frame)
            gif.load()  # Decode every frame so truncated/corrupt images are rejected.
            durations.append(gif.info.get("duration", 0))
            transparency = transparency or gif.convert("RGBA").getchannel("A").getextrema()[0] < 255
        return {
            "width": width, "height": height, "frames": len(durations),
            "animated": len(durations) > 1, "duration_ms": sum(durations),
            "frame_durations_ms": durations, "loop": loop,
            "has_transparency": transparency, "bytes": len(data),
            "sha256": hashlib.sha256(data).hexdigest(),
        }


def summarize(manifest: dict) -> None:
    records = manifest["images"]
    by_hash: dict[str, list[str]] = {}
    for record in records:
        by_hash.setdefault(record["sha256"], []).append(record["id"])
    manifest["duplicate_content"] = [ids for ids in by_hash.values() if len(ids) > 1]
    expected = sum(item["stop_exclusive"] - item["start"] for item in manifest["index"]["groups"])
    pending = len(manifest.get("pending_ids", []))
    manifest["summary"] = {
        "expected": expected, "downloaded": len(records),
        "animated": sum(record["animated"] for record in records),
        "static": sum(not record["animated"] for record in records),
        "failed": len(manifest["failures"]),
        "pending": pending,
        "validated": expected - pending - len(manifest["failures"]),
        "complete": len(records) == expected and not manifest["failures"] and not pending,
        "total_bytes": sum(record["bytes"] for record in records),
        "groups": {group: sum(record["group"] == group for record in records) for group in GROUPS},
    }
    manifest["updated_at"] = timestamp()
    atomic_json(MANIFEST, manifest)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--offline", action="store_true", help="Validate local GIFs using the saved index; never make requests")
    parser.add_argument("--interval", type=float, default=0.15, help="Minimum pause before each request (seconds)")
    parser.add_argument("--index-script", type=Path, help="Use an already downloaded official pack JS")
    parser.add_argument("--index-url", default=BASE + "/js/pack_f837b939bd.js", help="Provenance URL when supplying --index-script")
    args = parser.parse_args()
    if args.interval < 0.1:
        parser.error("--interval must be at least 0.1 seconds")
    previous = json.loads(MANIFEST.read_text(encoding="utf-8")) if MANIFEST.exists() else {}
    if args.offline:
        if not previous.get("index"):
            parser.error("--offline requires an existing manifest with an official index")
        index = previous["index"]
    else:
        index = discover_index(args.interval, args.index_script, args.index_url)
    old_records = {item["id"]: item for item in previous.get("images", [])}
    expected_ids = [
        f"byr_{group['group']}_{number:03d}"
        for group in index["groups"]
        for number in range(group["start"], group["stop_exclusive"])
    ]
    records = {identity: old_records[identity] for identity in expected_ids if identity in old_records}
    manifest = {
        "schema_version": 1, "source": "北邮人论坛 UBB 表情", "source_url": BASE,
        "collection_method": "Official picker ranges; serial requests with rate limiting, retries, validated cache, and byte-preserved GIFs.",
        # Keep unvisited records, including their original response provenance,
        # throughout a resumed validation. Pending IDs prevent a partial pass
        # from being mistaken for a complete, verified collection.
        "index": index, "images": list(records.values()), "failures": [],
        "pending_ids": expected_ids.copy(),
    }
    for group in index["groups"]:
        for number in range(group["start"], group["stop_exclusive"]):
            identity = f"byr_{group['group']}_{number:03d}"
            path = ROOT / "origins" / f"byr_{group['group']}" / f"{identity}.gif"
            url = f"{BASE}/img/ubb/{group['group']}/{number}.gif"
            try:
                response = {}
                metadata = None
                old = old_records.get(identity, {})
                if path.exists():
                    try:
                        metadata = gif_metadata(path.read_bytes())
                        if old.get("sha256") and old["sha256"] != metadata["sha256"]:
                            raise ValueError(f"Cached GIF checksum differs from the saved source: {identity}")
                    except (ValueError, OSError, EOFError, UnidentifiedImageError):
                        metadata = None
                        if args.offline:
                            raise
                if metadata is None:
                    if args.offline:
                        raise FileNotFoundError(f"Missing local GIF: {path.relative_to(ROOT)}")
                    data, response = fetch(url, args.interval)
                    metadata = gif_metadata(data)
                    path.parent.mkdir(parents=True, exist_ok=True)
                    temporary = path.with_suffix(".gif.part")
                    temporary.write_bytes(data)
                    temporary.replace(path)
                if not response and old.get("sha256") == metadata["sha256"]:
                    response = old.get("response", {})
                if not response:
                    response = {"fetched_at": timestamp(path.stat().st_mtime), "status": "validated_cached_file"}
                records[identity] = {
                    "id": identity, "group": group["group"], "group_name": group["label"],
                    "source_number": number, "source_url": url,
                    "path": path.relative_to(ROOT).as_posix(), "response": response, **metadata,
                }
                print(f"OK {identity}: {metadata['width']}x{metadata['height']}, {metadata['frames']} frames", flush=True)
            except (OSError, ValueError, RuntimeError, EOFError) as error:
                manifest["failures"].append({"id": identity, "source_url": url, "error": str(error)})
                print(f"FAILED {identity}: {error}", flush=True)
            manifest["pending_ids"].remove(identity)
            manifest["images"] = [records[identity] for identity in expected_ids if identity in records]
            summarize(manifest)  # Progress and unvisited provenance both survive interruption.
    print(json.dumps(manifest["summary"], ensure_ascii=False, indent=2))
    return 0 if manifest["summary"]["complete"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
