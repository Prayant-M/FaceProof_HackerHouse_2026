"""Hashing helpers shared by every stage.

Three independent fingerprints are used throughout the pipeline:

  sha256          exact bytes         -- breaks on a single re-encode
  pHash           perceptual (64-bit) -- survives resize / re-compression
  embedding hash  semantic            -- derived from the ArcFace vector

All three are reduced to 32-byte values so they can be stored as `bytes32`
on chain.
"""

from __future__ import annotations

import hashlib
from pathlib import Path

import numpy as np


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_file(path: str | Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def phash_hex(path: str | Path) -> str:
    """64-bit perceptual hash as 16 lowercase hex chars."""
    import imagehash
    from PIL import Image

    with Image.open(path) as im:
        return str(imagehash.phash(im.convert("RGB")))


def phash_hex_bytes(data: bytes) -> str:
    import io

    import imagehash
    from PIL import Image

    with Image.open(io.BytesIO(data)) as im:
        return str(imagehash.phash(im.convert("RGB")))


def embedding_hash(emb: np.ndarray) -> str:
    """Hash a face embedding irreversibly.

    The vector is quantized to int8 first so that harmless float jitter
    (different BLAS backend, different CPU) does not change the digest.

    NOTE: this digest is what goes on chain. The raw embedding -- which is
    biometric data -- never leaves the local machine.
    """
    q = np.round(np.asarray(emb, dtype=np.float32) * 127).astype(np.int8)
    return hashlib.sha256(q.tobytes()).hexdigest()


def to_bytes32(hex_str: str) -> bytes:
    """Left-pad any hex digest to exactly 32 bytes."""
    h = (hex_str or "").removeprefix("0x")
    if len(h) > 64:
        raise ValueError(f"digest too long for bytes32: {len(h)} hex chars")
    return bytes.fromhex(h.rjust(64, "0"))


def hamming_hex(a: str, b: str) -> int:
    """Hamming distance between two equal-length hex strings."""
    if not a or not b:
        return 64
    ia, ib = int(a, 16), int(b, 16)
    return bin(ia ^ ib).count("1")
