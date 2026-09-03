"""Merkle tree with sorted-pair hashing.

Sorted pairs (hash the smaller sibling first) means an inclusion proof needs no
left/right position bits -- the proof is just a list of sibling hashes. The
Solidity `verifyInclusion` uses the identical rule, so proofs built here verify
on chain without translation.
"""

from __future__ import annotations

from eth_utils import keccak


def _pair(a: bytes, b: bytes) -> bytes:
    return keccak(a + b) if a <= b else keccak(b + a)


def build(leaves: list[bytes]) -> tuple[bytes, list[list[bytes]]]:
    """Return (root, levels). levels[0] is the leaf level."""
    if not leaves:
        raise ValueError("cannot build a Merkle tree with no leaves")
    levels: list[list[bytes]] = [list(leaves)]
    while len(levels[-1]) > 1:
        cur = levels[-1]
        levels.append([
            _pair(cur[i], cur[i + 1]) if i + 1 < len(cur) else cur[i]
            for i in range(0, len(cur), 2)
        ])
    return levels[-1][0], levels


def proof(levels: list[list[bytes]], index: int) -> list[bytes]:
    """Sibling path for the leaf at `index`."""
    out: list[bytes] = []
    for lvl in levels[:-1]:
        sib = index ^ 1
        if sib < len(lvl):
            out.append(lvl[sib])
        index //= 2
    return out


def verify(root: bytes, leaf: bytes, path: list[bytes]) -> bool:
    """Local mirror of the on-chain check -- used by tests."""
    h = leaf
    for p in path:
        h = _pair(h, p)
    return h == root
