<div align="center">

# FaceProof

### Face scan → genuine web search → tamper-evident evidence on a public blockchain

**HH Goa 2026 · Shortlisting Task 3**

</div>

---

<div align="center">

| | |
|:--|:--|
| **Contract** | `0xcEcede3653BEf3942F8B7a6c37F7BFc10f7081b7` |
| **Network** | Ethereum Sepolia · chain id `11155111` · **public** |
| **Explorer** | [sepolia.etherscan.io](https://sepolia.etherscan.io/address/0xcEcede3653BEf3942F8B7a6c37F7BFc10f7081b7) |
| **Interface** | Command line. No website — the CLI *is* the product |

</div>

---

## The problem

> Take a face scan. Search the web for that person. Find a real social
> media post. Then use a blockchain to make that finding verifiable and
> tamper-evident.

## The summary

**FaceProof is a seven-stage forensic pipeline.** A face image goes in. A
real, live social media post comes out — found by an actual search, not a
hardcoded result. Three independent fingerprints of that finding are
written to a public blockchain, and the whole thing can be re-verified
later by anyone, from a browser.

Three decisions separate it from the obvious version of this task.

**The search engine is never trusted.** A reverse image search answers
*"what looks similar?"* — not *"is this the same person?"* So every
candidate it returns is re-downloaded, re-detected and re-embedded
locally, and must clear a face-similarity threshold before it can become
evidence. Rejections are recorded with their scores, not silently dropped.

**Three fingerprints go on chain, not one.** SHA-256 alone screams
"tampered" every time a CDN re-compresses a thumbnail. Adding a perceptual
hash and a semantic one lets the system tell *"someone edited this"* apart
from *"Instagram re-encoded this."*

**Privacy is enforced in code, not promised in a README.** The raw 512-d
face embedding is biometric data. It never leaves the machine and never
reaches the chain — it is quantized and hashed first, and a test in the
suite fails if anyone ever changes that.

---

## The four claims

| | Claim | Enforced by |
|:--:|:--|:--|
| **1** | The search engine is **not** trusted — every candidate is independently face-verified | `rerank.py` |
| **2** | **Three** fingerprints on chain — exact, perceptual, semantic | `evidence.py` |
| **3** | **Merkle batching** — N records, one transaction, flat gas | `merkle.py` + contract |
| **4** | **No biometric data on chain** — ever | `tests/test_evidence.py` |

---

## Architecture

```
╌╌╌╌╌╌╌  LOCAL MACHINE — nothing here is ever published  ╌╌╌╌╌╌╌

┌──────────────────────────────────────────────────────────────┐
│ probe image                                   samples/me.jpg │
└──────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌──────────────────────────────────────────────────────────────┐
│ ① INGEST                                           ingest.py │
│   sha256 of the ORIGINAL bytes  ·  perceptual hash           │
│   EXIF-stripped working copy (GPS, device serials)           │
└──────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌──────────────────────────────────────────────────────────────┐
│ ② FACE                                               face.py │
│   RetinaFace detect → 5-point align → ArcFace                │
│   512-d L2-normalized embedding  +  padded crop              │
│   the raw vector STOPS HERE — only its sha256 travels        │
└──────────────────────────────────────────────────────────────┘

╌╌╌╌╌╌  INTERNET — only the face crop crosses this line  ╌╌╌╌╌╌╌

┌──────────────────────────────────────────────────────────────┐
│ ③ SEARCH                                             search/ │
│   Google Lens · Yandex · Playwright · local corpus           │
│   live call, cascaded until a provider answers               │
└──────────────────────────────────────────────────────────────┘
                              │
                              ▼   N candidates — none trusted yet
┌──────────────────────────────────────────────────────────────┐
│ ④ RE-RANK                                          rerank.py │
│   re-download every candidate image                          │
│   re-detect, re-embed, cosine >= 0.40  or  REJECT            │
│   every accept AND reject recorded with its score            │
└──────────────────────────────────────────────────────────────┘
                              │
                              ▼   1 verified match
┌──────────────────────────────────────────────────────────────┐
│ ⑤ EVIDENCE                                       evidence.py │
│   canonical JSON — sorted keys, no whitespace                │
│   collapses to ONE 32-byte evidence hash                     │
└──────────────────────────────────────────────────────────────┘

╌╌╌╌╌╌╌╌╌╌╌  PUBLIC CHAIN — digests only, permanent  ╌╌╌╌╌╌╌╌╌╌╌

┌──────────────────────────────────────────────────────────────┐
│ ⑥ ANCHOR                                            chain.py │
│   anchor(evidenceHash, pHash, embeddingHash, cid)            │
│   Ethereum Sepolia · one transaction · ~0.0005 ETH           │
└──────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌──────────────────────────────────────────────────────────────┐
│ ⑦ VERIFY                                           verify.py │
│   recompute locally  +  read the chain  →  compare           │
│   EXACT · PERCEPTUAL · TAMPERED · UNANCHORED                 │
└──────────────────────────────────────────────────────────────┘
```

The two dotted lines are the ones that matter. **Only a cropped face
region ever crosses the first. Only digests ever cross the second.**

---

## The pipeline, stage by stage

### ① Ingest · `ingest.py`

Hash the file **before** touching it, so chain of custody survives.

| | |
|:--|:--|
| Takes | the probe image, exactly as given |
| Does | `sha256` of the original bytes · 64-bit perceptual hash · EXIF-stripped working copy |
| Leaves behind | `original.jpg` (untouched) · `clean.jpg` (no GPS, no device serial) |
| Why | EXIF carries location and hardware identifiers. Strip it — but hash first, or the record describes a file that never existed |

### ② Face · `face.py`

| | |
|:--|:--|
| Model | InsightFace `buffalo_l` — RetinaFace detection, ArcFace recognition |
| Does | detect → 5-point align → **512-d L2-normalized embedding** |
| Also writes | a crop padded by 60%, because a tight 112×112 face chip performs badly in reverse image search |
| Publishes | `sha256(int8_quantize(embedding))` — **irreversible** |
| Never publishes | the embedding itself |

> Quantizing to int8 before hashing means float jitter across CPUs and BLAS
> backends can't change the digest. Without it, verification would fail on a
> different machine for no reason.

### ③ Search · `search/`

| Provider | Needs | Notes |
|:--|:--|:--|
| `serpapi` — Google Lens | API key | Primary. Best social coverage |
| `yandex` — Yandex Images, also via SerpApi | API key | Better *face* recall; Lens is tuned for objects |
| `playwright` | nothing | Headless Chromium on lens.google.com. Free, genuine, brittle |
| `local` | nothing | Offline corpus. Matching is real, **discovery is local — disclose it** |

Providers cascade until one answers. The crop is briefly hosted on a public
throwaway host so the engine has a URL it can fetch — a real, short-lived
exposure, written into the audit trail rather than hidden.

> **What SerpApi is, and what it isn't.** Google Lens has no official public
> API, so SerpApi is the *transport*: it runs the Lens — or Yandex Images —
> query and hands back structured JSON, instead of this project scraping
> Google directly and breaking every time the page markup changes.
>
> The search is still a genuine Lens search, executed live at the moment the
> command runs. Nothing is cached or pre-picked.
>
> SerpApi does **no face matching at all.** It returns pages that *look*
> similar. Stage ④ exists precisely because that is not the same claim as
> *"same person."*
>
> Free tier is roughly **100 searches a month**, and every provider the
> cascade attempts spends one — a run that falls through Lens to Yandex
> costs two. Both key-free providers (`playwright`, `local`) exist so the
> pipeline still runs when the quota does not.

### ④ Re-rank · `rerank.py` — the adversarial step

```
   candidate  →  download  →  detect face  →  re-embed  →  cosine vs probe
                                                              │
                                              ┌───────────────┴──────────────┐
                                        >= 0.40                          < 0.40
                                              │                              │
                                          EVIDENCE                        REJECT
                                                                    (logged, with score)
```

Nothing the search engine says is taken at face value. Accepts *and*
rejects are recorded, so the decision is auditable and the threshold is
arguable rather than hidden.

### ⑤ Evidence · `evidence.py`

Everything is packed into one bundle — post URL, platform, both image
hashes, the similarity score, the threshold used, providers attempted,
timestamps — then serialized **canonically**: sorted keys, no whitespace,
UTF-8, no NaN.

> Without canonicalization the same evidence would serialize differently
> between runs, the hash would drift, and verification would fail
> spuriously. The whole tamper-evidence claim rests on this.

Volatile data — the full audit trail, the anchor receipt — deliberately
sits **outside** the hashed region, so recording the transaction does not
invalidate the hash it recorded.

### ⑥ Anchor · `chain.py` + `FaceEvidenceRegistry.sol`

**What one transaction writes:**

| Field | Meaning |
|:--|:--|
| `evidenceHash` | sha256 of the canonical bundle — breaks on any byte change |
| `pHash` | perceptual hash — survives re-compression and resize |
| `embeddingHash` | sha256 of the quantized face vector — semantic, irreversible |
| `merkleRoot` | non-zero only for batch anchors |
| `timestamp` | block time of the **first** anchor, set by the contract |
| `itemCount` | 1, or N for a batch |
| `submitter` | the signing wallet |
| `cid` | optional IPFS CID |

**What it does *not* write:** no image · no embedding · no URL · no
platform · no name · no similarity score.

> The chain alone identifies nobody. It only lets someone confirm that a
> specific bundle existed at a specific time. To show *what* was anchored
> you must produce the bundle — and the chain then confirms it is unedited.

Re-anchoring a hash the contract has already seen **reverts** with
`AlreadyAnchored(id, firstSeen)`. The first-seen timestamp is the entire
evidentiary claim; allowing an overwrite would defeat the registry.

**Merkle mode** — `anchorBatch` puts N records on chain under one root in
one transaction, gas flat in N, and `verifyInclusion` proves any single
record's membership on chain afterwards. Python and Solidity use identical
sorted-pair hashing, so a proof built locally verifies on chain untouched.

### ⑦ Verify · `verify.py`

Recompute every hash locally from the bundle, read the record back off the
chain, compare.

| Verdict | Meaning |
|:--:|:--|
| ✅ **EXACT** | Recomputed hash equals the on-chain hash, byte for byte |
| ⚠️ **PERCEPTUAL** | Hash differs, but pHash hamming ≤ 8 **and** face cosine ≥ 0.90 — a re-encode, not an edit |
| ❌ **TAMPERED** | Anchored, but neither the hash nor the fingerprints line up |
| ⬜ **UNANCHORED** | Nothing on chain for this hash |

---

## Verify it yourself — no wallet, no code

1. Open the [contract on Etherscan](https://sepolia.etherscan.io/address/0xcEcede3653BEf3942F8B7a6c37F7BFc10f7081b7)
2. **Contract → Read Contract**
3. `recordCount()` — how many records exist
   `recordAt(i)` — read one
   `verify(bytes32)` — paste an evidence hash, get the record back

Nothing on this machine is involved in that answer.

---

## By the numbers

| | |
|:--|:--|
| Pipeline stages | 7 |
| Fingerprints anchored per record | 3 |
| Embedding dimensions kept local | 512 |
| Bytes published per record | 4 × 32, plus a timestamp and an address |
| Deploy cost | 819,763 gas · ~0.0002 test ETH |
| Anchor cost | ~0.0005 test ETH · flat for a whole Merkle batch |
| Chains supported | Sepolia · Base Sepolia · local Anvil/Hardhat — one code path |

---

## Stated plainly

Consent is a required flag — `faceproof run` refuses to start without it.
A 0.40 cosine is a tuned threshold, not a legal identification standard,
and ArcFace has documented accuracy disparities across demographic groups.
Anchoring proves **when a claim was recorded**, not that the claim is true.

This is a hackathon build. It is not for surveillance or for identifying
anyone who has not agreed to it.

<div align="center">

---

**README.md** · design overview  **SETUP.md** · runbook  **SCRIPT.md** · demo script

MIT

</div>
