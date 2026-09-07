# FaceProof — Screen Recording Script (Public Chain)

**Target length:** 8–9 minutes · **Chain:** Ethereum Sepolia, public · **Search:** live SerpApi
**Deadline:** Sept 7, 2026, 11:59 PM — submit the form only once the video link opens in incognito.

Everything in this take happens on a **public** chain, so a reviewer can open a block
explorer on their own machine and check every claim without trusting the recording.

| | |
|---|---|
| Contract | `0xcEcede3653BEf3942F8B7a6c37F7BFc10f7081b7` |
| Network | Ethereum Sepolia, chain id `11155111` |
| Explorer | https://sepolia.etherscan.io/address/0xcEcede3653BEf3942F8B7a6c37F7BFc10f7081b7 |
| Deploy tx | https://sepolia.etherscan.io/tx/0xcdcd8e2e0e8fc4c953f7a5559fd1573d80c09bcfd96514950f31467ffc4c062a |
| Wallet | `0xfA3fC3e2a6fd34Dda26b342228B4953C774c1fCf` |
| Opening slide | https://claude.ai/code/artifact/69b7b033-1707-455c-b6ff-17cfb28e20c6 |

---

## Pre-flight checklist (do ALL of these before pressing record)

**Machine**

- [ ] `python scripts/fetch_models.py` already run — models cached (~300 MB, never download on camera)
- [ ] Terminal font size **16+**, window on the left half of the screen
- [ ] Browser on the right half, three tabs, **in this order**: the **overview page** (your only slide — https://claude.ai/code/artifact/69b7b033-1707-455c-b6ff-17cfb28e20c6), the **contract on Etherscan**, and a blank tab for the matched post
- [ ] Overview page scrolled back to the top, and its browser zoom set so the title and the deployment strip fill the frame
- [ ] OBS at 1080p, mic tested — **the voiceover matters more than the editing**
- [ ] Old `out/` scans cleared so the run produces one clean fresh id
- [ ] `.env` never opened on screen; use a fresh terminal so no history is visible

**Chain**

- [ ] `python -m faceproof info` shows `chain:sepolia  deployed 0xcEcede…81b7`
- [ ] Wallet balance ≥ 0.01 ETH — check with the one-liner in [SETUP.md §6](SETUP.md#6-step-by-step-install). Each anchor costs ~0.0005
- [ ] Etherscan tab already loaded on the contract's **Read Contract** panel, so you are not hunting for it live
- [ ] `python scripts/deploy.py --chain local` also done, as a fallback if the public RPC misbehaves mid-take

**Search**

- [ ] SerpApi quota checked at https://serpapi.com/dashboard — free tier is ~100 searches/month
      and **each provider the cascade attempts spends one**, so pin `--provider serpapi` in the take
- [ ] **One successful test search done today** with the exact probe image you will use
- [ ] Probe subject confirmed to return at least one real hit (yourself if you have public posts, otherwise a public figure's already-public post)

**Screen layout:** left = terminal · right = browser on Etherscan. The browser is the point —
it is what turns "trust me" into "check it yourself."

---

## A note on the speaking style

Talk like you are explaining it to a smart colleague who does not work with blockchains.
Say what a thing *is* before you say what it *does*. Short sentences. It is fine to pause.
Do not read the terminal out loud — say what it means.

Three terms will carry the whole video, so define each one the first time, in one line:

- **hash** — "a fingerprint of a file. Same file, same fingerprint. Change one character and the fingerprint changes completely, and you can't work backwards from the fingerprint to the file."
- **embedding** — "a list of 512 numbers that describes the geometry of a face. Two photos of the same person land close together."
- **testnet** — "a real public blockchain that runs on free, worthless coins. Same code, same explorer, no money involved."
- **SerpApi** — "Google Lens has no public API, so SerpApi runs the Lens search for me and hands back the results as clean JSON. It's the plumbing — it does no face matching of its own."

---

## The script

### 0:00 – 0:35 · What this is

**Screen:** the overview page, at the top. The title and the deployment strip — contract
address, the green "Ethereum Sepolia" dot, chain id — are on screen while you talk. This
page is the only slide in the whole video.

**Say:**
> "Hi — this is FaceProof, my submission for Task 3.
>
> The brief was: take a face scan, search the web for that person, find a real social media post, and then use a blockchain to make that finding tamper-evident. That's what this does, end to end, from the command line. There's no website — the brief said one wasn't needed, so all the effort went into the pipeline.
>
> Quick framing before I run anything. The blockchain here is doing one narrow job: it's a public notebook that anyone can read and nobody can go back and edit. I write a fingerprint of my evidence into it, and later I can prove that fingerprint hasn't changed.
>
> [gesture at the strip] That's the contract, live on Ethereum Sepolia — a public test network. Real blockchain, free and worthless coins. Which matters here, because it means you don't have to take my word for any of this. Everything I'm about to do lands on a public block explorer that you can open yourself."

### 0:35 – 1:05 · The shape of it — the two boundaries

**Screen:** scroll down to the architecture diagram. Let it sit still on screen. Trace the
top dashed line, then the bottom one, with the cursor as you talk.

**Say:**
> "This is the whole system on one screen, and I want to point at two lines in particular.
>
> Along the middle are the seven stages, running on my laptop. Above the top dashed line is the internet. Below the bottom dashed line is the public blockchain.
>
> The only thing that ever crosses that top line is a cropped face region — not my original photo. And the only thing that ever crosses the bottom line is four 32-byte fingerprints. My original image, the face data itself, and the full evidence file never cross either line.
>
> That's the design in one picture. Everything after this is me actually running it."

### 1:05 – 1:25 · The consent gate

**Do:** run the pipeline **without** `--i-have-consent`:

```powershell
python -m faceproof run --image samples\me.jpg --chain sepolia
```

It refuses and exits.

**Say:**
> "First thing you'll see is the tool refusing to run.
>
> Searching the web for someone's face is genuinely easy to misuse, so consent isn't a line in the README here — it's a flag you have to pass, and the program stops without it. I'm running this on my own face, with my own consent. That's the only reason it's about to work."

### 1:25 – 2:15 · Stage 1 and 2 — the face

**Do:**

```powershell
python -m faceproof scan --image samples\me.jpg
```

Then open `out/scan_<id>/annotated.jpg` so the bounding box is on screen.

**Say:**
> "Two things happen here.
>
> First, before anything touches the image, it takes a SHA-256 hash of the original file. A hash is basically a fingerprint of a file — same file gives the same fingerprint every time, change a single byte and the fingerprint is completely different, and you can't run it backwards to recover the file. That's the whole trick this project is built on. It also strips the EXIF metadata off a working copy, because EXIF can carry GPS coordinates and your camera's serial number.
>
> Second, it finds the face. RetinaFace draws the box you can see here, then ArcFace turns that face into an embedding — a list of 512 numbers that describes the geometry of the face. Two photos of the same person land close together in that number space, even in different lighting or at a different angle.
>
> And here's the privacy decision I want to flag. That embedding is biometric data. It never leaves this machine and it never goes on the blockchain. What goes on the chain is a SHA-256 of it, which is irreversible — you cannot rebuild my face from it. There's a test in the suite that fails if anyone ever adds the raw vector to the evidence bundle."

### 2:15 – 3:45 · Stage 3 — the live search

**Do:**

```powershell
python -m faceproof search --scan <scan_id> --provider serpapi
```

Let it run. Scroll the provider output / candidate list while it works.

**Say:**
> "Now the search. This is a live Google Lens call going out right now — nothing is cached, nothing is hardcoded, nothing was picked in advance. If I ran this again tomorrow I'd get different results, which is exactly what the brief was asking for.
>
> One thing worth explaining, because it's the piece people usually ask about. Google Lens has no official public API — there's no endpoint Google will sell you. So I go through SerpApi, which runs the Lens query and hands the results back as structured JSON. The alternative is scraping Google's HTML directly, which breaks the moment they change their markup — and I've actually got that as a backup provider in the repo, using headless Chromium, precisely so this doesn't depend on one paid service.
>
> But I want to be precise about what SerpApi is doing here: it is plumbing. It runs a real Google Lens search and delivers the answer. It does no face recognition of its own — none of these providers do. What comes back is 'pages containing a visually similar image', and that is a much weaker claim than 'this is the same person.' Closing that gap is the next stage, and it's the part of this project I actually care about.
>
> There's also a small honest detail here. The search API needs a URL it can fetch, not a file upload — so the tool briefly puts the cropped face region, not my original photo, on a temporary public host. That's a real exposure, and rather than hide it, the exact URL gets written into the audit trail inside the evidence file.
>
> [while it runs] So what comes back is a list of candidates. Notice I'm saying candidates, not matches."

### 3:45 – 4:35 · Stage 4 — why the search result isn't trusted

**Screen:** the re-rank table — every candidate, its cosine score, rejects and the accepted hit.

**Say:**
> "This is the part I'd point at if you only watch thirty seconds of this video.
>
> A reverse image search answers the question 'what looks similar to this picture?' That is not the same question as 'is this the same person?' Search engines match backgrounds, clothes, colours, whole-scene features. So I don't trust the result.
>
> Every single candidate the search engine returned gets re-downloaded here, the face is re-detected and re-embedded locally with the same model, and then compared to my probe by cosine similarity — basically, how close those two 512-number descriptions are. Anything under 0.40 is thrown out.
>
> You can see the rejects in this table with their actual scores. This one passed at [X]. And every accept and every reject is recorded with its score, so the decision is auditable — you can disagree with my threshold and see exactly what it changed."

### 4:35 – 4:55 · The real post

**Do:** open the matched `page_url` in the browser.

**Say:**
> "And there's the post. That's a real, live page on the internet, found by the pipeline in the run you just watched — not something I picked out beforehand. That's the 'find at least one real matching social media post' requirement, done."

### 4:55 – 5:25 · Stage 5 — the evidence bundle

**Screen:** `out/ev_<id>.json`, scrolled briefly.

**Say:**
> "Before anything goes on chain, everything gets packed into one evidence bundle: the post URL, the platform, hashes of both images, the similarity score, the threshold I used, which search providers I tried, timestamps.
>
> It's serialized in a strict canonical form — keys sorted, no whitespace — so that the exact same evidence always produces the exact same bytes, on any machine. If I skipped that, the fingerprint would drift between runs and the whole verification step would be meaningless.
>
> And then that whole bundle gets hashed down to one 32-byte number. That number is what goes on the blockchain."

### 5:25 – 6:25 · Stage 6 — the anchor

**Do:**

```powershell
python -m faceproof anchor --evidence <scan_id> --chain sepolia
```

Sepolia blocks are ~12 seconds, so there will be a visible wait. **Talk through it** — this
is the best place in the video to explain what is actually being written.

**Say:**
> "Now I write it to the chain. This is a real transaction on a real public network, so it takes a few seconds to get into a block — let me use that time to say exactly what's being stored, because 'we put it on the blockchain' is usually where these projects get vague.
>
> Three fingerprints go up, not one. The SHA-256 of the evidence bundle, which breaks if anything at all changes. A perceptual hash of the matched image, which survives re-compression — so if Instagram re-encodes a thumbnail, that still lines up. And the hash of the face embedding. Three of them, because with only SHA-256 you can tell that something changed but not what kind of change it was. With all three, I can tell 'someone edited this evidence' apart from 'a CDN re-compressed this image.'
>
> Alongside those, the contract itself writes the block timestamp and my wallet address as the submitter.
>
> What is *not* up there: no image, no embedding, no URL, no name. Only digests. Which means the chain by itself doesn't tell anyone who this is — it only lets someone confirm that a specific bundle existed at a specific time.
>
> [transaction confirms] And there it is — transaction hash, block number, gas used."

### 6:25 – 7:15 · Anyone can check this — the explorer

**Do:** click the explorer link the CLI printed. Then in the browser, go to the contract's
**Contract → Read Contract** tab, call `recordCount()`, then paste the `evidenceHash` into
`verify(bytes32)` and show the returned record.

**Say:**
> "This is the part that matters, and it's why I put this on a public testnet instead of a chain running on my laptop.
>
> This is Etherscan — a public block explorer, nothing to do with me. Here's the transaction I just sent, in a block, permanently. Here's the contract.
>
> And under 'Read Contract', anyone can query it directly in the browser. `recordCount` tells you how many records exist. And if I paste in my evidence hash and call `verify`, the contract hands back the stored record — the three fingerprints, the timestamp, my wallet address.
>
> No wallet needed to do that. No copy of my code. No access to my machine. If you're reviewing this, you can open that URL right now and get the same answer I'm getting. That's the whole point of using a public chain.
>
> And notice what's actually stored — the three fingerprints, a timestamp, an address. That's the bottom boundary from the diagram: only digests made it down here. No image, no URL, no name. The chain on its own can't tell you who this is. It can only confirm that a particular piece of evidence existed at a particular time."

### 7:15 – 7:40 · Stage 7 — re-verification

**Do:**

```powershell
python -m faceproof verify --evidence <scan_id> --chain sepolia
```

→ ✅ **EXACT**

**Say:**
> "Now the re-verification the brief asked for. This recomputes every hash locally from the evidence file, goes and reads the record back off the chain, and compares them.
>
> Exact match, byte for byte. The evidence I have on disk is provably the same evidence I anchored."

### 7:40 – 8:25 · The tamper demo

**Do:**

```powershell
python -m faceproof tamper-demo --evidence <scan_id> --chain sepolia
```

Show the single character it flips, then ❌ **TAMPERED**.

**Say:**
> "And then the interesting half. Let me change the evidence.
>
> One character. That's it — it edits a single character in the bundle and re-verifies against the same on-chain record.
>
> Red. Tampered. The chain doesn't care how small the edit was, because the fingerprint of the modified bundle simply isn't the fingerprint that was anchored.
>
> And I can't quietly fix that by anchoring the corrected version over the top, either — the contract rejects a second anchor for a hash it's already seen, with the original timestamp in the error. The first record wins, permanently. That's deliberate: the first-seen timestamp is the entire claim, so allowing an overwrite would defeat the point of having a registry at all."

### 8:25 – 8:55 · Merkle batching (keep only if you have time)

**Do:**

```powershell
python -m faceproof batch-anchor --evidence "out/ev_*.json" --chain sepolia
```

One root, one transaction, then per-record inclusion proofs verified on chain.

**Say:**
> "One last thing, quickly. Anchoring one record per transaction doesn't scale — if you had a thousand cases you'd pay a thousand times.
>
> So there's a batch mode: it builds a Merkle tree over all the evidence records, and puts just the single root hash on chain in one transaction. Gas is flat no matter how many records you batch. And you can still prove any individual record was part of that batch afterwards, and the contract verifies that proof on chain — that's what's running now."

### 8:55 – 9:15 · Close

**Screen:** switch back to the overview page — scroll to the deployment strip at the top, so
the contract address is the last thing on screen.

**Say:**
> "So, end to end: a face scan goes in, it gets encoded locally, a live search finds candidates, every candidate is independently face-verified instead of trusted, the result is packed into a canonical evidence bundle, and three fingerprints of that bundle are anchored on a public blockchain.
>
> Then I re-verified it against the chain and got an exact match, and I showed you that changing one single character breaks it.
>
> Everything I did is checkable — the contract address and the transaction are in the README, on a public explorer. Repo's linked in the submission. Thanks for watching."

---

## Requirement traceability — say these out loud at least once

The reviewer is checking a list. Make sure each of these is unambiguous in the audio, not
just implied by what's on screen:

| Task requirement | Where it lands in the script | The words that prove it |
|---|---|---|
| Detect and encode a face | 1:25 – 2:15 | "RetinaFace draws the box… ArcFace turns that face into an embedding" |
| Genuine search, not hardcoded | 2:15 – 3:45 | "live Google Lens call going out right now… nothing is hardcoded, nothing was picked in advance" |
| Which search approach, and why | 2:15 – 3:45 | "Google Lens has no official public API… SerpApi runs the query and hands the results back as JSON" |
| At least one **real** matching social post | 4:35 – 4:55 | "that's a real, live page on the internet, found by the pipeline in the run you just watched" |
| Upload post / hash / fingerprint to a blockchain | 5:25 – 6:25 | "three fingerprints go up… a real transaction on a real public network" |
| **Which** blockchain | 0:00 – 0:35 and 6:25 | "Ethereum Sepolia, a public test network" |
| Demonstrate **re-verifying** against the on-chain record | 7:15 – 7:40 | "reads the record back off the chain and compares… exact match, byte for byte" |
| Tamper-evidence is real | 7:40 – 8:25 | "one character… red, tampered" |
| Independently checkable | 6:25 – 7:15 | "you can open that URL right now and get the same answer" |
| Only hashes reach the chain | 0:35 – 1:05 and 6:25 | "the only thing that crosses that bottom line is four 32-byte fingerprints" |
| No biometric data published | 1:25 – 2:15 | "it never goes on the blockchain… you cannot rebuild my face from it" |
| No website required | 0:00 – 0:35 | "there's no website — the brief said one wasn't needed" |

---

## Recording rules

- Clear the terminal between stages so each screen is readable. Leave the browser alone.
- Two takes. Keep the better one. Don't edit — the brief explicitly says a plain recording is fine.
- **Never cut these five frames:** the live search output, the re-rank table with its scores,
  the Etherscan record, ✅ EXACT, ❌ TAMPERED. Those are the grade.
- Sepolia blocks are ~12 s. Do **not** sit in silence waiting — the anchor explanation at
  5:25 is written to fill exactly that gap. If it confirms early, keep talking anyway.
- Say the contract address out loud once, slowly, or leave it on screen for a few seconds.
- If SerpApi fails mid-take: stop, switch to `--provider yandex` (also SerpApi, different engine)
  or `--provider playwright` (no key, scrapes Lens directly), and restart the take. Do **not**
  silently fall back to the local corpus while recording — if you ever do use `--provider local`,
  say out loud that discovery is an offline index and only the matching is live.
- If the public RPC stalls or the transaction won't confirm: stop and restart the take on
  `--chain local`, and **say** you're on a local node. Never let the audio claim "public
  chain" over a local one.

## After recording

- [ ] Upload (YouTube unlisted / Drive / Loom) → open the link in an **incognito window** to confirm access
- [ ] Put the recording link and the repo link at the top of README.md
- [ ] Open the overview page once in the browser you'll record in, and confirm the diagram
      is fully visible without sideways scrolling at your zoom level
- [ ] Confirm the README states the chain used, how to run it, and the known limitations —
      that is an explicit requirement, not a nicety
- [ ] Confirm `.env` is absent from repo history: `git log --all --full-history -- .env`
- [ ] Push, then submit: https://forms.gle/oZbQGuwiNeHVcHWo8 — **no resubmissions allowed**

---

## Fallback: the local-chain take

If Sepolia is unreachable on the day, everything still works against a local Hardhat node —
it is the identical code path, only the RPC URL differs.

Run `npx hardhat node` in a second terminal, put it where the browser was, and swap every
`--chain sepolia` for `--chain local`. You lose the public explorer, so replace the 6:25
Etherscan segment with `npx hardhat console --network localhost` and call `recordAt(0)` to
read the stored record straight back off the contract.

Then be honest in the voiceover: say it's a local chain, and mention that the same contract
is also deployed publicly at `0xcEcede3653BEf3942F8B7a6c37F7BFc10f7081b7` on Sepolia, which
is in the README. An accurate local demo beats a public demo that stalls on camera.
