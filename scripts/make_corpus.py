"""Add one real post to the offline corpus used by the `local` provider.

    python scripts/make_corpus.py --url https://www.instagram.com/p/XYZ/ --image dl.jpg
    python scripts/make_corpus.py --url https://x.com/user/status/123 --image-url https://...

The corpus is a fallback for when the live providers are unavailable. It must
be disclosed in the README whenever it is used in a demo.
"""

from __future__ import annotations

import argparse
import datetime
import json
import shutil
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import requests  # noqa: E402

from faceproof import config  # noqa: E402


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--url", required=True, help="the real post page URL")
    ap.add_argument("--image", help="local image file already downloaded")
    ap.add_argument("--image-url", help="download the image from here instead")
    ap.add_argument("--title", default="")
    ap.add_argument("--name", help="corpus entry name (default: post_NNN)")
    args = ap.parse_args()

    if not (args.image or args.image_url):
        ap.error("pass --image or --image-url")

    config.CORPUS.mkdir(parents=True, exist_ok=True)
    existing = sorted(config.CORPUS.glob("post_*.json"))
    name = args.name or f"post_{len(existing) + 1:03d}"

    if args.image:
        src = Path(args.image)
        dest = config.CORPUS / f"{name}{src.suffix.lower()}"
        shutil.copy2(src, dest)
    else:
        r = requests.get(args.image_url, timeout=config.HTTP_TIMEOUT,
                         headers={"User-Agent": config.USER_AGENT})
        r.raise_for_status()
        ext = ".png" if r.content[:8].startswith(b"\x89PNG") else ".jpg"
        dest = config.CORPUS / f"{name}{ext}"
        dest.write_bytes(r.content)

    meta = {
        "page_url": args.url,
        "title": args.title,
        "captured_at": datetime.datetime.now(datetime.UTC).isoformat(timespec="seconds"),
        "image_url": args.image_url or "",
    }
    (config.CORPUS / f"{name}.json").write_text(
        json.dumps(meta, indent=2), encoding="utf-8")

    print(f"added {dest.name} -> {args.url}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
