"""Build scripts/samples_manifest.json from eval/dataset.yaml using the Wikimedia Commons API.

Reads metadata only: which files to use, their licenses, authors, download URLs and sizes.
Media is downloaded separately by download_samples.py, which also records sha256 checksums.

    python scripts/build_manifest.py            # writes the manifest, prints a summary
"""

import hashlib
import json
import re
import sys
import time
from collections import Counter
from datetime import date
from pathlib import Path

import yaml

sys.path.insert(0, str(Path(__file__).parent))
import commons  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
DATASET = ROOT / "eval" / "dataset.yaml"
MANIFEST = ROOT / "scripts" / "samples_manifest.json"

ALLOWED_LICENSES = re.compile(r"^(CC0|CC BY(-SA)? [\d.]+|Public domain|PD)", re.IGNORECASE)
PHOTO_MIME = {"image/jpeg", "image/png"}
VIDEO_EXT = (".webm", ".ogv")
MIN_PHOTO_WIDTH = 800


def evenly(items: list, n: int) -> list:
    """n items spread across the list, so picks don't all come from one photographer's series."""
    if len(items) <= n:
        return list(items)
    step = len(items) / n
    return [items[int(i * step)] for i in range(n)]


def slug(title: str) -> str:
    """Readable ASCII name plus a short hash of the title.

    The hash keeps names unique: titles in other scripts (e.g. Cyrillic) reduce to an empty
    ASCII slug and would otherwise collide.
    """
    stem = Path(title.removeprefix("File:")).stem
    readable = re.sub(r"[^a-z0-9]+", "-", stem.lower()).strip("-")[:50]
    digest = hashlib.sha1(title.encode()).hexdigest()[:6]
    return f"{readable}-{digest}" if readable else digest


def license_ok(info: dict) -> bool:
    meta = info.get("extmetadata", {})
    return bool(ALLOWED_LICENSES.match(meta.get("LicenseShortName", {}).get("value", "")))


def describe(title: str, info: dict) -> dict:
    meta = info.get("extmetadata", {})
    return {
        "title": title,
        "page_url": info["descriptionurl"],
        "license": meta.get("LicenseShortName", {}).get("value", ""),
        "license_url": meta.get("LicenseUrl", {}).get("value", ""),
        "author": commons.plain_text(meta.get("Artist", {}).get("value"))[:200],
    }


def content_length(url: str) -> int | None:
    time.sleep(0.2)
    with commons.open_url(url, method="HEAD") as response:
        value = response.headers.get("Content-Length")
    return int(value) if value else None


def duration_of(info: dict) -> float | None:
    for item in info.get("metadata") or []:
        if item.get("name") in ("playtime_seconds", "length", "duration"):
            try:
                return float(item["value"])
            except (TypeError, ValueError):
                return None
    return None


def pick_photos(tag: str, category: str, need: int, width: int, used: set[str]) -> list[dict]:
    titles = [
        t for t in commons.category_files(category)
        if t.lower().endswith((".jpg", ".jpeg", ".png")) and t not in used
    ]  # fmt: skip
    # Look at 4x as many candidates as needed; some fail the license or size filter.
    infos = commons.file_info(evenly(titles, need * 4), width)
    ok = [
        (t, i) for t, i in infos.items()
        if i.get("mime") in PHOTO_MIME and i.get("width", 0) >= MIN_PHOTO_WIDTH and license_ok(i)
    ]  # fmt: skip
    ok.sort(key=lambda ti: titles.index(ti[0]))
    picked = evenly(ok, need)
    if len(picked) < need:
        print(f"  ! {tag}: only {len(picked)} usable files of {need}", file=sys.stderr)
    out = []
    for title, info in picked:
        used.add(title)
        ext = ".png" if info["mime"] == "image/png" else ".jpg"
        url = info.get("thumburl") or info["url"]
        out.append(
            {
                "path": f"photos/{tag}/{slug(title)}{ext}",
                "kind": "photo",
                "tag": tag,
                "download_url": url,
                "bytes": content_length(url),
                "sha256": None,
                **describe(title, info),
            }
        )
    return out


def pick_videos(tag: str, category: str, need: int, max_seconds: float) -> list[dict]:
    titles = [t for t in commons.category_files(category) if t.lower().endswith(VIDEO_EXT)]
    infos = commons.file_info(evenly(titles, need * 6), 320)
    ok = []
    for title, info in infos.items():
        seconds = duration_of(info)
        if seconds and seconds <= max_seconds and license_ok(info):
            ok.append((title, info, seconds))
    ok.sort(key=lambda x: titles.index(x[0]))
    out = []
    for title, info, seconds in ok:
        if len(out) == need:
            break
        # Prefer a small transcode (360p-480p WebM); fall back to the original if small enough.
        derivatives = [
            d for d in commons.video_derivatives(title)
            if d.get("type", "").startswith("video/webm") and 240 <= (d.get("height") or 0) <= 480
        ]  # fmt: skip
        url = derivatives[-1]["src"] if derivatives else info["url"]
        size = content_length(url)
        if size is None or size > 25_000_000:
            continue
        out.append(
            {
                "path": f"videos/{tag}/{slug(title)}.webm",
                "kind": "video",
                "tag": tag,
                "seconds": round(seconds, 1),
                "download_url": url,
                "bytes": size,
                "sha256": None,
                **describe(title, info),
            }
        )
    if len(out) < need:
        print(f"  ! {tag}: only {len(out)} usable videos of {need}", file=sys.stderr)
    return out


def main() -> None:
    spec = yaml.safe_load(DATASET.read_text())
    per_tag = spec["photos_per_tag"]
    width = spec["image_width"]
    compilation_tags = spec["compilation"]["tags"]
    used: set[str] = set()
    files: list[dict] = []

    for tag, category in spec["photos"].items():
        need = per_tag + (1 if tag in compilation_tags else 0)
        print(f"photos  {tag:22s} <- {category}", flush=True)
        picked = pick_photos(tag, category, need, width, used)
        if tag in compilation_tags and picked:
            # The last pick is held out of the photo set and only appears inside the video.
            held_out = picked.pop()
            held_out["kind"] = "compilation_source"
            held_out["path"] = f"compilation/{tag}/{Path(held_out['path']).name}"
            picked.append(held_out)
        files += picked

    videos = spec["videos"]
    for tag, category in videos["tags"].items():
        print(f"videos  {tag:22s} <- {category}", flush=True)
        files += pick_videos(tag, category, videos["per_tag"], videos["max_seconds"])

    seconds = spec["compilation"]["seconds_per_segment"]
    segments = [
        {"tag": tag, "start": i * seconds, "end": (i + 1) * seconds}
        for i, tag in enumerate(compilation_tags)
    ]
    manifest = {
        "source": spec["source"],
        "generated": date.today().isoformat(),
        "note": "Each file keeps its own license; see license, author and page_url.",
        "compilation": {"path": "videos/compilation/compilation.mp4", "segments": segments},
        "files": files,
    }
    MANIFEST.write_text(json.dumps(manifest, indent=2, ensure_ascii=False) + "\n")
    summarize(manifest)


def summarize(manifest: dict) -> None:
    files = manifest["files"]
    kinds = Counter(f["kind"] for f in files)
    licenses = Counter(re.sub(r" [\d.]+$", "", f["license"]) for f in files)
    total = sum(f["bytes"] or 0 for f in files)
    print()
    print(f"manifest: {MANIFEST.relative_to(ROOT)}")
    print("files:    " + ", ".join(f"{n} {k}" for k, n in kinds.items()))
    print("licenses: " + ", ".join(f"{n} {k}" for k, n in licenses.most_common()))
    largest = max(f["bytes"] or 0 for f in files)
    print(f"download: {total / 1e6:.1f} MB total, largest {largest / 1e6:.1f} MB")
    per_tag = Counter(f["tag"] for f in files if f["kind"] == "photo")
    short = [t for t, n in per_tag.items() if n < 7]
    print(f"photo tags: {len(per_tag)}" + (f" (short: {', '.join(short)})" if short else ""))


if __name__ == "__main__":
    main()
