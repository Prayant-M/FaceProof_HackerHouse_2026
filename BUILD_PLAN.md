# FaceProof — Build & Execution Plan
### HH Goa 2026 · Shortlisting Task 3 — Face Identification & Blockchain Verification

**Plan date:** 2026-09-04 · **Hard deadline:** 2026-09-07, 23:59 IST
**Working time available:** ~3.5 days

---

## 0. TL;DR — what we are building

**FaceProof** is a CLI forensic pipeline:

```
face scan  →  face embedding  →  genuine web/social search  →  face-verified re-rank
           →  canonical evidence bundle  →  on-chain anchor  →  re-verification + tamper proof
```

It satisfies every stated requirement, then adds four things that separate it from the 200 other
submissions that will just do `face_recognition` + `requests` + `contract.store(hash)`:

| # | Differentiator | Why a judge cares |
|---|---|---|
| 1 | **The search engine is untrusted.** Every candidate a search API returns is re-downloaded, re-detected, re-embedded and cosine-compared against the probe. Only face-verified hits become evidence. | Proves the "match" is real, not a search-engine guess. Directly answers *"this should be a genuine search step."* |
| 2 | **Three-layer fingerprint on-chain**: SHA-256 (exact bytes) + pHash (perceptual) + embedding hash (semantic). | SHA-256 alone breaks the moment a CDN re-encodes the image. pHash survives resize/re-compression. Almost nobody else will do this. |
| 3 | **Merkle-batched anchoring.** N evidence records → one Merkle root → one transaction, with per-record inclusion proofs verified on-chain. | Real blockchain engineering, not a toy setter. Gas is O(1) in record count. |
| 4 | **Live tamper demo.** Flip one character of the caption, re-run `verify`, watch it go red against the immutable on-chain record. | This is the money shot of your screen recording. |

Plus a hard privacy rule that doubles as a talking point:
**no raw biometric data ever touches the chain — only irreversible hashes.**

---

## 1. Requirement → implementation traceability

| Task requirement | How FaceProof satisfies it | Artifact to show in the recording |
|---|---|---|
| Detect + encode a face from an input image | InsightFace `buffalo_l` (RetinaFace detection + ArcFace 512-d embedding) on ONNX Runtime — no compiler needed | Bounding-box overlay + first 8 dims of the L2-normalized embedding |
| Genuine web/social search for a matching post | `SearchProvider` interface; live SerpApi Google Lens / Bing Visual Search / Playwright-driven Google Lens. The result set is *not* hardcoded. | Terminal showing the raw provider JSON + candidate URLs |
| At least one real matching social post | Face-verified re-rank filters candidates to social domains with cosine ≥ threshold | The real post URL, opened in a browser tab |
| Upload post / hash / fingerprint to a blockchain | `FaceEvidenceRegistry.sol` on Base Sepolia (public testnet) **and** a local Anvil/Hardhat node | Transaction hash + BaseScan explorer link |
| Demonstrate re-verifying data against the on-chain record | `faceproof verify` — recomputes hashes, reads the chain, prints EXACT / PERCEPTUAL / TAMPERED | Green ✅, then red ❌ after `tamper-demo` |
| No website required | Pure CLI with a `rich` TUI + an optional local HTML case report | — |
| GitHub repo + README | Repo `faceproof`; README covers what / how to run / which chain / limitations | — |
| Screen recording end to end | 7-minute storyboard in §8 | — |

---

## 2. Architecture

```
                    ┌──────────────────────────────────────────────┐
  probe image  ───► │ STAGE 1  ingest.py                           │
  (or webcam)       │   raw bytes → sha256, pHash, EXIF strip      │
                    └───────────────────┬──────────────────────────┘
                                        ▼
                    ┌──────────────────────────────────────────────┐
                    │ STAGE 2  face.py   (InsightFace buffalo_l)   │
                    │   RetinaFace detect → 5-pt align → ArcFace   │
                    │   → 512-d L2-normalized embedding + quality  │
                    └───────────────────┬──────────────────────────┘
                                        ▼
                    ┌──────────────────────────────────────────────┐
                    │ STAGE 3  search/*.py   PROVIDER CASCADE      │
                    │   SerpApiLens → BingVisual → PlaywrightLens  │
                    │   → LocalCorpus (offline fallback)           │
                    │   returns N candidates {url, image_url, text}│
                    └───────────────────┬──────────────────────────┘
                                        ▼
                    ┌──────────────────────────────────────────────┐
                    │ STAGE 4  rerank.py   ADVERSARIAL VERIFY      │
                    │   per candidate: download image, detect face,│
                    │   embed, cosine vs probe                     │
                    │   keep if cos ≥ 0.40 AND domain ∈ SOCIAL     │
                    └───────────────────┬──────────────────────────┘
                                        ▼
                    ┌──────────────────────────────────────────────┐
                    │ STAGE 5  evidence.py                         │
                    │   canonical JSON (sorted keys, no ws)        │
                    │   evidence_hash = sha256(canonical)          │
                    │   + pHash + embedding_hash                   │
                    │   optional: pin bundle to IPFS → CID         │
                    └───────────────────┬──────────────────────────┘
                                        ▼
                    ┌──────────────────────────────────────────────┐
                    │ STAGE 6  chain.py   (web3.py)                │
                    │   anchor()   single record                   │
                    │   anchorBatch(merkleRoot, n)                 │
                    │   → txHash, blockNumber, gasUsed             │
                    └───────────────────┬──────────────────────────┘
                                        ▼
                    ┌──────────────────────────────────────────────┐
                    │ STAGE 7  verify.py                           │
                    │   recompute → read chain → compare           │
                    │   ✅ EXACT   ⚠️ PERCEPTUAL   ❌ TAMPERED       │
                    └──────────────────────────────────────────────┘
```

### Repo layout

```
faceproof/
├── README.md                      # graded artifact — see §9
├── BUILD_PLAN.md                  # this file
├── LICENSE                        # MIT
├── requirements.txt
├── .env.example
├── run.ps1  /  Makefile           # one-command demo
├── contracts/
│   ├── FaceEvidenceRegistry.sol
│   └── test/registry.test.js      # Hardhat tests (bonus signal)
├── faceproof/
│   ├── __init__.py
│   ├── cli.py                     # typer entrypoint
│   ├── config.py                  # env + thresholds
│   ├── ingest.py
│   ├── face.py
│   ├── rerank.py
│   ├── evidence.py
│   ├── merkle.py
│   ├── chain.py
│   ├── verify.py
│   ├── report.py                  # rich console + HTML case file
│   └── search/
│       ├── base.py                # SearchProvider ABC + Candidate dataclass
│       ├── serpapi_lens.py
│       ├── bing_visual.py
│       ├── playwright_lens.py
│       └── local_corpus.py
├── scripts/
│   ├── deploy.py                  # py-solc-x compile + deploy
│   └── fetch_models.py
├── samples/                       # consenting probe images
├── out/                           # evidence bundles, reports (gitignored)
└── tests/
```

---

## 3. Technology decisions (and why)

### 3.1 Python version — **use 3.11, not 3.14**

Python 3.14.3 is what is installed on this machine. `onnxruntime`, `insightface`, `opencv-python`
and `web3` will not all have prebuilt wheels for 3.14 yet, and you will burn half a day on
compiler errors. Create a 3.11 venv:

```powershell
py -3.11 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -U pip
```

If 3.11 is missing: `winget install Python.Python.3.11`.

### 3.2 Face stack — **InsightFace (buffalo_l)**, not `face_recognition`

| Option | Verdict |
|---|---|
| `face_recognition` / dlib | ❌ Needs CMake + Visual Studio Build Tools on Windows. Hours of pain. 128-d embedding, weaker. |
| **InsightFace + onnxruntime** | ✅ `pip install insightface onnxruntime`. Auto-downloads `buffalo_l`. RetinaFace detection + ArcFace 512-d. State of the art, CPU-fast (~150 ms/face). |
| DeepFace | ⚠️ Pulls TensorFlow (~500 MB). Works, but heavy. |
| AWS Rekognition / Azure Face | ⚠️ Azure Face is gated behind an approval form. Skip it. |

**Threshold.** ArcFace on L2-normalized embeddings — cosine similarity
`≥ 0.40` = same person (conservative), `0.28–0.40` = possible, `< 0.28` = different.
Keep it configurable and **print the number** so the judge sees the decision is quantitative.

### 3.3 Search provider — a cascade, because no single one is reliable

| Provider | Key needed | Notes |
|---|---|---|
| **SerpApi — Google Lens engine** | Yes, free tier ~100/mo | ⭐ Primary. Returns real URLs including Instagram / X / LinkedIn. `engine=google_lens&url=<hosted image>` |
| **Bing Visual Search API** (Azure) | Yes, free F1 tier | Good backup. Accepts a multipart image POST — no image hosting needed. |
| **Playwright → Google Lens** | No | Headless Chromium uploads the crop to lens.google.com and scrapes results. Genuine, zero cost, but brittle. |
| **LocalCorpus** | No | Offline fallback: an index of *real* posts you scraped earlier into `samples/corpus/`. The search runs face-matching over that index. Still a genuine matching step — disclose it in the README. |

> **Image hosting for SerpApi:** it needs a publicly fetchable image URL. Upload the aligned face
> crop at runtime to `tmpfiles.org`, `catbox.moe` or `0x0.st` (one POST, returns a URL). Bing avoids
> this entirely, which is exactly why it is the good backup.

**Ethics / legal — do not skip this.** Use a probe image of **yourself**, or of a **public figure
with an obvious public post**. Put a consent line at the top of the README and an
`--i-have-consent` flag on the CLI. Reverse-image-searching strangers is a GDPR and ToS problem
and a judge may well ask about it. The flag is a feature, not a liability.

### 3.4 Blockchain — **Base Sepolia primary, local Anvil for the guaranteed demo**

| Chain | Verdict |
|---|---|
| **Base Sepolia** | ⭐ Primary. Free faucet (Alchemy / Coinbase / QuickNode), 2 s blocks, BaseScan explorer for a clickable txhash. |
| Sepolia (ETH) | Backup. Faucets are rate-limited and often dry. |
| Polygon Amoy | Backup. Faucet frequently broken. |
| **Anvil (Foundry) or Hardhat node** | ⭐ Always-works local chain. Demo this first so the recording can never fail. |

Show **both** in the recording: local first (guaranteed), then the public testnet txhash with the
explorer open. That combination reads as "this person ships."

**Contract tooling.** Compile and deploy from Python with `py-solc-x`, so the runtime pipeline has
no Node dependency at all. Keep Hardhat purely for the Solidity unit tests — good signal, zero
runtime cost.

### 3.5 Cheap optional wins
- **IPFS pin** of the full evidence bundle (Pinata free tier, or local Kubo) → store the CID
  on-chain beside the hash. The classic "off-chain storage, on-chain anchor" pattern.
- **EIP-191 signature** over the evidence hash by the operator key → proves *who* asserted it.
- **`rich`** console output: panels, spinners, tables. Costs 30 minutes, makes the video look like
  a product instead of a homework assignment.

---

## 4. The smart contract

`contracts/FaceEvidenceRegistry.sol`

```solidity
// SPDX-License-Identifier: MIT
pragma solidity ^0.8.24;

/// @title FaceEvidenceRegistry
/// @notice Tamper-evident anchor for face-identification evidence bundles.
/// @dev Stores ONLY irreversible hashes. No biometric data, no PII, ever.
contract FaceEvidenceRegistry {
    struct Record {
        bytes32 evidenceHash;   // sha256 of the canonical evidence JSON
        bytes32 pHash;          // perceptual hash of the matched post image
        bytes32 embeddingHash;  // sha256 of the quantized ArcFace embedding
        bytes32 merkleRoot;     // 0x0 for single anchors
        uint64  timestamp;      // block time of the FIRST anchor
        uint32  itemCount;      // 1 for single, N for a batch
        address submitter;
        string  cid;            // optional IPFS CID of the full bundle
    }

    Record[] private _records;
    mapping(bytes32 => uint256) private _indexOf;   // evidenceHash => id+1 (0 = absent)
    mapping(bytes32 => uint256) private _rootIndex; // merkleRoot   => id+1

    event EvidenceAnchored(
        uint256 indexed id,
        bytes32 indexed evidenceHash,
        bytes32 indexed merkleRoot,
        address submitter,
        uint64  timestamp
    );

    error AlreadyAnchored(uint256 existingId, uint64 firstSeen);
    error NotFound();

    /// @notice Anchor a single evidence bundle. Reverts if already anchored —
    ///         the FIRST anchor timestamp is the thing with evidentiary value.
    function anchor(
        bytes32 evidenceHash,
        bytes32 pHash,
        bytes32 embeddingHash,
        string calldata cid
    ) external returns (uint256 id) {
        uint256 existing = _indexOf[evidenceHash];
        if (existing != 0) {
            revert AlreadyAnchored(existing - 1, _records[existing - 1].timestamp);
        }
        id = _records.length;
        _records.push(Record({
            evidenceHash:  evidenceHash,
            pHash:         pHash,
            embeddingHash: embeddingHash,
            merkleRoot:    bytes32(0),
            timestamp:     uint64(block.timestamp),
            itemCount:     1,
            submitter:     msg.sender,
            cid:           cid
        }));
        _indexOf[evidenceHash] = id + 1;
        emit EvidenceAnchored(id, evidenceHash, bytes32(0), msg.sender, uint64(block.timestamp));
    }

    /// @notice Anchor N bundles in one transaction via a Merkle root.
    function anchorBatch(bytes32 merkleRoot, uint32 itemCount, string calldata cid)
        external
        returns (uint256 id)
    {
        uint256 existing = _rootIndex[merkleRoot];
        if (existing != 0) {
            revert AlreadyAnchored(existing - 1, _records[existing - 1].timestamp);
        }
        id = _records.length;
        _records.push(Record({
            evidenceHash:  bytes32(0),
            pHash:         bytes32(0),
            embeddingHash: bytes32(0),
            merkleRoot:    merkleRoot,
            timestamp:     uint64(block.timestamp),
            itemCount:     itemCount,
            submitter:     msg.sender,
            cid:           cid
        }));
        _rootIndex[merkleRoot] = id + 1;
        emit EvidenceAnchored(id, bytes32(0), merkleRoot, msg.sender, uint64(block.timestamp));
    }

    function verify(bytes32 evidenceHash) external view returns (bool found, Record memory r) {
        uint256 i = _indexOf[evidenceHash];
        if (i == 0) return (false, r);
        return (true, _records[i - 1]);
    }

    /// @notice Verify a leaf belongs to an anchored Merkle root. Sorted-pair proof.
    function verifyInclusion(bytes32 root, bytes32 leaf, bytes32[] calldata proof)
        external
        view
        returns (bool)
    {
        if (_rootIndex[root] == 0) return false;
        bytes32 h = leaf;
        for (uint256 i = 0; i < proof.length; ++i) {
            bytes32 p = proof[i];
            h = h <= p ? keccak256(abi.encodePacked(h, p))
                       : keccak256(abi.encodePacked(p, h));
        }
        return h == root;
    }

    function recordCount() external view returns (uint256) { return _records.length; }

    function recordAt(uint256 id) external view returns (Record memory) {
        if (id >= _records.length) revert NotFound();
        return _records[id];
    }
}
```

**Design points worth saying out loud in the video:**
- Re-anchoring reverts with `AlreadyAnchored(id, firstSeen)`. The first-seen timestamp *is* the
  evidentiary claim; letting someone overwrite it would destroy the entire point of the system.
- Merkle leaves use **sorted-pair hashing**, so a proof needs no left/right position bits.
- `pHash` and `embeddingHash` sit next to `evidenceHash` so a re-encoded copy of the same post can
  still be tied to the record even when the exact bytes have changed.

---

## 5. Key implementation snippets

### 5.1 Face encoding — `faceproof/face.py`

```python
import numpy as np, cv2, hashlib
from insightface.app import FaceAnalysis

_app = None

def _get_app():
    global _app
    if _app is None:
        _app = FaceAnalysis(name="buffalo_l", providers=["CPUExecutionProvider"])
        _app.prepare(ctx_id=-1, det_size=(640, 640))
    return _app

def encode(image_path: str):
    """Return the highest-quality face: bbox, det score, L2-normalized 512-d embedding."""
    img = cv2.imread(image_path)
    if img is None:
        raise ValueError(f"unreadable image: {image_path}")
    faces = _get_app().get(img)
    if not faces:
        raise ValueError("no face detected")
    f = max(faces, key=lambda x: (x.bbox[2] - x.bbox[0]) * (x.bbox[3] - x.bbox[1]))
    emb = np.asarray(f.normed_embedding, dtype=np.float32)   # already L2-normalized
    return {
        "bbox": [float(v) for v in f.bbox],
        "det_score": float(f.det_score),
        "embedding": emb,
        "embedding_hash": embedding_hash(emb),
    }

def embedding_hash(emb: np.ndarray) -> str:
    """Quantize to int8 before hashing so float jitter does not change the digest."""
    q = np.round(emb * 127).astype(np.int8)
    return hashlib.sha256(q.tobytes()).hexdigest()

def cosine(a: np.ndarray, b: np.ndarray) -> float:
    return float(np.dot(a, b))   # both are unit vectors
```

### 5.2 Search provider interface — `faceproof/search/base.py`

```python
from abc import ABC, abstractmethod
from dataclasses import dataclass, field

SOCIAL_DOMAINS = {
    "instagram.com", "x.com", "twitter.com", "linkedin.com", "facebook.com",
    "reddit.com", "threads.net", "mastodon.social", "github.com", "youtube.com",
    "tiktok.com", "pinterest.com", "flickr.com",
}

@dataclass
class Candidate:
    page_url: str
    image_url: str
    title: str = ""
    snippet: str = ""
    provider: str = ""
    raw: dict = field(default_factory=dict)

class SearchProvider(ABC):
    name: str

    @abstractmethod
    def available(self) -> bool: ...

    @abstractmethod
    def search(self, image_path: str, limit: int = 20) -> list[Candidate]: ...
```

### 5.3 SerpApi Google Lens provider — `faceproof/search/serpapi_lens.py`

```python
import os, requests
from .base import SearchProvider, Candidate

class SerpApiLens(SearchProvider):
    name = "serpapi_google_lens"

    def available(self) -> bool:
        return bool(os.getenv("SERPAPI_KEY"))

    def search(self, image_path, limit=20):
        public_url = _host_temporarily(image_path)
        r = requests.get("https://serpapi.com/search", params={
            "engine":  "google_lens",
            "url":     public_url,
            "api_key": os.environ["SERPAPI_KEY"],
        }, timeout=60)
        r.raise_for_status()
        data = r.json()
        return [
            Candidate(
                page_url=m.get("link", ""),
                image_url=m.get("thumbnail") or m.get("image", ""),
                title=m.get("title", ""),
                snippet=m.get("source", ""),
                provider=self.name,
                raw=m,
            )
            for m in (data.get("visual_matches") or [])[:limit]
        ]

def _host_temporarily(path: str) -> str:
    """Upload to a throwaway host so Lens can fetch it. Returns a public URL."""
    with open(path, "rb") as fh:
        r = requests.post("https://tmpfiles.org/api/v1/upload",
                          files={"file": fh}, timeout=60)
    r.raise_for_status()
    return r.json()["data"]["url"].replace("tmpfiles.org/", "tmpfiles.org/dl/")
```

### 5.4 Adversarial re-rank — `faceproof/rerank.py` *(the differentiator)*

```python
import os, tempfile, requests
from urllib.parse import urlparse
from .face import encode, cosine
from .search.base import SOCIAL_DOMAINS

def rerank(probe_emb, candidates, threshold: float = 0.40, social_only: bool = True):
    """Do NOT trust the search engine. Re-download, re-detect, re-embed, compare."""
    scored = []
    for c in candidates:
        host = urlparse(c.page_url).netloc.lower().removeprefix("www.")
        is_social = any(host == d or host.endswith("." + d) for d in SOCIAL_DOMAINS)
        if social_only and not is_social:
            scored.append((c, None, "skip: not a social domain"))
            continue
        try:
            blob = requests.get(c.image_url, timeout=30,
                                headers={"User-Agent": "Mozilla/5.0 FaceProof/1.0"}).content
            with tempfile.NamedTemporaryFile(suffix=".jpg", delete=False) as tf:
                tf.write(blob)
                tmp = tf.name
            enc = encode(tmp)
            os.unlink(tmp)
        except Exception as e:
            scored.append((c, None, f"skip: {e}"))
            continue
        scored.append((c, cosine(probe_emb, enc["embedding"]), "ok"))

    hits = [(c, s) for c, s, _ in scored if s is not None and s >= threshold]
    hits.sort(key=lambda t: -t[1])
    return hits, scored          # `scored` is retained as the audit trail
```

### 5.5 Canonical evidence + hashing — `faceproof/evidence.py`

```python
import json, hashlib, datetime

PIPELINE_VERSION = "faceproof/1.0.0"

def canonical(obj) -> bytes:
    """Deterministic serialization: sorted keys, no whitespace, UTF-8, no NaN."""
    return json.dumps(obj, sort_keys=True, separators=(",", ":"),
                      ensure_ascii=False, allow_nan=False).encode("utf-8")

def build_bundle(probe, match, similarity, provider, audit) -> dict:
    return {
        "version": PIPELINE_VERSION,
        "created_at": datetime.datetime.now(datetime.UTC).isoformat(timespec="seconds"),
        "probe": {
            "sha256":         probe["sha256"],
            "phash":          probe["phash"],
            "embedding_hash": probe["embedding_hash"],
            "det_score":      round(probe["det_score"], 4),
        },
        "match": {
            "page_url":       match["page_url"],
            "image_url":      match["image_url"],
            "platform":       match["platform"],
            "title":          match["title"],
            "image_sha256":   match["image_sha256"],
            "image_phash":    match["image_phash"],
            "embedding_hash": match["embedding_hash"],
            "retrieved_at":   match["retrieved_at"],
            "http_status":    match["http_status"],
            "content_length": match["content_length"],
        },
        "similarity": round(similarity, 6),
        "search": {"provider": provider, "candidates_examined": len(audit)},
    }

def evidence_hash(bundle: dict) -> str:
    return hashlib.sha256(canonical(bundle)).hexdigest()
```

> **Why canonicalization matters:** with default `json.dumps`, key order and whitespace drift
> between runs and your hash will not reproduce. Sorted keys + tight separators make `verify`
> deterministic across machines. Say this in the video — it shows rigor.

### 5.6 Merkle tree — `faceproof/merkle.py`

```python
from eth_utils import keccak

def _pair(a: bytes, b: bytes) -> bytes:
    return keccak(a + b) if a <= b else keccak(b + a)   # sorted-pair, matches the contract

def build(leaves: list[bytes]):
    if not leaves:
        raise ValueError("no leaves")
    levels = [list(leaves)]
    while len(levels[-1]) > 1:
        cur = levels[-1]
        levels.append([
            _pair(cur[i], cur[i + 1]) if i + 1 < len(cur) else cur[i]
            for i in range(0, len(cur), 2)
        ])
    return levels[-1][0], levels

def proof(levels, index: int) -> list[bytes]:
    out = []
    for lvl in levels[:-1]:
        sib = index ^ 1
        if sib < len(lvl):
            out.append(lvl[sib])
        index //= 2
    return out
```

### 5.7 Chain client — `faceproof/chain.py`

```python
import os
from web3 import Web3
from web3.middleware import ExtraDataToPOAMiddleware

CHAINS = {
    "local":        {"rpc": "http://127.0.0.1:8545",           "explorer": None},
    "base-sepolia": {"rpc": os.getenv("BASE_SEPOLIA_RPC", ""), "explorer": "https://sepolia.basescan.org/tx/"},
    "sepolia":      {"rpc": os.getenv("SEPOLIA_RPC", ""),      "explorer": "https://sepolia.etherscan.io/tx/"},
}

class Chain:
    def __init__(self, network: str, address: str, abi: list):
        cfg = CHAINS[network]
        self.w3 = Web3(Web3.HTTPProvider(cfg["rpc"]))
        self.w3.middleware_onion.inject(ExtraDataToPOAMiddleware, layer=0)
        self.explorer = cfg["explorer"]
        self.acct = self.w3.eth.account.from_key(os.environ["PRIVATE_KEY"])
        self.c = self.w3.eth.contract(address=Web3.to_checksum_address(address), abi=abi)

    def _send(self, fn):
        tx = fn.build_transaction({
            "from":    self.acct.address,
            "nonce":   self.w3.eth.get_transaction_count(self.acct.address),
            "chainId": self.w3.eth.chain_id,
        })
        tx["gas"] = int(self.w3.eth.estimate_gas(tx) * 1.2)
        signed = self.acct.sign_transaction(tx)
        h = self.w3.eth.send_raw_transaction(signed.raw_transaction)
        rcpt = self.w3.eth.wait_for_transaction_receipt(h, timeout=180)
        tx_hash = rcpt.transactionHash.hex()
        return {
            "tx_hash":  tx_hash,
            "block":    rcpt.blockNumber,
            "gas_used": rcpt.gasUsed,
            "explorer": (self.explorer + tx_hash) if self.explorer else None,
        }

    def anchor(self, ev_hash_hex, phash_hex, emb_hash_hex, cid=""):
        return self._send(self.c.functions.anchor(
            bytes.fromhex(ev_hash_hex), bytes.fromhex(phash_hex),
            bytes.fromhex(emb_hash_hex), cid))

    def verify(self, ev_hash_hex):
        found, rec = self.c.functions.verify(bytes.fromhex(ev_hash_hex)).call()
        return found, rec
```

### 5.8 Verification verdicts — `faceproof/verify.py`

```python
EXACT, PERCEPTUAL, TAMPERED, UNANCHORED = "EXACT", "PERCEPTUAL", "TAMPERED", "UNANCHORED"

def classify(local_bundle, chain_record, live=None):
    """
    EXACT      — recomputed evidence hash equals the on-chain hash. Bytes are identical.
    PERCEPTUAL — hash differs, but pHash hamming <= 8 and embedding cosine >= 0.90.
                 Same content, re-encoded (CDN re-compression, resize).
    TAMPERED   — anchored, but neither the hash nor the fingerprints line up.
    UNANCHORED — nothing on chain for this hash.
    """
    if chain_record is None:
        return UNANCHORED
    if local_bundle["evidence_hash"] == chain_record["evidenceHash"]:
        return EXACT
    if live and live["phash_hamming"] <= 8 and live["embedding_cosine"] >= 0.90:
        return PERCEPTUAL
    return TAMPERED
```

---

## 6. CLI surface

```
faceproof scan         --image samples/me.jpg [--webcam]
faceproof search       --scan out/scan_<id>.json [--provider serpapi|bing|playwright|local]
faceproof anchor       --evidence out/ev_<id>.json --chain local|base-sepolia [--ipfs]
faceproof verify       --evidence out/ev_<id>.json --chain base-sepolia [--live-refetch]
faceproof batch-anchor --evidence "out/ev_*.json" --chain base-sepolia    # Merkle mode
faceproof tamper-demo  --evidence out/ev_<id>.json --chain base-sepolia
faceproof run          --image samples/me.jpg --chain base-sepolia --i-have-consent
faceproof report       --evidence out/ev_<id>.json --html out/case_<id>.html
```

`run` is the single command for the recording: scan → search → rerank → evidence → anchor → verify,
with a live `rich` progress panel per stage.

---

## 7. Day-by-day schedule (Sept 4 → Sept 7)

### Day 1 — Thursday Sept 4 (today): foundation
- [ ] `py -3.11` venv; `pip install insightface onnxruntime opencv-python-headless imagehash pillow requests web3 py-solc-x rich python-dotenv eth-utils typer`
- [ ] `git init`; push an empty `faceproof` repo to GitHub; MIT license; `.gitignore` (`.env`, `out/`, `.venv/`, `models/`)
- [ ] `ingest.py` + `face.py` working — `faceproof scan --image samples/me.jpg` prints bbox + embedding hash
- [ ] Write `FaceEvidenceRegistry.sol`; compile with py-solc-x; deploy to a local Anvil/Hardhat node; `anchor` + `verify` round-trip in a Python REPL
- **Checkpoint:** face in, hash on a local chain, verified back out.

### Day 2 — Friday Sept 5: the genuine search
- [ ] Sign up for SerpApi (free tier) and Azure Bing Visual Search (F1). Keys into `.env`
- [ ] `search/base.py`, `serpapi_lens.py`, `bing_visual.py`, `local_corpus.py`
- [ ] `rerank.py` — download, re-embed, cosine. Tune the threshold on 3–5 probe images
- [ ] Confirm you get **at least one real social-media hit** for your chosen probe. *If your own face returns nothing, switch to a public figure — decide this today, not on Sunday night.*
- [ ] `evidence.py` + canonical JSON + `evidence_hash`
- **Checkpoint:** `scan → search → evidence bundle` yields a real post URL.

### Day 3 — Saturday Sept 6: chain + polish
- [ ] Base Sepolia faucet; deploy the contract; save the address into `.env`
- [ ] `chain.py` anchor/verify against Base Sepolia; capture a real txhash
- [ ] `merkle.py` + `anchorBatch` + `verifyInclusion` end to end
- [ ] `verify.py` three-verdict logic + `tamper-demo`
- [ ] `report.py` rich console + HTML case file
- [ ] Hardhat Solidity tests (`npx hardhat test`) — 6–8 assertions
- **Checkpoint:** a full `faceproof run` succeeds twice in a row from a clean shell.

### Day 4 — Sunday Sept 7: freeze, record, submit
- [ ] **10:00** — Write the README (§9). It is graded. Give it two full hours.
- [ ] **13:00** — Clean-clone test: `git clone` into a fresh folder, fresh venv, follow your own README verbatim. Fix whatever breaks. *This step catches more bugs than anything else you will do.*
- [ ] **15:00** — Record the screen (§8). Two takes, keep the better one.
- [ ] **17:00** — Upload to YouTube unlisted (or Drive with link-sharing **on** — verify in an incognito window)
- [ ] **19:00** — Final push, tag `v1.0.0`, submit the form
- [ ] Do **not** submit at 23:50. There are no resubmissions.

**Cut list if you fall behind** (drop in this order):
IPFS pin → HTML report → Merkle batch → Bing provider → Base Sepolia (fall back to local-chain only, and say so honestly in the README).
**Never cut:** the adversarial re-rank, or the tamper demo. Those are what make it memorable.

---

## 8. Screen recording storyboard (~7 min)

Record at 1080p with OBS. Terminal font size 16+. **Talk while you do it** — voiceover matters far
more than editing.

| Time | Screen | Say |
|---|---|---|
| 0:00–0:30 | README title + architecture diagram | "FaceProof. Face scan in, a real social post out, anchored on Base Sepolia, and I can prove the record was not altered." |
| 0:30–1:15 | `faceproof scan --image samples/me.jpg` → bbox overlay + embedding hash | "RetinaFace detection, ArcFace 512-dimension embedding. Note that I hash the embedding — the raw biometric vector never leaves this machine and never touches the chain." |
| 1:15–2:45 | `faceproof search --provider serpapi` — show the **raw JSON response** scrolling | "This is a live SerpApi Google Lens call, happening right now. Nothing is hardcoded — here is the raw provider payload." |
| 2:45–3:45 | Re-rank table: every candidate with its cosine score, rejects greyed, the hit in green | "I do not trust the search engine. Every candidate is re-downloaded, the face re-detected and re-embedded, and compared to the probe. This one scores 0.71 — above my 0.40 threshold. The rest are rejected." |
| 3:45–4:10 | Open the matched post URL in a browser | "That is a real, live post." |
| 4:10–5:10 | `faceproof anchor --chain base-sepolia` → txhash → **open BaseScan** | "SHA-256 of the canonical evidence bundle, plus a perceptual hash and the embedding hash, anchored in one transaction. Here it is on BaseScan — block 12,345,678, 94,000 gas." |
| 5:10–5:50 | `faceproof verify` → big green ✅ EXACT | "Recompute locally, read the chain, compare. Exact match." |
| 5:50–6:40 | `faceproof tamper-demo` — show the single character it changes, then ❌ TAMPERED | "I change one character of the caption. Re-verify. Red. The chain does not care how small the edit was." |
| 6:40–7:00 | `faceproof batch-anchor` — 5 bundles, one Merkle root, one tx, then a per-record inclusion proof verified on-chain | "And a Merkle mode: five records, one transaction, each individually provable." |

**Recording rules:** clear the terminal between stages · pre-download the InsightFace models (the
first run pulls ~300 MB and will stall your video) · have the BaseScan tab pre-opened · have a
second terminal already running the local Anvil node.

---

## 9. README skeleton (graded — do not rush it)

```markdown
# FaceProof
Face scan → genuine web/social search → blockchain-anchored, tamper-evident evidence.

[demo gif]  [screen recording link]  [contract on BaseScan]

## What it does
1. Detects and encodes a face (InsightFace / ArcFace, 512-d).
2. Searches the live web for that face (SerpApi Google Lens · Bing Visual Search · Playwright).
3. Re-verifies every candidate by re-embedding its image — the search engine is untrusted.
4. Builds a canonical evidence bundle and anchors SHA-256 + pHash + embedding-hash on chain.
5. Re-verifies against the on-chain record and detects tampering.

## Quickstart
(exact copy-pasteable commands, tested from a clean clone)

## Which blockchain
Base Sepolia (chain id 84532). Contract: `0x...` — [BaseScan](...)
Also runs fully offline against a local Anvil/Hardhat node (`--chain local`).
Why Base Sepolia: free faucet, 2-second blocks, public explorer for independent verification.

## Privacy design
No biometric data is ever written on chain. Embeddings are quantized to int8 and SHA-256'd; the
digest is irreversible. The chain holds only hashes, a timestamp and a submitter address.

## Ethics & consent
Probe images are of the author, or of public figures with public posts. The CLI requires
`--i-have-consent`. Do not run this against strangers.

## Architecture
(the ASCII diagram from §2)

## Known limitations
- Reverse image search is optimized for *images*, not *faces*. Recall is best for people with a
  large public image footprint; a private individual may return zero hits.
- The SerpApi free tier is ~100 searches/month; the Playwright provider is a scraper and breaks
  whenever Google changes its DOM.
- ArcFace has documented demographic accuracy disparities. A 0.40 cosine threshold is a tuned
  heuristic, not a legal identification standard.
- Anchoring proves *when a claim was recorded*, not that the claim is true. FaceProof provides
  integrity and timestamping, not ground truth.
- The matched post can be deleted or edited by its author; FaceProof preserves the fingerprint,
  not the content (unless the IPFS pin is enabled).
- Gas is trivial on a testnet; at mainnet scale, Merkle batching would be mandatory.

## Tests
`pytest` for the Python pipeline · `npx hardhat test` for the contract.
```

---

## 10. Failure modes to pre-empt

| Risk | Mitigation |
|---|---|
| Search returns **zero** social hits for your face | Decide the probe subject on **Day 2**, not Day 4. Keep a public-figure fallback ready. `LocalCorpus` is the last resort — disclose it. |
| InsightFace model download stalls mid-demo | `scripts/fetch_models.py`, run once before recording. |
| Faucet dry / testnet down on Sunday | The local-chain path must work standalone. Record local first. |
| `pip install` fails on Python 3.14 | Use the 3.11 venv. Non-negotiable. |
| Hash does not reproduce between runs | Canonical JSON (sorted keys, tight separators) + int8-quantized embedding before hashing. |
| Instagram / X block the image download during re-rank | Set a browser `User-Agent`; fall back to the provider's own thumbnail URL, and record in the bundle **which** URL you actually hashed. |
| Private key leaks into the repo | `.env` in `.gitignore` from commit #1. Use a **throwaway** wallet holding testnet funds only. Add a pre-commit grep for `0x[0-9a-f]{64}`. |
| Judge asks "is this actually a real search?" | The raw provider JSON is saved into the audit trail of every bundle. Show it. |

---

## 11. Definition of done

- [ ] `git clone` → follow the README → `faceproof run` works on a machine that never built it
- [ ] A real social post URL appears in the output, produced by a live search call
- [ ] A Base Sepolia transaction hash resolves on BaseScan
- [ ] `verify` prints ✅ and `tamper-demo` prints ❌ within the same recording
- [ ] README covers what / how to run / which chain / limitations
- [ ] `.env` is absent from the repo history
- [ ] Recording uploaded, and the link opens in an incognito window
- [ ] Form submitted before Sept 7, 23:59
