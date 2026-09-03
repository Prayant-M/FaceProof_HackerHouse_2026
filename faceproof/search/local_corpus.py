"""Offline corpus provider - the demo floor.

Indexes a folder of REAL social posts you collected earlier. Each entry is an
image plus a sidecar .json describing the post it came from:

    samples/corpus/
        post_001.jpg
        post_001.json   {"page_url": "...", "title": "...", "captured_at": "..."}

The matching step is still genuine -- every corpus image is face-embedded and
compared to the probe -- but the *discovery* step is local, so this provider
must be disclosed in the README and never presented as a live web search.

Use it when: you are offline, out of SerpApi credits, or the venue Wi-Fi died
five minutes before your demo.
"""

from __future__ import annotations

import json
from pathlib import Path

from .. import config
from .base import Candidate, SearchProvider

_IMAGE_EXT = {".jpg", ".jpeg", ".png", ".webp", ".bmp"}


class LocalCorpus(SearchProvider):
    name = "local_corpus"
    requires_key = False

    def __init__(self, root: Path | None = None):
        self.root = Path(root or config.CORPUS)

    def available(self) -> bool:
        return self.root.is_dir() and any(
            p.suffix.lower() in _IMAGE_EXT for p in self.root.iterdir() if p.is_file()
        )

    def search(self, image_path: str, limit: int = 25) -> list[Candidate]:
        out: list[Candidate] = []
        for p in sorted(self.root.iterdir()):
            if not p.is_file() or p.suffix.lower() not in _IMAGE_EXT:
                continue
            meta = {}
            side = p.with_suffix(".json")
            if side.is_file():
                try:
                    meta = json.loads(side.read_text(encoding="utf-8"))
                except json.JSONDecodeError:
                    meta = {}
            out.append(Candidate(
                page_url=meta.get("page_url", f"file://{p.resolve()}"),
                image_url=p.resolve().as_uri(),
                title=meta.get("title", p.stem),
                snippet=meta.get("captured_at", ""),
                provider=self.name,
                raw={"local_file": str(p), **meta},
            ))
            if len(out) >= limit:
                break
        return out
