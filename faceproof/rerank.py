"""Stage 4 - adversarial re-rank. The core of the project.

A reverse image search returns "things that look similar", which is not the
same claim as "this is the same person". So nothing a provider says is taken
at face value: every candidate image is downloaded, the face is detected and
re-embedded locally, and the cosine similarity against the probe embedding
decides whether it becomes evidence.

Every candidate -- accepted, rejected, or unfetchable -- is recorded with its
score, so the audit trail shows the full decision, not just the winner.
"""

from __future__ import annotations

import datetime
import os
import tempfile
from pathlib import Path
from urllib.parse import unquote, urlparse

import numpy as np
import requests

from . import config, face
from .hashutil import phash_hex_bytes, sha256_bytes
from .search.base import Candidate

REJECT_NON_SOCIAL = "not a social domain"
REJECT_NO_FACE = "no face detected"
REJECT_BELOW_THRESHOLD = "below similarity threshold"


def _fetch(url: str) -> tuple[bytes, int, int]:
    """Return (bytes, http_status, content_length). Supports file:// for the
    local corpus provider."""
    if url.startswith("file://"):
        p = Path(unquote(urlparse(url).path.lstrip("/")))
        data = p.read_bytes()
        return data, 200, len(data)
    r = requests.get(url, timeout=config.HTTP_TIMEOUT,
                     headers={"User-Agent": config.USER_AGENT})
    r.raise_for_status()
    return r.content, r.status_code, len(r.content)


def rerank(probe_emb: np.ndarray,
           candidates: list[Candidate],
           threshold: float | None = None,
           social_only: bool = True,
           on_event=None) -> tuple[list[dict], list[dict]]:
    """Verify candidates against the probe face.

    Returns (hits, audit). `hits` is sorted best-first; each entry carries
    everything the evidence bundle needs about the matched post.
    """
    threshold = config.FACE_MATCH_THRESHOLD if threshold is None else threshold
    audit: list[dict] = []
    hits: list[dict] = []

    for c in candidates:
        row = {
            "page_url": c.page_url,
            "image_url": c.image_url,
            "platform": c.platform,
            "provider": c.provider,
            "similarity": None,
            "status": "",
        }

        if social_only and not c.is_social:
            row["status"] = REJECT_NON_SOCIAL
            audit.append(row)
            if on_event:
                on_event(row)
            continue

        try:
            blob, status, length = _fetch(c.image_url)
        except Exception as e:
            row["status"] = f"fetch failed: {type(e).__name__}"
            audit.append(row)
            if on_event:
                on_event(row)
            continue

        tmp = None
        try:
            with tempfile.NamedTemporaryFile(suffix=".img", delete=False) as tf:
                tf.write(blob)
                tmp = tf.name
            enc = face.encode(tmp)
        except ValueError:
            row["status"] = REJECT_NO_FACE
            audit.append(row)
            if on_event:
                on_event(row)
            continue
        except Exception as e:
            row["status"] = f"decode failed: {type(e).__name__}"
            audit.append(row)
            if on_event:
                on_event(row)
            continue
        finally:
            if tmp and os.path.exists(tmp):
                os.unlink(tmp)

        sim = face.cosine(probe_emb, enc["embedding"])
        row["similarity"] = round(sim, 6)

        if sim < threshold:
            row["status"] = REJECT_BELOW_THRESHOLD
            audit.append(row)
            if on_event:
                on_event(row)
            continue

        row["status"] = "MATCH"
        audit.append(row)
        if on_event:
            on_event(row)

        hits.append({
            "page_url": c.page_url,
            "image_url": c.image_url,
            "platform": c.platform,
            "title": c.title,
            "snippet": c.snippet,
            "provider": c.provider,
            "similarity": sim,
            "image_sha256": sha256_bytes(blob),
            "image_phash": phash_hex_bytes(blob),
            "embedding_hash": enc["embedding_hash"],
            "det_score": round(enc["det_score"], 4),
            "http_status": status,
            "content_length": length,
            "retrieved_at": datetime.datetime.now(datetime.UTC)
                                    .isoformat(timespec="seconds"),
        })

    hits.sort(key=lambda h: -h["similarity"])
    return hits, audit
