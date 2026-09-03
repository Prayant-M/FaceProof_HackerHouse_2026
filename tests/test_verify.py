from faceproof import verify as V
from faceproof.hashutil import hamming_hex, to_bytes32

H = "a" * 64
OTHER = "b" * 64


def rec(h):
    return {"evidenceHash": h, "pHash": "0" * 64, "embeddingHash": "0" * 64,
            "merkleRoot": "0" * 64, "timestamp": 1, "itemCount": 1,
            "submitter": "0x0", "cid": ""}


def test_unanchored_when_no_record():
    assert V.classify(H, None) == V.UNANCHORED


def test_exact_match():
    assert V.classify(H, rec(H)) == V.EXACT


def test_exact_tolerates_0x_prefix():
    assert V.classify(H, rec("0x" + H)) == V.EXACT


def test_tampered_when_hash_differs_and_no_live_data():
    assert V.classify(H, rec(OTHER)) == V.TAMPERED


def test_perceptual_when_reencoded():
    live = {"ok": True, "phash_hamming": 4, "embedding_cosine": 0.97}
    assert V.classify(H, rec(OTHER), live) == V.PERCEPTUAL


def test_perceptual_requires_both_signals():
    assert V.classify(H, rec(OTHER),
                      {"ok": True, "phash_hamming": 4,
                       "embedding_cosine": 0.10}) == V.TAMPERED
    assert V.classify(H, rec(OTHER),
                      {"ok": True, "phash_hamming": 40,
                       "embedding_cosine": 0.99}) == V.TAMPERED


def test_hamming():
    assert hamming_hex("0000000000000000", "0000000000000000") == 0
    assert hamming_hex("0000000000000000", "0000000000000001") == 1
    assert hamming_hex("", "abc") == 64


def test_to_bytes32_pads_a_short_phash():
    b = to_bytes32("0123456789abcdef")
    assert len(b) == 32
    assert b.endswith(bytes.fromhex("0123456789abcdef"))
    assert b[:24] == b"\x00" * 24
