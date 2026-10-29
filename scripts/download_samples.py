"""Download the eval samples listed in scripts/samples_manifest.json into samples/.

    python scripts/download_samples.py            # download and verify checksums
    python scripts/download_samples.py --record   # first run only: store checksums in the manifest

Also builds the synthetic compilation video (held-out photos, known segments) and writes
samples/ATTRIBUTION.md, since most files are CC BY / CC BY-SA and need attribution.
Run with the backend environment (it needs PyAV, Pillow and NumPy for the compilation).
"""

import argparse
import hashlib
import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import commons  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
MANIFEST = ROOT / "scripts" / "samples_manifest.json"
SAMPLES = ROOT / "samples"


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def download(entry: dict, record: bool) -> str:
    dest = SAMPLES / entry["path"]
    expected = entry.get("sha256")
    if dest.exists() and (expected is None or sha256(dest) == expected):
        if expected is None and record:
            entry["sha256"] = sha256(dest)
        return "cached"

    dest.parent.mkdir(parents=True, exist_ok=True)
    tmp = dest.with_suffix(dest.suffix + ".part")
    time.sleep(0.25)  # be gentle with upload.wikimedia.org
    with commons.open_url(entry["download_url"], timeout=120) as response, tmp.open("wb") as out:
        while chunk := response.read(1 << 20):
            out.write(chunk)
    actual = sha256(tmp)
    if expected and actual != expected:
        tmp.unlink()
        raise RuntimeError(f"checksum mismatch for {entry['path']}: the file changed upstream")
    tmp.replace(dest)
    if record:
        entry["sha256"] = actual
    return "downloaded"


def build_compilation(manifest: dict, seconds_per_segment: float) -> Path:
    """Stitch held-out photos into one video with a slow zoom, one segment per tag."""
    import av
    import numpy as np
    from PIL import Image

    width, height, fps = 640, 360, 24
    sources = {
        f["tag"]: SAMPLES / f["path"]
        for f in manifest["files"]
        if f["kind"] == "compilation_source"
    }
    out = SAMPLES / manifest["compilation"]["path"]
    out.parent.mkdir(parents=True, exist_ok=True)
    with av.open(str(out), "w") as container:
        stream = container.add_stream("libx264", rate=fps)
        stream.width, stream.height, stream.pix_fmt = width, height, "yuv420p"
        for segment in manifest["compilation"]["segments"]:
            image = Image.open(sources[segment["tag"]]).convert("RGB")
            frames = round(seconds_per_segment * fps)
            for i in range(frames):
                zoom = 1.0 + 0.12 * i / frames
                crop_h = min(image.height, image.width * height / width) / zoom
                crop_w = crop_h * width / height
                left, top = (image.width - crop_w) / 2, (image.height - crop_h) / 2
                frame = image.crop((left, top, left + crop_w, top + crop_h)).resize((width, height))
                packet = stream.encode(
                    av.VideoFrame.from_ndarray(np.asarray(frame), format="rgb24")
                )
                container.mux(packet)
        container.mux(stream.encode())
    return out


def write_attribution(manifest: dict) -> None:
    lines = [
        "# Sample attribution",
        "",
        "Downloaded from Wikimedia Commons by scripts/download_samples.py. Each file keeps its",
        "own license. `videos/compilation/compilation.mp4` is a derivative of the",
        "`compilation/` photos below and is shared under the same terms as those photos.",
        "",
        "| File | Author | License | Source |",
        "|---|---|---|---|",
    ]
    for f in manifest["files"]:
        author = (f["author"] or "unknown").replace("|", "/")
        lines.append(f"| `{f['path']}` | {author} | {f['license']} | {f['page_url']} |")
    (SAMPLES / "ATTRIBUTION.md").write_text("\n".join(lines) + "\n")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--record", action="store_true", help="store checksums in the manifest")
    args = parser.parse_args()

    manifest = json.loads(MANIFEST.read_text())
    files = manifest["files"]
    counts = {"downloaded": 0, "cached": 0}
    for n, entry in enumerate(files, start=1):
        counts[download(entry, args.record)] += 1
        print(f"\r{n}/{len(files)} files", end="", flush=True)
    print(f"\n{counts['downloaded']} downloaded, {counts['cached']} already present")

    if args.record:
        MANIFEST.write_text(json.dumps(manifest, indent=2, ensure_ascii=False) + "\n")
        print("checksums recorded in", MANIFEST.relative_to(ROOT))

    segments = manifest["compilation"]["segments"]
    seconds = segments[0]["end"] - segments[0]["start"]
    print("compilation:", build_compilation(manifest, seconds).relative_to(ROOT))
    write_attribution(manifest)
    print("attribution: samples/ATTRIBUTION.md")


if __name__ == "__main__":
    main()
