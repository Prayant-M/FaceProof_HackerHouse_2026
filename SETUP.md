# FaceProof — Setup & Run Guide

Machine-specific runbook for `E:\Projects\HackerHouse_2026`.
Audited 2026-09-06 against the actual repo state and the actual toolchain on this box.
Updated 2026-09-07: contract is now **live on a public chain** (Ethereum Sepolia) —
see [section 5](#5-testnet--faucets-rpc-explorer).

`README.md` describes the design. **This file describes what you personally still have to
do to make it run.**

---

## Table of contents

1. [What this project is](#1-what-this-project-is)
2. [Current state of this machine](#2-current-state-of-this-machine)
3. [Toolchain problems you will hit](#3-toolchain-problems-you-will-hit)
4. [API keys — what and where](#4-api-keys--what-and-where)
5. [Testnet — faucets, RPC, explorer](#5-testnet--faucets-rpc-explorer)
6. [Step-by-step install](#6-step-by-step-install)
7. [Running the pipeline](#7-running-the-pipeline)
8. [Command reference](#8-command-reference)
9. [Recommended order of work](#9-recommended-order-of-work)
10. [Troubleshooting](#10-troubleshooting)
11. [Quota and cost discipline](#11-quota-and-cost-discipline)
12. [Ethics / consent gate](#12-ethics--consent-gate)

---

## 1. What this project is

**FaceProof** — a command-line forensic pipeline. Face image in, blockchain-anchored
tamper-evident evidence bundle out. **No website.** The CLI is the product.

Built for HH Goa 2026 — Shortlisting Task 3.

### Pipeline

```
image
  |- stage 1  ingest.py    sha256 of original bytes + pHash + EXIF-stripped copy
  |- stage 2  face.py      RetinaFace detect -> 5-pt align -> ArcFace 512-d embedding
  |- stage 3  search/      reverse image search, provider cascade
  |- stage 4  rerank.py    re-download every hit, re-embed, cosine >= 0.40 or reject
  |- stage 5  evidence.py  canonical JSON (sorted keys, no whitespace) + hash
  |- stage 6  chain.py     anchor 3 hashes on chain
  \- stage 7  verify.py    recompute + read chain -> EXACT / PERCEPTUAL / TAMPERED / UNANCHORED
```

### The four design claims

| # | Claim | Where |
|---|---|---|
| 1 | Search engine is **not trusted** — every candidate is re-downloaded, re-detected, re-embedded locally, and must clear the ArcFace threshold | `rerank.py` |
| 2 | **Three** fingerprints on chain: `sha256` (any byte change), `pHash` (survives re-compression), embedding hash (semantic) | `evidence.py` |
| 3 | **Merkle batching** — N records, one transaction, O(1) gas. Python and Solidity use identical sorted-pair hashing | `merkle.py` + contract |
| 4 | **Privacy enforced** — raw 512-d embedding never leaves the machine; quantized to int8, SHA-256'd, only the digest is published | `tests/test_evidence.py::test_bundle_contains_no_raw_biometric_data` |

Why three fingerprints: a SHA-256-only design reports TAMPERED every time a CDN
re-compresses a thumbnail, which makes it useless in the field. FaceProof can tell
*"someone edited this"* apart from *"Instagram re-encoded this."*

### Verdicts

| Verdict | Meaning |
|---|---|
| `EXACT` | Recomputed hash equals on-chain hash, byte for byte |
| `PERCEPTUAL` | Hash differs, but pHash hamming <= 8 **and** face cosine >= 0.90 — a re-encode, not an edit |
| `TAMPERED` | Anchored, but neither hash nor fingerprints line up |
| `UNANCHORED` | Nothing on chain for this hash |

### Contract

`contracts/FaceEvidenceRegistry.sol` — Solidity 0.8.24, optimizer on, 200 runs.

Stores `bytes32 evidenceHash`, `bytes32 pHash`, `bytes32 embeddingHash`, a timestamp, a
count, the submitter address, and an optional IPFS CID string. Only hashes. No images, no
biometrics.

Re-anchoring the same hash **reverts** with `AlreadyAnchored(id, firstSeen)` — the
first-seen timestamp is the entire evidentiary claim, so allowing an overwrite would defeat
the registry.

### Node.js role

**The runtime does not need Node.** Python compiles and deploys the contract via
`py-solc-x`. Hardhat exists only for (a) `npx hardhat test` Solidity unit tests and
(b) `npx hardhat node` as a local chain.

---

## 2. Current state of this machine

Verified 2026-09-07.

| Thing | Status | Created by |
|---|---|---|
| `.venv` | **created** — Python 3.12.3 | `py -3.12 -m venv .venv` |
| Python dependencies | **installed** | `pip install -r requirements.txt` |
| `.env` | **created**, `SERPAPI_KEY` + testnet keys filled | `copy .env.example .env` |
| `node_modules` | **installed** | `npm install` |
| InsightFace models (~300 MB) | **downloaded** | `scripts/fetch_models.py` |
| `samples\me.jpg` probe image | **present** — pipeline has run end to end | **you, manually** |
| `out/deployment_local.json` | **deployed** `0x5FbDB2315678afecb367f032d93F642f64180aa3` | `scripts/deploy.py --chain local` |
| `out/deployment_sepolia.json` | **deployed** `0xcEcede3653BEf3942F8B7a6c37F7BFc10f7081b7` | `scripts/deploy.py --chain sepolia` |
| `out/deployment_base-sepolia.json` | not deployed — wallet unfunded on Base | `scripts/deploy.py --chain base-sepolia` |

`python -m faceproof info` prints this table live, including the resolved signer address
for every network.

Present and fine: git repo clean on `main`, Node v24.14.0, npm 11.12.1,
Python 3.12 / 3.13 / 3.14, MSVC Build Tools 2022 + 2026.

---

## 3. Toolchain problems you will hit

### A. Python version — 3.13 and 3.14 will NOT work

Installed on this box: 3.14 (default), 3.13, 3.12. **Python 3.11 is not installed.**

Verified against PyPI:

- `onnxruntime==1.18.1` -> cp312 wheel **exists**
- `onnxruntime==1.18.1` -> no cp313 / cp314 wheel

So **3.11 or 3.12 only**. **This build uses 3.12** — no reason to download 3.11.

`setup.ps1` originally hardcoded `py -3.11` and exited 1 when it was absent. It has been
**patched** to probe `3.12` then `3.11` and use whichever it finds, so it now works here
unchanged.

### B. `insightface==0.7.3` has no wheel for ANY Python version

Verified:

```
> pip download insightface==0.7.3 --only-binary=:all: --no-deps
ERROR: No matching distribution found for insightface==0.7.3
```

It is source-distribution only and compiles Cython C extensions. On Windows that requires
**Microsoft C++ Build Tools**. The README does not mention this. It is the single most
likely install failure on a fresh machine.

**On this box it is already satisfied** — `vswhere` reports Visual Studio Build Tools 2022
*and* 2026, both with `Microsoft.VisualStudio.Component.VC.Tools.x86.x64`. `cl.exe` is not
on `PATH`, which is fine: setuptools locates the compiler through `vswhere` on its own.

### C. Node v24 vs Hardhat 2.22

Hardhat 2.x officially supports Node 18 / 20 / 22. Node 24 prints an unsupported-version
warning. It generally still works. This only affects `npx hardhat test` and
`npx hardhat node`, never the Python pipeline.

---

## 4. API keys — what and where

Exactly **two** secrets exist in the whole codebase. Confirmed by grepping every
`os.getenv` call in `faceproof/` and `scripts/`.

### `SERPAPI_KEY` — live web search

- **Get it:** https://serpapi.com/users/sign_up -> dashboard -> *Your Private API Key*
- Free tier ~100 searches/month. No credit card.
- Powers **both** the `serpapi` (Google Lens) and `yandex` providers.
- **Each cascade attempt spends one search.** Do not burn quota while debugging.
- **Skippable.** `--provider playwright` (free headless-Chromium scraper, brittle) and
  `--provider local` (offline corpus) need no key at all.

### Keys resolve **per network**

`config.private_key_for(network)` picks the signing key, most specific first:

| # | Source | Example |
|---|---|---|
| 1 | `PRIVATE_KEY_<NETWORK>` | `PRIVATE_KEY_BASE_SEPOLIA` |
| 2 | `PRIVATE_KEY` | shared fallback |
| 3 | Hardhat dev account | **local chain only**, automatic |

So the local chain works with an empty `.env`, and the public testnet gets its own
funded throwaway wallet — both live in one file, both usable at once.

**Signing on a public network with the Hardhat dev key is refused outright.** That key is
published in Hardhat's docs: the on-chain `submitter` field would prove nothing, and
sweeper bots empty the address on sight. `python -m faceproof info` shows the resolved
signer address for every network (never the key itself).

### `PRIVATE_KEY` — any chain write

- **Use a throwaway wallet.** MetaMask -> create new account -> Account details ->
  Show private key. 64 hex chars, `0x` prefix optional.
- Never a key that holds real value. Testnet funds only.
- For `--chain local`: use a Hardhat dev key. `npx hardhat node` prints 20 pre-funded
  accounts with their private keys on startup — copy Account #0's. That key is public
  knowledge and safe **only** because it is local-chain-only.

### Not required

- **IPFS / Pinata** — `--cid` is a manual command-line flag. No API, no key.
- **Image hosting** — `tmpfiles.org` (falling back to `catbox.moe`) are anonymous
  endpoints. No key. Used to give SerpApi a fetchable URL for the probe crop, because
  SerpApi's Lens/Yandex engines need a URL, not a file upload.

### `.env` — fill the key and the network you actually fund

```ini
SERPAPI_KEY=your_serpapi_key_here

# whichever public testnet you funded -- one is enough
PRIVATE_KEY_SEPOLIA=0xyour_throwaway_testnet_key
PRIVATE_KEY_BASE_SEPOLIA=0xyour_throwaway_testnet_key
SEPOLIA_RPC=https://ethereum-sepolia-rpc.publicnode.com
```

The same throwaway key can serve both networks — one wallet address exists on every EVM
chain, but its **balance is per chain**. Funding it on Ethereum Sepolia does nothing for
Base Sepolia and vice versa. That is the single most common confusion here.

Everything else in `.env.example` already has a working default:
`BASE_SEPOLIA_RPC`, `LOCAL_RPC`, `DEFAULT_CHAIN=local`, `FACE_MATCH_THRESHOLD=0.40`,
`PHASH_HAMMING_MAX=8`, `PERCEPTUAL_COSINE_MIN=0.90`, `CROP_MARGIN=0.60`,
`SEARCH_LIMIT=25`, `HTTP_TIMEOUT=30`, `PLAYWRIGHT_HEADLESS=1`.

`.env` is gitignored. Never commit it.

---

## 5. Testnet — faucets, RPC, explorer

### Live deployments (as of 2026-09-07)

| Network | Chain id | Contract | Status |
|---|---|---|---|
| Ethereum Sepolia | `11155111` | [`0xcEcede3653BEf3942F8B7a6c37F7BFc10f7081b7`](https://sepolia.etherscan.io/address/0xcEcede3653BEf3942F8B7a6c37F7BFc10f7081b7) | **live, public** |
| Local Hardhat | `31337` | `0x5FbDB2315678afecb367f032d93F642f64180aa3` | live while `npx hardhat node` runs |
| Base Sepolia | `84532` | — | not deployed (wallet unfunded on Base) |

Deploy tx: [`0xcdcd8e2e…4c062a`](https://sepolia.etherscan.io/tx/0xcdcd8e2e0e8fc4c953f7a5559fd1573d80c09bcfd96514950f31467ffc4c062a) · 819,763 gas.

**This is the answer to "how do other people see it on a chain."** Anyone opens the
Etherscan link, clicks **Contract → Read Contract**, pastes an evidence hash into
`verify(bytes32)`, and gets the stored record back — no wallet, no clone of this repo, no
access to your machine. `recordCount()` and `recordAt(i)` browse every anchored record.

### Testnet ETH is fake

Faucet ETH has no market value and cannot move to or from a mainnet. It exists only to pay
gas. Deploying costs ~0.0002 ETH, an anchor ~0.0005, so 0.05 ETH is hundreds of runs.

**Only ever paste your wallet *address* into a faucet. Never the private key.**

### Which faucet actually works

Base Sepolia's faucets mostly gate on holding real mainnet ETH. Ethereum Sepolia's Google
Cloud faucet does not, which is why the live deployment above landed on Sepolia:

| Faucet | Network | Gate |
|---|---|---|
| Google Cloud | Ethereum Sepolia | Google account only — **worked, 0.05 ETH** |
| Coinbase CDP | Base Sepolia | free CDP signup |
| Alchemy | either | requires ≥ 0.001 ETH on **mainnet** |
| QuickNode | Base Sepolia | requires mainnet balance |

- Google: https://cloud.google.com/application/web3/faucet/ethereum/sepolia
- Coinbase: https://portal.cdp.coinbase.com/products/faucet

Holding Sepolia ETH but needing Base Sepolia? Bridge at https://superbridge.app/base-sepolia
(~2 min). Simpler: just deploy to `--chain sepolia` instead — identical code path.

### Ethereum Sepolia — chain id `11155111` — currently deployed

```powershell
python scripts\deploy.py --chain sepolia
python -m faceproof anchor --evidence <id> --chain sepolia
```

RPC default: `https://ethereum-sepolia-rpc.publicnode.com` (free, no signup).
Explorer: https://sepolia.etherscan.io — ~12 s blocks, so an anchor visibly pauses.

### Base Sepolia — chain id `84532` — supported, not currently deployed

Chosen because faucets are reliable, blocks are ~2 s (a demo does not stall waiting for
confirmation), and BaseScan gives anyone a public URL to independently verify the
transaction.

**Faucets** — fund your deployer address before `deploy.py --chain base-sepolia`:

| Faucet | URL | Note |
|---|---|---|
| Coinbase CDP | https://portal.cdp.coinbase.com/products/faucet | most reliable |
| Alchemy | https://www.alchemy.com/faucets/base-sepolia | README's pick, needs Alchemy signup |
| QuickNode | https://faucet.quicknode.com/base/sepolia | backup |

**Explorer:** https://sepolia.basescan.org

**RPC:** `https://sepolia.base.org` — free public, works, already the default.
For a live demo a dedicated endpoint is more reliable: https://dashboard.alchemy.com ->
create a Base Sepolia app -> copy the HTTPS URL into `BASE_SEPOLIA_RPC` in `.env`.

### Local chain — `--chain local`

Identical code path. No faucet, no network, no cost, unlimited retries.
`npx hardhat node` serves `http://127.0.0.1:8545`. **Do all your development here.**

### Picking one

Local for development (free, instant, unlimited). Sepolia for the public proof — it is
deployed and funded already. Base Sepolia only if the demo specifically needs Base; it
needs its own faucet run.

---

## 6. Step-by-step install

> **Windows users: do not run the bash block from `README.md`.** `python3.11`, `source`,
> and `cp` do not exist in cmd.exe or PowerShell. Use the commands below.

### Step 1 — Python

Already satisfied: Python 3.12.3 is installed at `C:\Program Files\Python312`.
Nothing to download. Do **not** use 3.13 or 3.14
([section 3A](#a-python-version--313-and-314-will-not-work)).

### Step 2 — Microsoft C++ Build Tools

Already satisfied on this box — Build Tools 2022 and 2026 are both present with the
VC x86/x64 toolset ([section 3B](#b-insightface073-has-no-wheel-for-any-python-version)).

On a fresh machine you would need:

```powershell
winget install Microsoft.VisualStudio.2022.BuildTools --override "--wait --quiet --add Microsoft.VisualStudio.Workload.VCTools --includeRecommended"
```

Then open a **fresh terminal** (or reboot) so the toolchain registers.

### Step 3 — venv + dependencies

`setup.ps1` has been **patched** to probe for 3.12 first, then 3.11, instead of demanding
3.11. It is idempotent — it skips the venv and `.env` if they already exist — so it is safe
to run now:

```powershell
cd E:\Projects\HackerHouse_2026
.\setup.ps1
```

<details>
<summary>Manual equivalent, if you would rather see each step</summary>

**PowerShell:**

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -r requirements.txt
python scripts\fetch_models.py
copy .env.example .env
```

**cmd.exe** — identical except the activate line:

```
py -3.12 -m venv .venv
.venv\Scripts\activate.bat
```
</details>

`requirements.txt` pulls ~400 MB. `fetch_models.py` pulls ~300 MB of InsightFace weights
into `~/.insightface/models`. Pre-downloading the models matters: the first `FaceAnalysis`
call otherwise stalls on a progress bar in the middle of your demo recording.

<details>
<summary>Linux / macOS equivalent</summary>

```bash
python3.12 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
python scripts/fetch_models.py
cp .env.example .env
```
</details>

### Step 4 — edit `.env`

Fill in `SERPAPI_KEY` and `PRIVATE_KEY`. See [section 4](#4-api-keys--what-and-where).

### Step 5 — add a probe image at `samples\me.jpg`

Read `samples/README.md` first. **This is the most common way the project fails.**

| Subject | Expected result |
|---|---|
| You, with public posts on Instagram / LinkedIn / X | usually works |
| You, with no public photos anywhere | **zero hits — correct behaviour, dead demo** |
| A public figure | reliably works; use this to prove the pipeline |

Test your probe subject **early**. Discovering on the last day that your face returns
nothing is the single most common way this project fails. Probe images are gitignored on
purpose — do not commit photographs of people.

### Step 6 — install Node dependencies

Only needed for the Solidity tests and the local chain.

```powershell
npm install
```

### Step 7 — verify with the local chain

Terminal 1 — leave this running:

```powershell
npx hardhat node
```

Terminal 2:

```powershell
.\.venv\Scripts\Activate.ps1
python scripts\deploy.py --chain local
python -m faceproof run --image samples\me.jpg --chain local --i-have-consent --html
```

### Step 8 — deploy to a public testnet

**Already done for Ethereum Sepolia** — see [section 5](#5-testnet--faucets-rpc-explorer).
To repeat it on a fresh machine or a different network:

```powershell
# 1. see which address needs funding (prints the signer, never the key)
python -m faceproof info

# 2. paste that ADDRESS into a faucet, wait ~1 min

# 3. deploy
python scripts\deploy.py --chain sepolia
```

`deploy.py` prints the deployer address, its balance, and the chain id before sending, and
**stops with the faucet list on a zero balance** rather than failing later with an opaque
`gas required exceeds allowance (0)`. It writes `out\deployment_<chain>.json` (address +
ABI + tx hash) and refuses to redeploy over an existing record without `--force`.

Check a balance directly:

```powershell
python -c "from faceproof import config; from web3 import Web3; w3=Web3(Web3.HTTPProvider(config.CHAINS['sepolia']['rpc'])); a=w3.eth.account.from_key(config.private_key_for('sepolia')); print(a.address, w3.from_wei(w3.eth.get_balance(a.address),'ether'), 'ETH')"
```

### Step 9 — run the tests

```powershell
python -m pytest      # canonicalization, Merkle, verdict logic, privacy invariant
npx hardhat test      # Solidity: anchoring, revert-on-overwrite, Merkle inclusion
```

`tests/test_evidence.py::test_bundle_contains_no_raw_biometric_data` is the one that guards
the privacy claim — if someone adds the raw embedding to the bundle, it fails.

---

## 7. Running the pipeline

### One shot

```powershell
python -m faceproof run --image samples\me.jpg --chain sepolia --i-have-consent --html
```

### Stage by stage

This is what the demo recording does, so each step is visible on camera instead of
scrolling past.

```powershell
python -m faceproof info
python -m faceproof scan   --image samples\me.jpg
python -m faceproof search --scan <scan_id>
python -m faceproof anchor --evidence <scan_id> --chain sepolia
python -m faceproof verify --evidence <scan_id> --chain sepolia
python -m faceproof tamper-demo --evidence <scan_id> --chain sepolia
```

`--chain sepolia` is the deployed public network ([section 5](#5-testnet--faucets-rpc-explorer)).
Swap in `local` to rehearse for free, or `base-sepolia` once that wallet is funded — the
code path is identical either way.

### Driven demo

Runs that whole sequence with a pause and a screen-clear between stages.

```powershell
.\demo.ps1 -Image samples\me.jpg -Chain local
.\demo.ps1 -Image samples\me.jpg -Chain sepolia
.\demo.ps1 -Image samples\me.jpg -Chain local -NoPause   # unattended
```

### Makefile (Git Bash / Linux / macOS)

```bash
make install        # pip install -r requirements.txt
make models         # scripts/fetch_models.py
make test           # pytest
make contract-test  # npx hardhat test
make chain          # npx hardhat node
make deploy CHAIN=local
make run IMAGE=samples/me.jpg CHAIN=local
make clean
```

### What a complete run actually changes

`faceproof run` is stages 1–7 in order. Nothing outside `out/` and the chain is touched
— no global state, no system config, no writes elsewhere in the repo.

#### Files created on disk

| Stage | Path | Contents |
|---|---|---|
| 1 | `out/scan_<id>/original.jpg` | byte-for-byte copy of your probe image, EXIF intact — the chain-of-custody original |
| 1 | `out/scan_<id>/clean.jpg` | EXIF-stripped working copy, JPEG q95. Everything downstream reads this, so GPS and device serials never travel |
| 2 | `out/scan_<id>/embedding.npy` | **raw 512-d ArcFace vector. Biometric data. Never uploaded, never hashed into the bundle, never on chain.** Kept only so `search` can re-run without re-detecting |
| 2 | `out/scan_<id>/annotated.jpg` | detection overlay — bbox + confidence. Demo visual |
| 2 | `out/scan_<id>/probe_crop.jpg` | face crop padded by `CROP_MARGIN` (60%). This is the file uploaded to the image host |
| 2 | `out/scan_<id>.json` | scan record: `scan_id`, sha256 of the original, pHash, byte count, bbox, det score, face count, embedding hash, timestamps, and the four paths above |
| 5 | `out/ev_<id>.json` | evidence envelope — the canonical `bundle` (the hashed part), its `evidence_hash`, the full `audit` (every provider attempt, every candidate with its cosine score and accept/reject), and `anchor: null` |
| 6 | `out/ev_<id>.json` *(rewritten)* | same file; `anchor` now holds tx hash, block, gas used, contract, submitter, explorer URL. The `bundle` is untouched, so the hash still verifies |
| `--html` | `out/case_<id>.html` | self-contained case report |
| deploy | `out/deployment_<chain>.json` | contract address, ABI, deploy tx, block, gas, deployer, solc version |

`<id>` is a fresh random 12-hex-char `scan_id` per run, so runs never collide.

#### What leaves your machine

| Step | Goes where | What exactly |
|---|---|---|
| Stage 3 | `tmpfiles.org`, else `catbox.moe` | `probe_crop.jpg`, on a public anonymous host, so the search engine has a fetchable URL. A real if short-lived exposure — the URL is recorded in the audit trail rather than hidden |
| Stage 3 | SerpApi | that URL. Spends **one search credit per provider attempted** |
| Stage 4 | the candidate image hosts | a plain GET on every candidate image, to re-embed it locally |
| Stage 6 | the chain RPC | one signed transaction — see below |

#### What goes on chain

One `anchor()` call. Permanent and public:

| Field | Value |
|---|---|
| `evidenceHash` | sha256 of the canonical bundle |
| `pHash` | perceptual hash of the matched image |
| `embeddingHash` | sha256 of the int8-quantized embedding — **irreversible, not the vector** |
| `timestamp` | block time, set by the contract |
| `submitter` | your wallet address |
| `cid` | empty unless you pass `--cid` |

**No image, no URL, no name, no embedding.** Everything on chain is a digest.
Re-anchoring the same hash reverts with `AlreadyAnchored` — first-seen wins, always.

#### What it costs

| | Local | Sepolia |
|---|---|---|
| Deploy, once | free | ~0.0002 ETH, 819,763 gas |
| Each anchor | free | ~0.0005 ETH |
| Each search | 1 SerpApi credit per provider attempted | same |

#### What it does *not* do

No tracked repo file is modified, nothing is committed or pushed, `.env` is never touched,
the original image is never uploaded (only the crop), and nothing biometric is published.

---

## 8. Command reference

| Command | Does |
|---|---|
| `info` | Which providers are available, which chains are deployed, current thresholds |
| `scan --image X` | Stages 1-2: ingest, hash, detect, encode. Writes an annotated overlay and a search crop |
| `search --scan ID` | Stages 3-5: live search, adversarial re-rank, evidence bundle |
| `anchor --evidence ID --chain C` | Stage 6: write the record on chain |
| `verify --evidence ID --chain C` | Stage 7: recompute, read chain, classify |
| `batch-anchor --evidence "out/ev_*.json"` | Merkle-batch many bundles into one transaction |
| `tamper-demo --evidence ID` | Flip one character, prove the chain rejects it |
| `report --evidence ID` | Write a self-contained HTML case report |

### Useful flags

| Flag | Effect |
|---|---|
| `--provider serpapi\|yandex\|playwright\|local` | Pin one provider instead of running the cascade |
| `--threshold 0.35` | Override the ArcFace cosine cutoff |
| `--any-domain` | Drop the social-platform domain filter |
| `--limit 40` | More candidates per search |
| `--live-refetch` | On `verify`, re-download the matched post |
| `--html` | Write an HTML case report |
| `--cid <ipfs-cid>` | Record an IPFS CID of the full bundle on chain |
| `--i-have-consent` | **Required** by `run`. See [section 12](#12-ethics--consent-gate) |
| `--force` | On `deploy.py`, redeploy over an existing deployment record |

### Search providers

| Provider | Key | Notes |
|---|---|---|
| `serpapi` (Google Lens) | `SERPAPI_KEY` | Best social coverage. Primary. |
| `yandex` (via SerpApi) | `SERPAPI_KEY` | Better *face* recall than Lens, which is tuned for objects |
| `playwright` | none | Headless Chromium against lens.google.com. Free, genuine, brittle. `pip install -r requirements-optional.txt` then `playwright install chromium` |
| `local` | none | Offline index under `samples/corpus/`. Matching is genuine, **discovery is local — disclose it** |

Providers are tried in cascade order until one returns results.

### Building the offline corpus

```powershell
python scripts\make_corpus.py --url https://www.instagram.com/p/XYZ/ --image dl.jpg
python scripts\make_corpus.py --url https://x.com/user/status/123 --image-url https://...
```

Writes `samples/corpus/post_NNN.jpg` plus a `post_NNN.json` sidecar with `page_url`,
`title`, `captured_at`. Corpus contents are gitignored — they are other people's
photographs.

---

## 9. Recommended order of work

1. **Build tools + Python 3.12 -> `setup.ps1`.** Longest step, most likely to fail. Do it first.
2. **Test the probe subject** with `--provider local` or a public figure. Confirm the search
   returns hits **before** spending any SerpApi quota.
3. **Local chain end-to-end.** Free, unlimited retries, identical code path.
4. **Only then** faucet + a public testnet. One good public transaction is all the demo
   needs — and Ethereum Sepolia is already deployed.
5. **`demo.ps1`** for the recording; [SCRIPT.md](SCRIPT.md) has the shot-by-shot voiceover.

---

## 10. Troubleshooting

| Symptom | Cause / fix |
|---|---|
| `setup.ps1` exits with "No supported Python found" | Neither 3.12 nor 3.11 is on `PATH`. `winget install Python.Python.3.12` |
| `'python3.11' is not recognized` / `source` fails | You ran the Linux block on Windows. Use `py -3.12 -m venv .venv` then `.venv\Scripts\activate.bat` (cmd) or `.\.venv\Scripts\Activate.ps1` (PowerShell) |
| `&&` gives a parser error | PowerShell 5.1 has no `&&`. Run the commands on separate lines, or use `;` |
| `Activate.ps1 cannot be loaded ... execution policy` | `Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass` in that terminal, then activate again |
| `pip install insightface` tries to build and fails | Missing MSVC. Install C++ Build Tools ([3B](#b-insightface073-has-no-wheel-for-any-python-version)), open a fresh terminal, retry |
| `No matching distribution found for onnxruntime` | You are on Python 3.13 or 3.14. No wheels exist. Use 3.11 or 3.12 |
| Hardhat prints an unsupported-Node warning | Node 24 vs Hardhat 2.22. Usually harmless. Only affects Node commands |
| `deploy.py` dies with `Failed to resolve 'solc-bin.ethereum.org'` | Dead dependency URL, not your network. `py-solc-x==2.0.3` hardcodes a host Ethereum retired. Fixed by pinning `py-solc-x==2.0.5`, which uses `binaries.soliditylang.org`. Already applied to `requirements.txt`; on an old venv run `pip install --upgrade "py-solc-x==2.0.5"` |
| `no RPC for <chain> -- set it in .env` | That chain has no RPC in `.env`. `SEPOLIA_RPC` now defaults to `https://ethereum-sepolia-rpc.publicnode.com`; `base-sepolia` and `local` have defaults too |
| Balance reads `0 ETH` right after a faucet said "transaction complete" | **You funded a different chain.** One address, but a separate balance per chain — Sepolia ETH is invisible on Base Sepolia. Deploy to the chain you actually funded, or bridge at https://superbridge.app/base-sepolia |
| Every Base Sepolia faucet demands mainnet ETH | Known gating. Use the Google Cloud Ethereum Sepolia faucet and `--chain sepolia` instead ([section 5](#5-testnet--faucets-rpc-explorer)) |
| Explorer link printed without the `0x` prefix | Fixed. web3 7's `.hex()` drops it; `deploy.py` and `chain.py` both re-add it |
| `no signing key for '<net>'` | Set `PRIVATE_KEY_<NET>` or `PRIVATE_KEY` in `.env`. See [section 4](#4-api-keys--what-and-where) |
| `refusing to sign on '<net>' with the public Hardhat dev key` | Working as intended. That key is public knowledge — set `PRIVATE_KEY_BASE_SEPOLIA` to a funded throwaway wallet |
| `cannot reach http://127.0.0.1:8545` | `npx hardhat node` is not running in the other terminal |
| `WARNING: zero balance` | Fund the printed deployer address from a faucet ([section 5](#5-testnet--faucets-rpc-explorer)) |
| `already deployed on <chain>` | A deployment record exists in `out/`. Add `--force` to deploy a fresh instance |
| `provider 'X' unavailable (missing API key or dependency)` | `serpapi`/`yandex` need `SERPAPI_KEY`; `playwright` needs `pip install -r requirements-optional.txt` + `playwright install chromium` |
| `serpapi yandex: The URL does not refer to an image` — and Lens returns `ok 0` in the same run | **Not a probe problem.** tmpfiles.org changed its scheme: `/dl/<id>/` now serves an HTML viewer page, so both engines were handed a document instead of an image. Fixed in `_imagehost.py` — it now verifies `content-type` + magic bytes, prefers catbox, and scrapes tmpfiles' signed direct link as a fallback |
| Search returns zero hits, hosting verified OK | Probe subject has no public image footprint, **or the probe is too small**. A face bbox under ~150 px, or a screenshot rather than the original file, gives reverse image search almost nothing to match. Use the original full-resolution photo |
| `AlreadyAnchored` revert | By design. That hash already has a first-seen timestamp; overwriting would defeat the registry |
| Playwright provider suddenly breaks | It is a scraper. Google changed the Lens DOM. Fall back to `serpapi` or `local` |
| `could not host probe image publicly` | Both tmpfiles.org and catbox.moe are down or blocked. Use `--provider local` |
| First run stalls on a download bar | Models were never pre-fetched. Run `python scripts\fetch_models.py` |
| `verify` says TAMPERED on an untouched bundle | Volatile data leaked into the hashed region. The audit trail and anchor receipt live *outside* it by design |

---

## 11. Quota and cost discipline

- SerpApi free tier is **~100 searches/month**, and **each cascade attempt spends one**.
  A single failed `run` that walks `serpapi` -> `yandex` costs two.
- `--chain local` costs nothing. `--provider local` and `--provider playwright` cost nothing.
- Develop entirely on the local chain + local corpus. Spend live quota only on the take you
  actually record.
- Testnet gas is free but faucets are rate-limited. Deploy **once**; `deploy.py`
  already refuses to redeploy without `--force`. Sepolia is deployed — nothing to spend.
- `batch-anchor` puts N bundles on chain in one transaction. Use it if you have several.

---

## 12. Ethics / consent gate

`faceproof run` **refuses to start** without `--i-have-consent`. That is deliberate.

Run it on your own face, on a subject who has agreed, or on a public figure's
already-public posts. **Not on strangers.** Searching for a private individual without
consent is a GDPR and platform-ToS problem, and it is not what this tool is for.

- Probe images and the local corpus are gitignored. Do not commit photographs of people.
- Nothing biometric is published. Only irreversible digests reach the chain.
- If you demo with `--provider local`, **say so out loud** — the matching is genuine but
  the discovery is an offline index.

### Known limitations, stated plainly

- **Reverse image search is tuned for images, not faces.** Recall depends heavily on the
  subject's public image footprint.
- **Threshold, not proof.** A 0.40 ArcFace cosine is a tuned heuristic. ArcFace has
  documented accuracy disparities across demographic groups. This is not a legal
  identification standard and must never be treated as one.
- **Anchoring proves *when a claim was recorded*, not that the claim is true.** FaceProof
  provides integrity and timestamping over its own output. It cannot make a wrong match
  right.
- **Content can disappear.** The matched post can be deleted or edited by its author.
  FaceProof preserves the fingerprint, not the content, unless you pin the bundle to IPFS
  and pass `--cid`.
- **Image hosting exposure.** The probe crop is briefly uploaded to a public throwaway host
  so the search engine can fetch it. That is a real, if short-lived, exposure of the probe
  image — it is recorded in the audit trail rather than hidden.
- **Public-testnet dependency.** Sepolia and Base Sepolia are testnets; their history
  carries no guarantee of permanence, and testnet ETH has no value. For a real deployment,
  use a mainnet with Merkle batching.

This is a hackathon build, not a forensic product. It is not appropriate for surveillance,
doxxing, or any identification with consequences for the person identified.

---

## Repository layout

```
faceproof/            pipeline package
  ingest.py           stage 1  hashing, EXIF strip
  face.py             stage 2  RetinaFace + ArcFace
  search/             stage 3  provider cascade
    base.py                    cascade order, Candidate, provider registry
    serpapi_lens.py            Google Lens via SerpApi
    serpapi_yandex.py          Yandex Images via SerpApi
    playwright_lens.py         headless Chromium scraper
    local_corpus.py            offline index
    _imagehost.py              tmpfiles.org / catbox.moe upload
  rerank.py           stage 4  adversarial face verification
  evidence.py         stage 5  canonical JSON + hashing
  merkle.py                    sorted-pair Merkle tree
  chain.py            stage 6  web3 client
  verify.py           stage 7  four-verdict classification
  report.py                    rich console + HTML case report
  cli.py                       command line
  config.py                    all tunables, chain registry
contracts/            FaceEvidenceRegistry.sol + Hardhat tests
scripts/              deploy.py, fetch_models.py, make_corpus.py
tests/                pytest suite
out/                  scans, evidence bundles, deployment records, HTML reports
samples/              probe image (gitignored) + corpus/ (gitignored)
BUILD_PLAN.md         design rationale, schedule, demo storyboard
OVERVIEW.md           one-page summary + architecture diagram (shown on camera)
README.md             design overview
SETUP.md              this file
SCRIPT.md             screen-recording script, shot by shot
```

---

## License

MIT — see [LICENSE](LICENSE).
