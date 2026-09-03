import hashlib

import pytest

from faceproof import merkle


def leaf(i: int) -> bytes:
    return hashlib.sha256(f"leaf-{i}".encode()).digest()


@pytest.mark.parametrize("n", [1, 2, 3, 4, 5, 8, 9, 17])
def test_every_leaf_proves_inclusion(n):
    leaves = [leaf(i) for i in range(n)]
    root, levels = merkle.build(leaves)
    for i in range(n):
        assert merkle.verify(root, leaves[i], merkle.proof(levels, i)), f"leaf {i}"


def test_wrong_leaf_fails():
    leaves = [leaf(i) for i in range(6)]
    root, levels = merkle.build(leaves)
    assert not merkle.verify(root, leaf(999), merkle.proof(levels, 0))


def test_sorted_pairing_is_order_independent():
    a, b = leaf(1), leaf(2)
    assert merkle._pair(a, b) == merkle._pair(b, a)


def test_single_leaf_is_its_own_root():
    root, levels = merkle.build([leaf(0)])
    assert root == leaf(0)
    assert merkle.proof(levels, 0) == []


def test_empty_rejected():
    with pytest.raises(ValueError):
        merkle.build([])
