"""Stage 5 - the evidence bundle.

The bundle is the thing that gets hashed and anchored, so its serialization
must be byte-for-byte reproducible on any machine, in any Python version, in
any order the dict was built. That means canonical JSON:

    sorted keys, no whitespace, UTF-8, no NaN/Infinity

Without this, `verify` would fail spuriously and the whole tamper-evidence
claim would be worthless.

Volatile data (the full audit trail, the anchoring receipt) lives OUTSIDE the
hashed region, in the envelope. Only `bundle` is hashed.
"""

from __future__ import annotations

import datetime
import json
from pathlib import Path

from . import PIPELINE_VERSION, config
from .hashutil import sha256_bytes


def canonical(obj) -> bytes:
    """Deterministic JSON serialization -- the input to every evidence hash."""
    return json.dumps(
        obj, sort_keys=True, separators=(",", ":"),
        ensure_ascii=False, allow_nan=False,
    ).encode("utf-8")


def build_bundle(probe: dict, match: dict, search_trace: list[dict],
                 audit: list[dict], threshold: float) -> dict:
    """Assemble the hashed core of an evidence record.

    Note what is absent: no raw embedding, no image bytes, no face crop. Only
    digests. This bundle is safe to publish; the biometric data is not.
    """
    return {
        "version": PIPELINE_VERSION,
        "created_at": datetime.datetime.now(datetime.UTC).isoformat(timespec="seconds"),
        "probe": {
            "sha256": probe["sha256"],
            "phash": probe["phash"],
            "embedding_hash": probe["embedding_hash"],
            "det_score": round(float(probe["det_score"]), 4),
            "bytes": probe["bytes"],
        },
        "match": {
            "page_url": match["page_url"],
            "image_url": match["image_url"],
            "platform": match["platform"],
            "title": match["title"],
            "image_sha256": match["image_sha256"],
            "image_phash": match["image_phash"],
            "embedding_hash": match["embedding_hash"],
            "retrieved_at": match["retrieved_at"],
            "http_status": match["http_status"],
            "content_length": match["content_length"],
        },
        "similarity": round(float(match["similarity"]), 6),
        "decision": {
            "threshold": round(float(threshold), 4),
            "metric": "arcface_cosine",
        },
        "search": {
            "provider": match["provider"],
            "providers_attempted": [t.get("provider") for t in search_trace],
            "candidates_examined": len(audit),
            "candidates_matched": sum(1 for a in audit if a["status"] == "MATCH"),
        },
    }


def evidence_hash(bundle: dict) -> str:
    return sha256_bytes(canonical(bundle))


def envelope(bundle: dict, search_trace: list[dict], audit: list[dict],
             scan_id: str) -> dict:
    """Wrap the hashed bundle with non-hashed context."""
    return {
        "scan_id": scan_id,
        "evidence_hash": evidence_hash(bundle),
        "bundle": bundle,
        "audit": {
            "search_trace": search_trace,
            "candidates": audit,
        },
        "anchor": None,
    }


def save(env: dict, path: str | Path | None = None) -> Path:
    path = Path(path or config.OUT / f"ev_{env['scan_id']}.json")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(env, indent=2, ensure_ascii=False), encoding="utf-8")
    return path


def load(path: str | Path) -> dict:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def recompute(env: dict) -> str:
    """Re-derive the evidence hash from the stored bundle.

    If someone edited the bundle after anchoring, this returns a different
    digest than `env['evidence_hash']` -- and a different digest than the one
    on chain.
    """
    return evidence_hash(env["bundle"])
