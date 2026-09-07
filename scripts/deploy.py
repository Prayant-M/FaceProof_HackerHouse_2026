"""Compile and deploy FaceEvidenceRegistry.

Uses py-solc-x so the pipeline has no Node.js dependency at runtime. Hardhat
(package.json) exists only to run the Solidity unit tests.

    python scripts/deploy.py --chain local
    python scripts/deploy.py --chain base-sepolia
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from web3 import Web3  # noqa: E402

from faceproof import config  # noqa: E402

try:  # web3 >= 7
    from web3.middleware import ExtraDataToPOAMiddleware as _POA
except ImportError:  # web3 6.x
    from web3.middleware import geth_poa_middleware as _POA  # type: ignore

SRC = config.ROOT / "contracts" / "FaceEvidenceRegistry.sol"

# Printed when the deployer has no gas money. Testnet ETH only -- it is free,
# has no market value, and cannot be moved to or from a mainnet.
FAUCETS = {
    "base-sepolia": [
        ("Coinbase", "https://portal.cdp.coinbase.com/products/faucet"),
        ("Alchemy", "https://www.alchemy.com/faucets/base-sepolia"),
        ("QuickNode", "https://faucet.quicknode.com/base/sepolia"),
    ],
    "sepolia": [
        ("Alchemy", "https://www.alchemy.com/faucets/ethereum-sepolia"),
        ("Google", "https://cloud.google.com/application/web3/faucet/ethereum/sepolia"),
    ],
}


def compile_contract(version: str) -> tuple[list, str]:
    import solcx

    installed = [str(v) for v in solcx.get_installed_solc_versions()]
    if version not in installed:
        print(f"installing solc {version} ...")
        solcx.install_solc(version)

    out = solcx.compile_files(
        [str(SRC)],
        output_values=["abi", "bin"],
        solc_version=version,
        optimize=True,
        optimize_runs=200,
    )
    key = next(k for k in out if k.endswith(":FaceEvidenceRegistry"))
    return out[key]["abi"], out[key]["bin"]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--chain", default=config.DEFAULT_CHAIN, choices=sorted(config.CHAINS))
    ap.add_argument("--solc", default=config.SOLC_VERSION)
    ap.add_argument("--force", action="store_true",
                    help="redeploy even if a deployment record already exists")
    args = ap.parse_args()

    dep_path = config.deployment_path(args.chain)
    if dep_path.is_file() and not args.force:
        d = json.loads(dep_path.read_text())
        print(f"already deployed on {args.chain}: {d['address']}")
        print("use --force to deploy a fresh instance")
        return 0

    cfg = config.CHAINS[args.chain]
    if not cfg["rpc"]:
        print(f"no RPC for {args.chain} -- set it in .env", file=sys.stderr)
        return 2
    key = config.private_key_for(args.chain)
    problem = config.key_error(args.chain, key)
    if problem:
        print(problem, file=sys.stderr)
        return 2

    print(f"compiling {SRC.name} with solc {args.solc} ...")
    abi, bytecode = compile_contract(args.solc)

    w3 = Web3(Web3.HTTPProvider(cfg["rpc"], request_kwargs={"timeout": 60}))
    try:
        w3.middleware_onion.inject(_POA, layer=0)
    except Exception:
        pass
    if not w3.is_connected():
        print(f"cannot reach {cfg['rpc']}", file=sys.stderr)
        return 2

    acct = w3.eth.account.from_key(key)
    bal = w3.from_wei(w3.eth.get_balance(acct.address), "ether")
    print(f"deployer {acct.address}  balance {bal} ETH  chain id {w3.eth.chain_id}")
    if bal == 0:
        # Continuing here only produces `gas required exceeds allowance (0)`
        # wrapped in a web3 traceback, which is a confusing way to say "no
        # funds". Stop with the address and the faucets instead.
        print(f"\nzero balance -- nothing to pay gas with on {args.chain}.\n",
              file=sys.stderr)
        print(f"  fund this address:  {acct.address}\n", file=sys.stderr)
        for name, url in FAUCETS.get(args.chain, []):
            print(f"    {name:10s} {url}", file=sys.stderr)
        print("\nfunds usually land within a minute. re-run this command after.",
              file=sys.stderr)
        return 2

    Contract = w3.eth.contract(abi=abi, bytecode=bytecode)
    tx = Contract.constructor().build_transaction({
        "from": acct.address,
        "nonce": w3.eth.get_transaction_count(acct.address),
        "chainId": w3.eth.chain_id,
    })
    tx["gas"] = int(w3.eth.estimate_gas(tx) * 1.25)

    signed = acct.sign_transaction(tx)
    raw = getattr(signed, "raw_transaction", None) or getattr(signed, "rawTransaction")
    tx_hash = w3.eth.send_raw_transaction(raw)
    print(f"deploy tx {tx_hash.hex()} -- waiting for receipt ...")
    rcpt = w3.eth.wait_for_transaction_receipt(tx_hash, timeout=300)
    if rcpt.status != 1:
        print("deployment reverted", file=sys.stderr)
        return 1

    tx_hex = rcpt.transactionHash.hex()
    if not tx_hex.startswith("0x"):  # web3 7 returns bare hex
        tx_hex = "0x" + tx_hex

    record = {
        "network": args.chain,
        "chain_id": w3.eth.chain_id,
        "address": rcpt.contractAddress,
        "deployer": acct.address,
        "tx_hash": tx_hex,
        "block": rcpt.blockNumber,
        "gas_used": rcpt.gasUsed,
        "solc": args.solc,
        "abi": abi,
    }
    dep_path.write_text(json.dumps(record, indent=2), encoding="utf-8")

    print(f"\ndeployed at {rcpt.contractAddress}")
    print(f"gas used    {rcpt.gasUsed:,}")
    if cfg["explorer"]:
        print(f"explorer    {cfg['explorer']}{tx_hex}")
    print(f"saved       {dep_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
