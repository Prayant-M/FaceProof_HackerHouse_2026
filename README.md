# FaceProof

**Face scan → genuine web/social search → blockchain-anchored, tamper-evident evidence.**

A command-line forensic pipeline built for **HH Goa 2026 — Shortlisting Task 3**.
It takes a face image, searches the live web for that face, verifies every candidate
by re-embedding it locally, and anchors a canonical evidence bundle on a public
blockchain so the record can be re-verified — and tampering detected — later.

```
 face scan ──► ArcFace embedding ──► live reverse image search ──► adversarial re-rank
           ──► canonical evidence bundle ──► on-chain anchor ──► re-verification
```

| | |
|---|---|
| **Blockchain** | **Live on Ethereum Sepolia (chain id 11155111)** · Base Sepolia (84532) supported · also runs fully offline on a local Anvil/Hardhat node |
| **Contract** | `contracts/FaceEvidenceRegistry.sol` — [`0xcEcede3653BEf3942F8B7a6c37F7BFc10f7081b7`](https://sepolia.etherscan.io/address/0xcEcede3653BEf3942F8B7a6c37F7BFc10f7081b7) on Sepolia; address + ABI in `out/deployment_<chain>.json` |
| **Face model** | InsightFace `buffalo_l` — RetinaFace detection + ArcFace 512-d embedding |
| **Search** | SerpApi Google Lens · SerpApi Yandex Images · headless Playwright Lens · offline corpus |
| **Website** | None. The task does not require one; the CLI *is* the product. |

### Verify it yourself, without running anything

The registry is deployed on a public testnet, so the integrity claim is checkable by a
stranger with a browser:

1. Open [the contract on Etherscan](https://sepolia.etherscan.io/address/0xcEcede3653BEf3942F8B7a6c37F7BFc10f7081b7)
2. **Contract → Read Contract**
3. Call `recordCount()` to see how many records exist, `recordAt(i)` to read one, or paste
   an `evidenceHash` into `verify(bytes32)` to fetch that record

No wallet, no clone, no access to the author's machine. Deploy transaction:
[`0xcdcd8e2e…4c062a`](https://sepolia.etherscan.io/tx/0xcdcd8e2e0e8fc4c953f7a5559fd1573d80c09bcfd96514950f31467ffc4c062a).

---

## What makes this different

Most implementations of this task are three calls in a row: detect a face, hit a
reverse image API, write `sha256(result)` to a contract. FaceProof does four things
that design does not.

**1. The search engine is not trusted.**
A reverse image search answers *"what looks similar to this?"* — which is not the same
claim as *"this is the same person."* So every candidate a provider returns is
re-downloaded, the face re-detected, re-embedded with ArcFace, and compared to the probe
by cosine similarity. Only candidates that clear the threshold (default `0.40`) can
become evidence. The full decision — every accepted, rejected, and unfetchable candidate
with its score — is written into the audit trail.

**2. Three independent fingerprints go on chain, not one.**

| Fingerprint | Survives | Catches |
|---|---|---|
| `sha256` | nothing | any byte change |
| `pHash` (perceptual) | resize, re-compression, format change | visual edits |
| embedding hash (semantic) | re-encoding | a different face entirely |

A SHA-256-only design reports "TAMPERED" every time a CDN re-compresses a thumbnail,
which makes it useless in the field. FaceProof can tell *"someone edited this"* apart
from *"Instagram re-encoded this."*

**3. Merkle-batched anchoring.**
`anchorBatch` puts N evidence records on chain in **one** transaction via a Merkle root,
and `verifyInclusion` proves any individual record's membership on chain afterwards. Gas
is O(1) in record count. Python and Solidity use identical sorted-pair hashing, so proofs
built locally verify on chain with no translation.

**4. Privacy is enforced, not promised.**
The raw 512-d face embedding is biometric data. It never leaves the local machine and
never touches the chain. It is quantized to int8 and SHA-256'd first; only that
irreversible digest is published. `tests/test_evidence.py` asserts the property.

---

## Quickstart

### Requirements

- **Python 3.11 or 3.12** — *not 3.13 or 3.14.* `onnxruntime` publishes no cp313/cp314
  wheels, and `insightface` ships source-only, so pip falls back to compiling. On Windows
  that also means Microsoft C++ Build Tools. This build runs on 3.12.
- Node 18+ — only for the local test chain and the Solidity tests. The pipeline itself
  has no Node dependency.
- A SerpApi key (free tier, ~100 searches/month) for the live search path.
- A throwaway wallet with testnet ETH on whichever public chain you target (free — see
  [SETUP.md §5](SETUP.md#5-testnet--faucets-rpc-explorer)).

### 1. Install

```powershell
git clone https://github.com/<you>/faceproof
cd faceproof
.\setup.ps1          # venv + deps + model download + .env
```

<details>
<summary>Linux / macOS / manual</summary>

```bash
python3.12 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
python scripts/fetch_models.py     # pre-download ~300 MB of models
cp .env.example .env
```
</details>

### 2. Configure

Edit `.env`:

```ini
SERPAPI_KEY=your_key_here

# per-network keys; PRIVATE_KEY is the shared fallback, the local chain needs neither
PRIVATE_KEY_SEPOLIA=0xyour_throwaway_testnet_key
SEPOLIA_RPC=https://ethereum-sepolia-rpc.publicnode.com
BASE_SEPOLIA_RPC=https://sepolia.base.org
DEFAULT_CHAIN=local
```

> `.env` is gitignored. Use a wallet that holds testnet funds and nothing else.
> `--chain local` needs no key at all — it falls back to the Hardhat dev account, which is
> **refused** on any public network because everyone has it.

### 3. Deploy the contract

**Local chain** (always works, no faucet):

```bash
npx hardhat node                       # terminal 1
python scripts/deploy.py --chain local # terminal 2
```

**Public testnet** (has an explorer, so anyone can verify):

```bash
python -m faceproof info                  # prints the address that needs funding
# paste that ADDRESS (never the key) into a faucet, wait ~1 min:
#   Ethereum Sepolia -> https://cloud.google.com/application/web3/faucet/ethereum/sepolia
#   Base Sepolia     -> https://portal.cdp.coinbase.com/products/faucet
python scripts/deploy.py --chain sepolia   # or --chain base-sepolia
```

Testnet ETH is free and worthless — it only pays gas. Deploying costs ~0.0002 ETH.
Note that a balance is **per chain**: funding Ethereum Sepolia does nothing for Base
Sepolia, even though the address is identical.

### 4. Run the pipeline

```bash
python -m faceproof run \
    --image samples/me.jpg \
    --chain sepolia \
    --i-have-consent \
    --html
```

Or stage by stage — this is what the demo recording does:

```bash
python -m faceproof info
python -m faceproof scan   --image samples/me.jpg
python -m faceproof search --scan <scan_id>
python -m faceproof anchor --evidence <scan_id> --chain sepolia
python -m faceproof verify --evidence <scan_id> --chain sepolia
python -m faceproof tamper-demo --evidence <scan_id> --chain sepolia
```

`.\demo.ps1 -Image samples\me.jpg -Chain sepolia` drives that whole sequence with a pause
between stages. Swap `sepolia` for `local` to rehearse for free.
[SCRIPT.md](SCRIPT.md) is the shot-by-shot recording script.

### What a run produces

| Where | What |
|---|---|
| `out/scan_<id>/` | `original.jpg` (EXIF intact — chain of custody) · `clean.jpg` (EXIF stripped) · `probe_crop.jpg` (the only file that leaves the machine) · `annotated.jpg` · `embedding.npy` — **raw biometric vector, local only** |
| `out/scan_<id>.json` | hashes, bbox, det score, embedding hash, timestamps |
| `out/ev_<id>.json` | canonical evidence bundle + `evidence_hash` + full audit trail; the `anchor` receipt is filled in after stage 6 |
| `out/case_<id>.html` | case report, with `--html` |
| on chain | one `anchor()` tx — `evidenceHash`, `pHash`, `embeddingHash`, block timestamp, submitter, optional CID. **Digests only** |

Nothing outside `out/` and the chain is written. Full breakdown, including what leaves the
machine and what it costs: [SETUP.md §7](SETUP.md#7-running-the-pipeline).

---

## Command reference

| Command | Does |
|---|---|
| `info` | Which providers are available, which chains are deployed, current thresholds |
| `scan --image X` | Stages 1–2: ingest, hash, detect, encode. Writes an annotated overlay and a search crop |
| `search --scan ID` | Stages 3–5: live search, adversarial re-rank, evidence bundle |
| `anchor --evidence ID --chain C` | Stage 6: write the record on chain |
| `verify --evidence ID --chain C` | Stage 7: recompute, read chain, classify. `--live-refetch` re-downloads the post |
| `batch-anchor --evidence "out/ev_*.json"` | Merkle-batch many bundles into one transaction |
| `tamper-demo --evidence ID` | Flip one character, prove the chain rejects it |
| `report --evidence ID` | Write a self-contained HTML case report |

Useful flags: `--provider serpapi|yandex|playwright|local`, `--threshold 0.35`,
`--any-domain` (drop the social-platform filter), `--limit 40`.

---

## How it works, stage by stage

**1 · Ingest** (`ingest.py`) — SHA-256 of the *original* bytes, perceptual hash, and an
EXIF-stripped working copy. EXIF can carry GPS and device serials; the digest is taken
before stripping so chain of custody survives.

**2 · Face** (`face.py`) — RetinaFace finds faces, the largest is 5-point aligned, ArcFace
produces a 512-d L2-normalized embedding. A context-padded crop (60% margin) is written for
search — a tight 112×112 face chip performs badly in reverse image search because engines
match whole-scene features too.

**3 · Search** (`search/`) — providers are tried in cascade until one returns results:

| Provider | Key | Notes |
|---|---|---|
| `serpapi` (Google Lens) | `SERPAPI_KEY` | Best social coverage. Primary. |
| `yandex` (via SerpApi) | `SERPAPI_KEY` | Better *face* recall than Lens, which is tuned for objects. |
| `playwright` | none | Drives headless Chromium against lens.google.com. Free, genuine, and brittle. |
| `local` | none | Offline index of real posts under `samples/corpus/`. Discovery is local — disclose it. |

SerpApi needs a fetchable URL, so the crop is pushed to a throwaway host
(`tmpfiles.org`, falling back to `catbox.moe`) for the duration of the query. The URL used
is recorded in the audit trail.

**4 · Re-rank** (`rerank.py`) — the adversarial step described above.

**5 · Evidence** (`evidence.py`) — canonical JSON: sorted keys, no whitespace, UTF-8, no
NaN. Without canonicalization the digest would drift between runs and `verify` would fail
spuriously. Volatile data (the audit trail, the anchor receipt) lives *outside* the hashed
region, so recording the transaction does not invalidate the hash it recorded.

**6 · Anchor** (`chain.py`) — `anchor(evidenceHash, pHash, embeddingHash, cid)`. Re-anchoring
the same hash **reverts** with `AlreadyAnchored(id, firstSeen)`: the first-seen timestamp is
the entire evidentiary claim, and allowing an overwrite would defeat the registry.

**7 · Verify** (`verify.py`) — four verdicts:

| Verdict | Meaning |
|---|---|
| ✅ `EXACT` | Recomputed hash equals the on-chain hash, byte for byte |
| ⚠️ `PERCEPTUAL` | Hash differs, but pHash hamming ≤ 8 **and** face cosine ≥ 0.90 — a re-encode, not an edit |
| ❌ `TAMPERED` | Anchored, but neither the hash nor the fingerprints line up |
| `UNANCHORED` | Nothing on chain for this hash |

---

## Which blockchain, and why

Three networks, one code path — only the RPC URL and the explorer prefix differ.

| `--chain` | Chain id | Blocks | Cost | Use it for |
|---|---|---|---|---|
| `local` | 31337 | instant | free | all development and rehearsal |
| `sepolia` | 11155111 | ~12 s | faucet ETH | **the live public record** |
| `base-sepolia` | 84532 | ~2 s | faucet ETH | faster public demo, if you can fund it |

**Ethereum Sepolia holds the live deployment.** Base Sepolia has nicer 2-second blocks,
but in practice its faucets (Alchemy, QuickNode) gate on holding real mainnet ETH, while
the Google Cloud Sepolia faucet needs only a Google account. Base Sepolia stays fully
supported — `deploy.py --chain base-sepolia` — for anyone who can get funds there.

A **local Anvil/Hardhat node** (`--chain local`) runs the identical code path with no
faucet, no network, and no cost. Develop there; spend faucet ETH only on the take you
actually record.

Only hashes are stored. A record is 4 × `bytes32` + a timestamp + a count + an address +
an optional IPFS CID string.

---

## Tests

```bash
python -m pytest        # canonicalization, Merkle, verdict logic, privacy invariant
npx hardhat test        # Solidity: anchoring, revert-on-overwrite, Merkle inclusion
```

`tests/test_evidence.py::test_bundle_contains_no_raw_biometric_data` is the one that
guards the privacy claim — if someone adds the raw embedding to the bundle, it fails.

---

## Ethics and consent

FaceProof searches the open web for a person's face. That is a capability with obvious
misuse potential, so:

- `faceproof run` **refuses to start** without `--i-have-consent`.
- Use it on your own face, on a subject who has agreed, or on a public figure's already-public
  posts. Not on strangers.
- Probe images and the local corpus are gitignored. Do not commit photographs of people.
- Nothing biometric is published. Only irreversible digests reach the chain.

This is a hackathon build, not a forensic product, and it is not appropriate for
surveillance, doxxing, or any identification with consequences for the person identified.

---

## Known limitations

- **Reverse image search is tuned for images, not faces.** Recall depends heavily on the
  subject's public image footprint. A private individual with no public photos will
  correctly return zero hits — that is the pipeline working, not failing. Test your probe
  subject early.
- **API quotas.** SerpApi's free tier is roughly 100 searches per month, and each cascade
  attempt spends one. The Playwright provider is a scraper and will break whenever Google
  changes the Lens DOM.
- **The `local` provider is not web discovery.** Its matching is genuine; its discovery is
  an offline index. It exists for demo resilience and must be disclosed when used.
- **Threshold, not proof.** A 0.40 ArcFace cosine is a tuned heuristic. ArcFace has
  documented accuracy disparities across demographic groups. This is not a legal
  identification standard and should never be treated as one.
- **Anchoring proves *when a claim was recorded*, not that the claim is true.** FaceProof
  provides integrity and timestamping over its own output. It cannot make a wrong match
  right.
- **Content can disappear.** The matched post can be deleted or edited by its author.
  FaceProof preserves the fingerprint, not the content, unless you pin the bundle to IPFS
  and pass the CID.
- **Public-testnet dependency.** Sepolia and Base Sepolia are testnets; their history
  carries no guarantee of permanence, and testnet ETH has no value. For a real deployment,
  use a mainnet with Merkle batching.
- **Image hosting for SerpApi.** The probe crop is briefly uploaded to a public throwaway
  host so the search engine can fetch it. That is a real (if short-lived) exposure of the
  probe image, and it is recorded in the audit trail rather than hidden.
- **Python 3.11/3.12 pin.** Newer Python versions lack `onnxruntime` wheels, and
  `insightface` is source-only — on Windows that also means MSVC Build Tools.

---

## Repository layout

```
faceproof/            pipeline package
  ingest.py           stage 1  hashing, EXIF strip
  face.py             stage 2  RetinaFace + ArcFace
  search/             stage 3  provider cascade
  rerank.py           stage 4  adversarial face verification
  evidence.py         stage 5  canonical JSON + hashing
  merkle.py                    sorted-pair Merkle tree
  chain.py            stage 6  web3 client
  verify.py           stage 7  four-verdict classification
  report.py                    rich console + HTML case report
  cli.py                       command line
contracts/            FaceEvidenceRegistry.sol + Hardhat tests
scripts/              deploy.py, fetch_models.py, make_corpus.py
tests/                pytest suite
BUILD_PLAN.md         design rationale, schedule, demo storyboard
OVERVIEW.md           one-page project summary + architecture diagram
SETUP.md              machine-specific runbook: install, keys, faucets, troubleshooting
SCRIPT.md             screen-recording script, shot by shot
```

## License

MIT — see [LICENSE](LICENSE).
