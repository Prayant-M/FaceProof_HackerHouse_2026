"""Central configuration. Everything tunable lives here or in .env."""

from __future__ import annotations

import os
from pathlib import Path

try:
    from dotenv import load_dotenv
except ImportError:  # dotenv is optional at runtime
    def load_dotenv(*_a, **_k):  # type: ignore
        return False

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "out"
SAMPLES = ROOT / "samples"
CORPUS = SAMPLES / "corpus"

load_dotenv(ROOT / ".env")

OUT.mkdir(exist_ok=True)

# ---------------------------------------------------------------- face
# ArcFace cosine similarity on L2-normalized 512-d embeddings.
#   >= 0.40  same person (conservative)
#   0.28-0.40 possible
#   <  0.28  different
FACE_MATCH_THRESHOLD = float(os.getenv("FACE_MATCH_THRESHOLD", "0.40"))
DET_SIZE = int(os.getenv("DET_SIZE", "640"))
INSIGHTFACE_MODEL = os.getenv("INSIGHTFACE_MODEL", "buffalo_l")

# Expand the detected bbox by this fraction before uploading to a search engine.
# Reverse image search performs badly on a tight 112x112 face chip.
CROP_MARGIN = float(os.getenv("CROP_MARGIN", "0.60"))

# ---------------------------------------------------------------- verify
# pHash is a 64-bit perceptual hash. Hamming distance <= 8 means "visually the
# same image" after re-compression / resize.
PHASH_HAMMING_MAX = int(os.getenv("PHASH_HAMMING_MAX", "8"))
PERCEPTUAL_COSINE_MIN = float(os.getenv("PERCEPTUAL_COSINE_MIN", "0.90"))

# ---------------------------------------------------------------- search
SERPAPI_KEY = os.getenv("SERPAPI_KEY", "")
SEARCH_LIMIT = int(os.getenv("SEARCH_LIMIT", "25"))
HTTP_TIMEOUT = int(os.getenv("HTTP_TIMEOUT", "30"))
USER_AGENT = os.getenv(
    "USER_AGENT",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0 Safari/537.36 FaceProof/1.0",
)
PLAYWRIGHT_HEADLESS = os.getenv("PLAYWRIGHT_HEADLESS", "1") != "0"

# ---------------------------------------------------------------- chain
CHAINS = {
    "local": {
        "rpc": os.getenv("LOCAL_RPC", "http://127.0.0.1:8545"),
        "explorer": None,
        "name": "Local (Anvil/Hardhat)",
    },
    "base-sepolia": {
        "rpc": os.getenv("BASE_SEPOLIA_RPC", "https://sepolia.base.org"),
        "explorer": "https://sepolia.basescan.org/tx/",
        "name": "Base Sepolia",
    },
    "sepolia": {
        "rpc": os.getenv("SEPOLIA_RPC", ""),
        "explorer": "https://sepolia.etherscan.io/tx/",
        "name": "Ethereum Sepolia",
    },
}
DEFAULT_CHAIN = os.getenv("DEFAULT_CHAIN", "local")
PRIVATE_KEY = os.getenv("PRIVATE_KEY", "")
SOLC_VERSION = os.getenv("SOLC_VERSION", "0.8.24")

# Hardhat/Anvil account #0. Published in their docs, funded with 10000 fake ETH
# on every fresh node, and worthless anywhere else. Used ONLY as the local-chain
# fallback so `--chain local` works with no configuration at all.
#
# It is deliberately never a fallback for a public network: it is a key every
# bot on every public chain sweeps on sight, and a submitter address anyone can
# forge, which would make the `submitter` field on a public record meaningless.
_HARDHAT_DEV_KEY = (
    "0xac0974bec39a17e36ba4a6b4d238ff944bacb478cbed5efcae784d7bf4f2ff80"
)


def private_key_for(network: str) -> str:
    """Resolve the signing key for one network.

    Resolution order:
      1. PRIVATE_KEY_<NETWORK>   e.g. PRIVATE_KEY_BASE_SEPOLIA
      2. PRIVATE_KEY             the shared fallback
      3. the Hardhat dev key     local chain only

    This lets a throwaway funded wallet sign on a public testnet while the local
    chain keeps using the free pre-funded dev account, from a single .env.
    """
    specific = os.getenv(f"PRIVATE_KEY_{network.upper().replace('-', '_')}", "")
    if specific:
        return specific
    if PRIVATE_KEY:
        return PRIVATE_KEY
    if network == "local":
        return _HARDHAT_DEV_KEY
    return ""


def is_dev_key(key: str) -> bool:
    """True if this is the publicly-known Hardhat/Anvil dev key."""
    return bool(key) and key.lower().removeprefix("0x") == (
        _HARDHAT_DEV_KEY.removeprefix("0x")
    )


def key_error(network: str, key: str) -> str | None:
    """Return a human-readable reason this key must not sign on this network."""
    if not key:
        return (
            f"no signing key for {network!r}. Set PRIVATE_KEY_"
            f"{network.upper().replace('-', '_')} or PRIVATE_KEY in .env"
        )
    if network != "local" and is_dev_key(key):
        return (
            f"refusing to sign on {network!r} with the public Hardhat dev key.\n"
            "Everyone has that key, so the `submitter` field would prove nothing "
            "and sweeper bots drain the address on sight.\n"
            f"Set PRIVATE_KEY_{network.upper().replace('-', '_')} in .env to a "
            "funded throwaway wallet."
        )
    return None


def deployment_path(network: str) -> Path:
    return OUT / f"deployment_{network}.json"
