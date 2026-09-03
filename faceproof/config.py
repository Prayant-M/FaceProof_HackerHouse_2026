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


def deployment_path(network: str) -> Path:
    return OUT / f"deployment_{network}.json"
