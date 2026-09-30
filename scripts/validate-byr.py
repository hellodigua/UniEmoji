#!/usr/bin/env python3
"""Validate BYR originals, accepted AI deliveries, and optional flat dist offline.

Requires Python 3.10+ and Pillow with AVIF support. This command is read-only:
    python3 scripts/validate-byr.py
    python3 scripts/validate-byr.py --dist
"""
import argparse
import hashlib
import json
from pathlib import Path, PurePosixPath

from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
GROUPS = ("em", "ema", "emb", "emc")
IMAGE_EXTENSIONS = {".avif", ".gif", ".webp", ".png", ".jpg", ".jpeg"}


def require(condition, message):
    if not condition:
        raise ValueError(message)


def read_json(path):
    return json.loads(path.read_text(encoding="utf-8"))


def sha256(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def local_file(root, relative, prefix=None):
    require(isinstance(relative, str) and relative, f"Invalid resource path: {relative!r}")
    pure = PurePosixPath(relative)
    require(not pure.is_absolute() and ".." not in pure.parts and "\\" not in relative,
            f"Resource must use a local relative path: {relative}")
    if prefix:
        require(relative.startswith(prefix), f"Unexpected resource directory: {relative}")
    path = root / relative
    require(path.is_file() and path.resolve().is_relative_to(root.resolve()),
            f"Missing or external resource: {relative}")
    return path


def gif_metadata(path):
    with Image.open(path) as image:
        require(image.format == "GIF", f"Expected GIF: {path}")
        width, height = image.size
        loop = image.info.get("loop")
        durations = []
        transparency = False
        for frame in range(image.n_frames):
            image.seek(frame)
            image.load()
            durations.append(image.info.get("duration", 0))
            transparency = transparency or image.convert("RGBA").getchannel("A").getextrema()[0] < 255
    return {
        "width": width, "height": height, "frames": len(durations),
        "animated": len(durations) > 1, "duration_ms": sum(durations),
        "frame_durations_ms": durations, "loop": loop,
        "has_transparency": transparency, "bytes": path.stat().st_size,
        "sha256": sha256(path),
    }


def static_image(path, expected_format=None):
    with Image.open(path) as image:
        require(getattr(image, "n_frames", 1) == 1, f"Expected a static image: {path}")
        if expected_format:
            require(image.format == expected_format, f"Expected {expected_format}: {path}")
        image.load()
        return image.size


def validate(root=ROOT, check_dist=False, expected_originals=199):
    root = Path(root)
    sources = read_json(root / "docs/byr-sources.json")
    summary = sources["summary"]
    require(summary.get("complete") is True and not sources.get("failures")
            and not sources.get("pending_ids") and summary.get("pending", 0) == 0,
            "Source collection is incomplete or has unresolved failures")
    index = sources["index"]["groups"]
    require(len(index) == 4 and {g["group"] for g in index} == set(GROUPS),
            "Expected all four official BYR groups exactly once")
    expected_ids = {
        f"byr_{group['group']}_{number:03d}"
        for group in index for number in range(group["start"], group["stop_exclusive"])
    }
    records = sources["images"]
    require(len(expected_ids) == expected_originals and len(records) == expected_originals
            and {s["id"] for s in records} == expected_ids,
            f"Expected exactly {expected_originals} unique indexed originals")
    require(summary.get("expected") == expected_originals and summary.get("downloaded") == expected_originals,
            "Source summary count does not match the collection")
    by_id = {source["id"]: source for source in records}
    for source in records:
        relative = f"origins/byr_{source['group']}/{source['id']}.gif"
        require(source["path"] == relative, f"Unexpected original path: {source['id']}")
        actual = gif_metadata(local_file(root, relative, "origins/"))
        for key, value in actual.items():
            require(source.get(key) == value, f"Original {key} mismatch: {source['id']}")

    public = read_json(root / "emoji.json")
    platforms, urls, filenames, byr_urls = set(), set(), set(), set()
    for platform in public:
        name = platform["platform"]
        require(name not in platforms, f"Duplicate platform: {name}")
        platforms.add(name)
        for emoji in platform["emojis"]:
            path = local_file(root, emoji["url"], "output/")
            require(emoji["url"] not in urls, f"Duplicate published URL: {emoji['url']}")
            require(path.name.lower() not in filenames, f"Duplicate published filename: {path.name}")
            urls.add(emoji["url"])
            filenames.add(path.name.lower())
            if name in {"byr_" + g for g in GROUPS}:
                byr_urls.add(emoji["url"])
                require(emoji["url"].startswith(f"output/{name}/"), f"Wrong BYR group for {emoji['url']}")
    require({"byr_" + g for g in GROUPS} <= platforms, "Published data is missing a BYR group")

    processing = read_json(root / "docs/byr-processing.json")
    outputs = processing["images"]
    require(len(outputs) == expected_originals and {item["id"] for item in outputs} == expected_ids,
            "Processing records must cover every original exactly once")
    published_outputs = set()
    restorations = companions = animated = 0
    for item in outputs:
        source = by_id[item["id"]]
        require(item["source"] == source["path"] and item["source_sha256"] == source["sha256"],
                f"Processing source mismatch: {source['id']}")
        require(item["animated"] == source["animated"], f"Animation classification mismatch: {source['id']}")
        target = local_file(root, item["output"], f"output/byr_{source['group']}/")
        require(sha256(target) == item["output_sha256"], f"Published hash mismatch: {item['output']}")
        published_outputs.add(item["output"])
        if source["animated"]:
            animated += 1
            require(item["method"] == "original-gif" and sha256(target) == source["sha256"],
                    f"Animated original was changed: {source['id']}")
        else:
            restorations += 1
            require(item["method"] == "static-restoration", f"Static AI restoration still pending: {source['id']}")
        if not source["animated"] or "static_companion" in item:
            sidecar_relative = f"enhanced/byr_{source['group']}/{source['id']}.json"
            require(item.get("generation_record") == sidecar_relative, f"Generation record missing: {source['id']}")
            sidecar = read_json(local_file(root, sidecar_relative, "enhanced/"))
            require(sidecar.get("review") == "accepted", f"AI master not accepted: {source['id']}")
            require(sidecar.get("source_id") == source["id"] and sidecar.get("source_path") == source["path"]
                    and sidecar.get("source_sha256", source["sha256"]) == source["sha256"],
                    f"AI sidecar source mismatch: {source['id']}")
            kind = "static-companion" if source["animated"] else "static-restoration"
            require(sidecar.get("kind") == kind, f"AI sidecar kind mismatch: {source['id']}")
            require(sidecar.get("master") == item.get("master"), f"AI master path mismatch: {source['id']}")
            master = local_file(root, item["master"], f"enhanced/byr_{source['group']}/")
            master_hash = sha256(master)
            require(sidecar.get("reviewed_sha256") == master_hash,
                    f"AI master differs from its accepted review; review it again: {source['id']}")
            require(master_hash == item["master_sha256"], f"AI master hash mismatch: {source['id']}")
            master_size = static_image(master)
            release = target
            if source["animated"]:
                companions += 1
                release = local_file(root, item["static_companion"], f"output/byr_{source['group']}/")
                require(sha256(release) == item["static_companion_sha256"], f"Companion hash mismatch: {source['id']}")
                published_outputs.add(item["static_companion"])
            release_size = static_image(release, "AVIF")
            require(max(release_size) <= processing["delivery_long_edge"]
                    and all(size <= original for size, original in zip(release_size, master_size)),
                    f"Unexpected delivery size: {release}")
    require(published_outputs == byr_urls, "Published BYR URLs differ from the processing manifest")
    expected_summary = {
        "originals": expected_originals, "animated_originals_preserved": animated,
        "static_ai_restorations": restorations, "static_originals_pending": 0,
        "animated_static_companions": companions, "published_items": len(byr_urls),
    }
    require(processing["summary"] == expected_summary, "Processing summary differs from verified files")

    dist_images = None
    if check_dist:
        assets = {}
        for path in sorted((root / "output").rglob("*")):
            require(not path.is_symlink(), f"Output contains a symbolic link: {path}")
            if path.is_file() and path.suffix.lower() in IMAGE_EXTENSIONS:
                require(path.name.lower() not in {name.lower() for name in assets},
                        f"Build filename collision: {path.name}")
                assets[path.name] = path
        dist_images = len(assets)
        assets.update({name: root / name for name in ("LICENSE", "THIRD_PARTY_NOTICES.md")})
        dist = root / "dist"
        require(dist.is_dir() and not dist.is_symlink(), "dist is missing or is a symbolic link")
        require({p.name for p in dist.iterdir()} == set(assets), "dist has missing or stale files; rebuild it")
        for name, original in assets.items():
            packaged = dist / name
            require(packaged.is_file() and not packaged.is_symlink()
                    and sha256(packaged) == sha256(original), f"dist content differs from source: {name}")
    return {**expected_summary, "all_published_items": len(urls), "dist_images": dist_images}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dist", action="store_true", help="Also verify the current flat build byte for byte")
    args = parser.parse_args()
    try:
        print(json.dumps(validate(check_dist=args.dist), ensure_ascii=False, indent=2))
    except (OSError, ValueError, KeyError, TypeError) as error:
        parser.exit(1, f"BYR validation failed: {error}\n")


if __name__ == "__main__":
    main()
