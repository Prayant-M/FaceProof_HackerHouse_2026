"""Stage 1 - ingest the probe image.

Records the exact bytes that entered the pipeline before anything touches them.
EXIF is stripped from the working copy (it can carry GPS and device serials)
but the sha256 recorded is of the ORIGINAL file, so chain of custody survives.
"""

from __future__ import annotations

import datetime
import shutil
import uuid
from pathlib import Path

from PIL import Image

from . import config
from .hashutil import phash_hex, sha256_file


def new_scan_id() -> str:
    return uuid.uuid4().hex[:12]


def ingest(image_path: str | Path, scan_id: str | None = None) -> dict:
    src = Path(image_path)
    if not src.is_file():
        raise FileNotFoundError(f"no such image: {src}")

    scan_id = scan_id or new_scan_id()
    workdir = config.OUT / f"scan_{scan_id}"
    workdir.mkdir(parents=True, exist_ok=True)

    original = workdir / f"original{src.suffix.lower() or '.jpg'}"
    shutil.copy2(src, original)

    # EXIF-stripped working copy
    clean = workdir / "clean.jpg"
    with Image.open(original) as im:
        rgb = im.convert("RGB")
        rgb.save(clean, format="JPEG", quality=95)

    return {
        "scan_id": scan_id,
        "workdir": str(workdir),
        "source_path": str(src.resolve()),
        "original_path": str(original),
        "clean_path": str(clean),
        "sha256": sha256_file(original),
        "phash": phash_hex(clean),
        "bytes": original.stat().st_size,
        "ingested_at": datetime.datetime.now(datetime.UTC).isoformat(timespec="seconds"),
    }
