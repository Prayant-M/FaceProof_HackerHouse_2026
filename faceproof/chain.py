"""Stage 6 - blockchain client.

Talks to FaceEvidenceRegistry over web3.py. Works against a local Anvil /
Hardhat node and against public testnets (Base Sepolia, Sepolia) with the same
code path -- only the RPC URL and the explorer prefix differ.

Only hashes go on chain. See contracts/FaceEvidenceRegistry.sol.
"""

from __future__ import annotations

import json
from pathlib import Path

from web3 import Web3

from . import config
from .hashutil import to_bytes32

try:  # web3 >= 7
    from web3.middleware import ExtraDataToPOAMiddleware as _POA
except ImportError:  # web3 6.x
    from web3.middleware import geth_poa_middleware as _POA  # type: ignore

RECORD_FIELDS = [
    "evidenceHash", "pHash", "embeddingHash", "merkleRoot",
    "timestamp", "itemCount", "submitter", "cid",
]


class ChainError(RuntimeError):
    pass


def load_deployment(network: str) -> dict:
    p = config.deployment_path(network)
    if not p.is_file():
        raise ChainError(
            f"no deployment for {network!r}. Run:  python scripts/deploy.py --chain {network}"
        )
    return json.loads(p.read_text(encoding="utf-8"))


def _record_to_dict(rec) -> dict:
    d = dict(zip(RECORD_FIELDS, rec))
    for k in ("evidenceHash", "pHash", "embeddingHash", "merkleRoot"):
        v = d[k]
        d[k] = v.hex() if isinstance(v, (bytes, bytearray)) else str(v)
    d["timestamp"] = int(d["timestamp"])
    d["itemCount"] = int(d["itemCount"])
    return d


class Chain:
    def __init__(self, network: str = None, address: str = None, abi: list = None):
        self.network = network or config.DEFAULT_CHAIN
        if self.network not in config.CHAINS:
            raise ChainError(f"unknown chain {self.network!r}")
        cfg = config.CHAINS[self.network]
        if not cfg["rpc"]:
            raise ChainError(f"no RPC configured for {self.network!r} (check .env)")

        self.explorer = cfg["explorer"]
        self.label = cfg["name"]
        self.w3 = Web3(Web3.HTTPProvider(cfg["rpc"], request_kwargs={"timeout": 60}))
        try:
            self.w3.middleware_onion.inject(_POA, layer=0)
        except Exception:
            pass
        if not self.w3.is_connected():
            raise ChainError(f"cannot reach RPC {cfg['rpc']}")

        if address is None or abi is None:
            dep = load_deployment(self.network)
            address, abi = dep["address"], dep["abi"]
        self.address = Web3.to_checksum_address(address)
        self.contract = self.w3.eth.contract(address=self.address, abi=abi)

        if not config.PRIVATE_KEY:
            raise ChainError("PRIVATE_KEY missing from .env")
        self.acct = self.w3.eth.account.from_key(config.PRIVATE_KEY)

    # ------------------------------------------------------------ helpers
    @property
    def chain_id(self) -> int:
        return self.w3.eth.chain_id

    def balance_eth(self) -> float:
        return float(self.w3.from_wei(self.w3.eth.get_balance(self.acct.address), "ether"))

    def explorer_url(self, tx_hash: str) -> str | None:
        return (self.explorer + tx_hash) if self.explorer else None

    def _send(self, fn) -> dict:
        tx = fn.build_transaction({
            "from": self.acct.address,
            "nonce": self.w3.eth.get_transaction_count(self.acct.address),
            "chainId": self.chain_id,
        })
        try:
            tx["gas"] = int(self.w3.eth.estimate_gas(tx) * 1.25)
        except Exception as e:
            # A failing estimate is nearly always a revert -- surface it plainly
            # instead of burning gas on a doomed transaction.
            raise ChainError(f"gas estimation failed (transaction would revert): {e}") from e

        signed = self.acct.sign_transaction(tx)
        raw = getattr(signed, "raw_transaction", None) or getattr(signed, "rawTransaction")
        h = self.w3.eth.send_raw_transaction(raw)
        rcpt = self.w3.eth.wait_for_transaction_receipt(h, timeout=240)
        tx_hash = rcpt.transactionHash.hex()
        if not tx_hash.startswith("0x"):
            tx_hash = "0x" + tx_hash
        if rcpt.status != 1:
            raise ChainError(f"transaction reverted: {tx_hash}")
        return {
            "network": self.network,
            "chain_id": self.chain_id,
            "contract": self.address,
            "tx_hash": tx_hash,
            "block": rcpt.blockNumber,
            "gas_used": rcpt.gasUsed,
            "submitter": self.acct.address,
            "explorer": self.explorer_url(tx_hash),
        }

    # ------------------------------------------------------------ writes
    def anchor(self, evidence_hash: str, phash: str, embedding_hash: str,
               cid: str = "") -> dict:
        return self._send(self.contract.functions.anchor(
            to_bytes32(evidence_hash), to_bytes32(phash),
            to_bytes32(embedding_hash), cid))

    def anchor_batch(self, merkle_root: bytes, item_count: int, cid: str = "") -> dict:
        return self._send(self.contract.functions.anchorBatch(
            merkle_root, int(item_count), cid))

    # ------------------------------------------------------------ reads
    def verify(self, evidence_hash: str) -> dict | None:
        found, rec = self.contract.functions.verify(to_bytes32(evidence_hash)).call()
        return _record_to_dict(rec) if found else None

    def verify_inclusion(self, root: bytes, leaf: bytes, proof: list[bytes]) -> bool:
        return bool(self.contract.functions.verifyInclusion(root, leaf, proof).call())

    def record_count(self) -> int:
        return int(self.contract.functions.recordCount().call())

    def record_at(self, idx: int) -> dict:
        return _record_to_dict(self.contract.functions.recordAt(int(idx)).call())
