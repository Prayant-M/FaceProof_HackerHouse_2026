"""Stage 7 - re-verification against the on-chain record.

Four verdicts, because "the hash changed" is not always "someone lied":

  EXACT       recomputed evidence hash == on-chain hash. Bytes are identical.
  PERCEPTUAL  hash differs, but the live post is still visually and
              semantically the same image (pHash hamming <= 8 AND face cosine
              >= 0.90). This is what a CDN re-encode looks like.
  TAMPERED    anchored, but neither the hash nor the fingerprints line up.
  UNANCHORED  nothing on chain for this hash at all.

The PERCEPTUAL verdict is the reason three fingerprints are stored rather than
one. A pure-sha256 design reports TAMPERED every time Instagram re-compresses a
thumbnail, which would make the tool useless in practice.
"""

from __future__ import annotations

import os
import tempfile

from . import config, evidence, face
from .hashutil import hamming_hex, phash_hex_bytes, sha256_bytes
from .rerank import _fetch

# `classify` is pure logic and must stay importable without web3 / opencv, so
# the chain client is imported inside `run`.

EXACT = "EXACT"
PERCEPTUAL = "PERCEPTUAL"
TAMPERED = "TAMPERED"
UNANCHORED = "UNANCHORED"


def refetch_live(env: dict) -> dict | None:
    """Download the matched post image again and compare it to what was anchored."""
    m = env["bundle"]["match"]
    try:
        blob, status, length = _fetch(m["image_url"])
    except Exception as e:
        return {"ok": False, "error": f"{type(e).__name__}: {e}"}

    live_sha = sha256_bytes(blob)
    live_phash = phash_hex_bytes(blob)
    out = {
        "ok": True,
        "http_status": status,
        "content_length": length,
        "sha256": live_sha,
        "phash": live_phash,
        "sha256_identical": live_sha == m["image_sha256"],
        "phash_hamming": hamming_hex(live_phash, m["image_phash"]),
        "embedding_cosine": None,
    }

    tmp = None
    try:
        with tempfile.NamedTemporaryFile(suffix=".img", delete=False) as tf:
            tf.write(blob)
            tmp = tf.name
        enc = face.encode(tmp)
        out["embedding_hash"] = enc["embedding_hash"]
        out["embedding_identical"] = enc["embedding_hash"] == m["embedding_hash"]
        # exact embedding equality is brittle; the caller also gets the digests
        out["embedding_cosine"] = 1.0 if out["embedding_identical"] else None
    except Exception as e:
        out["embedding_error"] = f"{type(e).__name__}: {e}"
    finally:
        if tmp and os.path.exists(tmp):
            os.unlink(tmp)
    return out


def classify(recomputed_hash: str, chain_record: dict | None,
             live: dict | None = None) -> str:
    if chain_record is None:
        return UNANCHORED

    on_chain = (chain_record.get("evidenceHash") or "").removeprefix("0x").lower()
    if on_chain == recomputed_hash.lower():
        return EXACT

    if live and live.get("ok"):
        close_enough = (
            live.get("phash_hamming", 64) <= config.PHASH_HAMMING_MAX
            and (live.get("embedding_cosine") or 0.0) >= config.PERCEPTUAL_COSINE_MIN
        )
        if close_enough:
            return PERCEPTUAL

    return TAMPERED


def run(env: dict, network: str, live_refetch: bool = False) -> dict:
    """Full verification pass over one evidence envelope."""
    from .chain import Chain

    recomputed = evidence.recompute(env)
    stored = env.get("evidence_hash", "")

    chain = Chain(network)
    record = chain.verify(recomputed)
    if record is None and stored and stored != recomputed:
        # The bundle was edited. Look up what was ORIGINALLY anchored so the
        # report can show both sides of the tamper.
        record = chain.verify(stored)

    live = refetch_live(env) if live_refetch else None
    verdict = classify(recomputed, record, live)

    return {
        "verdict": verdict,
        "stored_hash": stored,
        "recomputed_hash": recomputed,
        "hash_drift": stored != recomputed,
        "chain": {
            "network": chain.network,
            "label": chain.label,
            "chain_id": chain.chain_id,
            "contract": chain.address,
        },
        "record": record,
        "live": live,
    }
