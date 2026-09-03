import json

import pytest

from faceproof import evidence

PROBE = {
    "sha256": "a" * 64,
    "phash": "0123456789abcdef",
    "embedding_hash": "b" * 64,
    "det_score": 0.987654321,
    "bytes": 123456,
}
MATCH = {
    "page_url": "https://instagram.com/p/XYZ",
    "image_url": "https://cdn.example/img.jpg",
    "platform": "instagram.com",
    "title": "a caption",
    "image_sha256": "c" * 64,
    "image_phash": "fedcba9876543210",
    "embedding_hash": "d" * 64,
    "retrieved_at": "2026-09-04T10:00:00+00:00",
    "http_status": 200,
    "content_length": 91011,
    "similarity": 0.7123456789,
    "provider": "serpapi_google_lens",
}
TRACE = [{"provider": "serpapi_google_lens", "status": "ok", "count": 12}]
AUDIT = [{"status": "MATCH"}, {"status": "below similarity threshold"}]


def bundle():
    return evidence.build_bundle(PROBE, MATCH, TRACE, AUDIT, 0.40)


def test_canonical_is_key_order_independent():
    b = bundle()
    shuffled = json.loads(json.dumps(dict(reversed(list(b.items())))))
    assert evidence.canonical(b) == evidence.canonical(shuffled)


def test_canonical_has_no_whitespace():
    assert b" " not in evidence.canonical(bundle()).replace(b"a caption", b"acaption")


def test_hash_is_stable_across_calls():
    assert evidence.evidence_hash(bundle()) == evidence.evidence_hash(bundle())


def test_single_character_edit_changes_the_hash():
    a = bundle()
    b = bundle()
    b["match"]["title"] = "a captioo"
    assert evidence.evidence_hash(a) != evidence.evidence_hash(b)


def test_bundle_contains_no_raw_biometric_data():
    """The whole privacy claim rests on this."""
    blob = evidence.canonical(bundle()).decode()
    for banned in ("embedding\":[", "vector", "descriptor"):
        assert banned not in blob
    assert "embedding_hash" in blob


def test_nan_is_rejected():
    b = bundle()
    b["similarity"] = float("nan")
    with pytest.raises(ValueError):
        evidence.canonical(b)


def test_envelope_hash_matches_recompute():
    b = bundle()
    env = evidence.envelope(b, TRACE, AUDIT, "deadbeef")
    assert env["evidence_hash"] == evidence.recompute(env)


def test_audit_is_outside_the_hashed_region():
    b = bundle()
    env = evidence.envelope(b, TRACE, AUDIT, "deadbeef")
    before = evidence.recompute(env)
    env["audit"]["candidates"].append({"status": "noise"})
    assert evidence.recompute(env) == before
