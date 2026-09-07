"""FaceProof command line.

    faceproof run --image samples/me.jpg --chain base-sepolia --i-have-consent

Stages can also be driven one at a time (scan / search / anchor / verify),
which is what the demo recording does so each step is visible on camera.
"""

from __future__ import annotations

import argparse
import glob
import json
import sys
from pathlib import Path

import numpy as np

from . import __version__, config, evidence, face, ingest, merkle, report
from .rerank import rerank
from .search.base import CASCADE_ORDER, cascade, get_provider

CONSENT_NOTE = (
    "Refusing to run without --i-have-consent.\n"
    "FaceProof searches the open web for a person's face. Only run it on your own\n"
    "face, on a subject who has agreed, or on a public figure's public posts.\n"
    "Searching for a private individual without consent is a GDPR and platform-ToS\n"
    "problem, and it is not what this tool is for."
)


# ---------------------------------------------------------------- helpers

def _scan_paths(scan_id: str) -> tuple[Path, Path]:
    return (config.OUT / f"scan_{scan_id}.json",
            config.OUT / f"scan_{scan_id}" / "embedding.npy")


def _load_scan(arg: str) -> tuple[dict, np.ndarray]:
    p = Path(arg)
    if not p.is_file():
        p = config.OUT / f"scan_{arg}.json"
    if not p.is_file():
        raise SystemExit(f"no scan found: {arg}")
    scan = json.loads(p.read_text(encoding="utf-8"))
    emb = np.load(config.OUT / f"scan_{scan['scan_id']}" / "embedding.npy")
    return scan, emb


def _load_env(arg: str) -> tuple[dict, Path]:
    p = Path(arg)
    if not p.is_file():
        p = config.OUT / f"ev_{arg}.json"
    if not p.is_file():
        raise SystemExit(f"no evidence bundle found: {arg}")
    return evidence.load(p), p


# ---------------------------------------------------------------- stages

def do_scan(args) -> dict:
    report.stage(1, "INGEST")
    probe = ingest.ingest(args.image, scan_id=getattr(args, "scan_id", None))
    report.kv_panel("PROBE", {
        "scan id": probe["scan_id"],
        "source": probe["source_path"],
        "bytes": f"{probe['bytes']:,}",
        "sha256": probe["sha256"],
        "pHash": probe["phash"],
    })

    report.stage(2, "FACE DETECTION + ENCODING")
    enc = face.encode(probe["clean_path"])
    probe.update({
        "bbox": enc["bbox"],
        "det_score": enc["det_score"],
        "faces_in_image": enc["faces_in_image"],
        "embedding_hash": enc["embedding_hash"],
    })

    workdir = Path(probe["workdir"])
    np.save(workdir / "embedding.npy", enc["embedding"])
    probe["crop_path"] = face.save_probe_crop(
        probe["clean_path"], enc["bbox"], workdir / "probe_crop.jpg")
    probe["annotated_path"] = face.save_annotated(
        probe["clean_path"], enc["bbox"], enc["det_score"], workdir / "annotated.jpg")

    head = ", ".join(f"{v:+.4f}" for v in enc["embedding"][:8])
    report.kv_panel("FACE", {
        "model": f"insightface/{config.INSIGHTFACE_MODEL} (RetinaFace + ArcFace)",
        "faces found": enc["faces_in_image"],
        "bbox": enc["bbox"],
        "det score": f"{enc['det_score']:.4f}",
        "embedding": f"512-d, L2-normalized  [{head}, ...]",
        "embedding hash": enc["embedding_hash"],
        "annotated": probe["annotated_path"],
        "search crop": probe["crop_path"],
    })
    report.out("Raw embedding stays local. Only its SHA-256 is ever published.",
               style="dim italic")

    out_path = config.OUT / f"scan_{probe['scan_id']}.json"
    out_path.write_text(json.dumps(probe, indent=2), encoding="utf-8")
    report.out(f"\nscan saved -> {out_path}", style="dim")
    return probe


def do_search(args, probe: dict | None = None, emb: np.ndarray | None = None) -> dict:
    if probe is None:
        probe, emb = _load_scan(args.scan)

    report.stage(3, "WEB / SOCIAL SEARCH")
    crop = probe.get("crop_path") or probe["clean_path"]

    if args.provider:
        p = get_provider(args.provider)
        if not p.available():
            raise SystemExit(
                f"provider {args.provider!r} unavailable (missing API key or dependency)")
        report.out(f"provider: {p.name}")
        candidates = p.search(crop, limit=args.limit)
        trace = [{"provider": p.name, "status": "ok", "count": len(candidates)}]
    else:
        report.out(f"cascade: {' -> '.join(CASCADE_ORDER)}")
        candidates, trace = cascade(crop, limit=args.limit)

    for t in trace:
        report.out(f"  {t.get('provider'):<24} {t.get('status'):<12} "
                   f"{t.get('count', t.get('detail', ''))}", style="dim")
    if not candidates:
        raise SystemExit("no candidates returned by any provider")
    report.out(f"\n{len(candidates)} candidate(s) returned. "
               f"None is trusted yet.", style="bold")

    report.stage(4, "ADVERSARIAL RE-RANK (face-verify every candidate)")
    hits, audit = rerank(emb, candidates, threshold=args.threshold,
                         social_only=not args.any_domain)
    report.candidate_table(audit, args.threshold or config.FACE_MATCH_THRESHOLD)

    if not hits:
        raise SystemExit(
            "no candidate passed face verification.\n"
            "Try: --any-domain, a lower --threshold, a different --provider, "
            "or a probe image with a larger public footprint.")

    best = hits[0]
    report.kv_panel("VERIFIED MATCH", {
        "post": best["page_url"],
        "platform": best["platform"],
        "image": best["image_url"],
        "cosine": f"{best['similarity']:.4f}  (threshold "
                  f"{args.threshold or config.FACE_MATCH_THRESHOLD})",
        "image sha256": best["image_sha256"],
        "image pHash": best["image_phash"],
        "retrieved": best["retrieved_at"],
    })

    report.stage(5, "EVIDENCE BUNDLE")
    bundle = evidence.build_bundle(
        probe, best, trace, audit,
        args.threshold or config.FACE_MATCH_THRESHOLD)
    env = evidence.envelope(bundle, trace, audit, probe["scan_id"])
    path = evidence.save(env)
    report.kv_panel("EVIDENCE", {
        "canonical bytes": f"{len(evidence.canonical(bundle)):,}",
        "evidence hash": env["evidence_hash"],
        "saved": str(path),
    })
    return env


def do_anchor(args, env: dict | None = None, env_path: Path | None = None) -> dict:
    from .chain import Chain, ChainError

    if env is None:
        env, env_path = _load_env(args.evidence)

    report.stage(6, "BLOCKCHAIN ANCHOR")
    chain = Chain(args.chain)
    report.kv_panel("CHAIN", {
        "network": f"{chain.label} ({chain.network})",
        "chain id": chain.chain_id,
        "contract": chain.address,
        "submitter": chain.acct.address,
        "balance": f"{chain.balance_eth():.6f} ETH",
    })

    b = env["bundle"]
    try:
        receipt = chain.anchor(
            env["evidence_hash"], b["match"]["image_phash"],
            b["match"]["embedding_hash"], cid=args.cid or "")
    except ChainError as e:
        if "revert" in str(e).lower():
            existing = chain.verify(env["evidence_hash"])
            if existing:
                report.out("Already anchored - the contract refuses to overwrite a "
                           "first-seen timestamp.", style="yellow")
                report.kv_panel("EXISTING RECORD", existing)
                return env
        raise SystemExit(str(e))

    env["anchor"] = receipt
    evidence.save(env, env_path)
    report.anchor_panel(receipt)
    return env


def do_verify(args, env: dict | None = None) -> dict:
    from . import verify as V

    if env is None:
        env, _ = _load_env(args.evidence)

    report.stage(7, "RE-VERIFICATION AGAINST CHAIN")
    result = V.run(env, args.chain, live_refetch=args.live_refetch)

    report.kv_panel("COMPARISON", {
        "stored hash": result["stored_hash"],
        "recomputed": result["recomputed_hash"],
        "drift": "YES - bundle was edited" if result["hash_drift"] else "none",
        "on chain": (result["record"] or {}).get("evidenceHash", "<not found>"),
    })
    if result["record"]:
        report.kv_panel("ON-CHAIN RECORD", {
            "evidenceHash": result["record"]["evidenceHash"],
            "pHash": result["record"]["pHash"],
            "embeddingHash": result["record"]["embeddingHash"],
            "timestamp": result["record"]["timestamp"],
            "submitter": result["record"]["submitter"],
        })
    if result["live"]:
        report.kv_panel("LIVE RE-FETCH", result["live"])

    detail = {
        V.EXACT: "Recomputed hash matches the on-chain record byte for byte.",
        V.PERCEPTUAL: "Bytes changed (re-encode), but the image is perceptually and "
                      "semantically the same.",
        V.TAMPERED: "The bundle no longer matches what was anchored.",
        V.UNANCHORED: "No record on chain for this evidence hash.",
    }[result["verdict"]]
    report.verdict_banner(result["verdict"], detail)
    return result


def do_run(args) -> None:
    if not args.i_have_consent:
        raise SystemExit(CONSENT_NOTE)
    probe = do_scan(args)
    emb = np.load(Path(probe["workdir"]) / "embedding.npy")
    env = do_search(args, probe, emb)
    env = do_anchor(args, env, config.OUT / f"ev_{env['scan_id']}.json")
    if env.get("anchor"):
        do_verify(args, env)
    if args.html:
        from . import verify as V
        res = V.run(env, args.chain)
        p = report.write_html(env, res)
        report.out(f"\ncase report -> {p}", style="dim")


def do_tamper_demo(args) -> None:
    """Change one character of the evidence and watch the chain reject it."""
    env, _ = _load_env(args.evidence)
    if not env.get("anchor"):
        raise SystemExit("bundle is not anchored yet - run `faceproof anchor` first")

    report.rule("TAMPER DEMO")
    field = args.field
    original = env["bundle"]["match"].get(field, "")
    if not original:
        raise SystemExit(f"field {field!r} is empty; pick another with --field")

    # flip exactly one character
    i = len(original) // 2
    ch = original[i]
    swapped = "0" if ch != "0" else "1"
    tampered_value = original[:i] + swapped + original[i + 1:]

    report.kv_panel("SINGLE-CHARACTER EDIT", {
        "field": f"match.{field}",
        "before": original,
        "after": tampered_value,
        "position": i,
    })

    env["bundle"]["match"][field] = tampered_value
    env["evidence_hash"] = evidence.recompute(env)
    path = config.OUT / f"ev_{env['scan_id']}_TAMPERED.json"
    evidence.save(env, path)
    report.out(f"tampered copy -> {path}", style="dim")

    args.live_refetch = False
    result = do_verify(args, env)
    if result["verdict"] != "TAMPERED":
        report.out("WARNING: expected TAMPERED. Check that the bundle was anchored "
                   "on this same chain.", style="bold red")


def do_batch_anchor(args) -> None:
    from .chain import Chain

    paths = sorted({p for pat in args.evidence for p in glob.glob(pat)})
    if not paths:
        raise SystemExit("no evidence bundles matched")

    envs = [evidence.load(p) for p in paths]
    leaves = [bytes.fromhex(e["evidence_hash"]) for e in envs]
    root, levels = merkle.build(leaves)

    report.rule("MERKLE BATCH ANCHOR")
    report.kv_panel("TREE", {
        "records": len(leaves),
        "levels": len(levels),
        "root": "0x" + root.hex(),
        "transactions": 1,
    })

    chain = Chain(args.chain)
    receipt = chain.anchor_batch(root, len(leaves), cid=args.cid or "")
    report.anchor_panel(receipt)

    report.out("\nPer-record inclusion proofs verified on chain:", style="bold")
    for i, (p, env) in enumerate(zip(paths, envs)):
        path_proof = merkle.proof(levels, i)
        ok = chain.verify_inclusion(root, leaves[i], path_proof)
        env["anchor"] = {**receipt,
                         "merkle_root": "0x" + root.hex(),
                         "merkle_index": i,
                         "merkle_proof": ["0x" + h.hex() for h in path_proof]}
        evidence.save(env, p)
        mark = "OK " if ok else "FAIL"
        report.out(f"  [{mark}] #{i}  {env['evidence_hash'][:24]}...  "
                   f"proof len {len(path_proof)}",
                   style="green" if ok else "bold red")


def do_report(args) -> None:
    from . import verify as V

    env, _ = _load_env(args.evidence)
    result = None
    if env.get("anchor"):
        try:
            result = V.run(env, args.chain)
        except Exception as e:
            report.out(f"chain unavailable: {e}", style="yellow")
    p = report.write_html(env, result, args.html)
    report.out(f"case report -> {p}")


def do_info(args) -> None:
    report.rule(f"FaceProof v{__version__}")
    rows = {}
    for key in CASCADE_ORDER:
        try:
            p = get_provider(key)
            rows[f"provider:{key}"] = f"{p.name}  {'available' if p.available() else 'unavailable'}"
        except Exception as e:
            rows[f"provider:{key}"] = f"error: {e}"
    for net, cfg in config.CHAINS.items():
        dep = config.deployment_path(net)
        state = ("deployed " + json.loads(dep.read_text())["address"]
                 if dep.is_file() else "not deployed")
        # Show which key signs here, and why it might refuse, without ever
        # printing the key itself -- only the address it derives to.
        key = config.private_key_for(net)
        problem = config.key_error(net, key)
        if problem:
            signer = "NO USABLE KEY" if not key else "dev key refused on public net"
        else:
            from eth_account import Account
            signer = Account.from_key(key).address
            if config.is_dev_key(key):
                signer += "  (hardhat dev)"
        rows[f"chain:{net}"] = f"{state}   signer {signer}"
    rows["threshold"] = config.FACE_MATCH_THRESHOLD
    rows["out dir"] = str(config.OUT)
    report.kv_panel("ENVIRONMENT", rows)


# ---------------------------------------------------------------- parser

def build_parser() -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser(
        prog="faceproof",
        description="Face scan -> genuine web/social search -> blockchain-anchored evidence.")
    ap.add_argument("--version", action="version", version=f"faceproof {__version__}")
    sub = ap.add_subparsers(dest="cmd", required=True)

    def add_chain(p):
        p.add_argument("--chain", default=config.DEFAULT_CHAIN,
                       choices=sorted(config.CHAINS), help="target network")

    def add_search(p):
        p.add_argument("--provider", choices=CASCADE_ORDER,
                       help="force one provider instead of the cascade")
        p.add_argument("--limit", type=int, default=config.SEARCH_LIMIT)
        p.add_argument("--threshold", type=float, default=None,
                       help=f"ArcFace cosine cutoff (default {config.FACE_MATCH_THRESHOLD})")
        p.add_argument("--any-domain", action="store_true",
                       help="do not restrict matches to social platforms")

    p = sub.add_parser("scan", help="stage 1-2: ingest + encode a face")
    p.add_argument("--image", required=True)
    p.set_defaults(fn=do_scan)

    p = sub.add_parser("search", help="stage 3-5: search, re-rank, build evidence")
    p.add_argument("--scan", required=True, help="scan id or path to scan_*.json")
    add_search(p)
    p.set_defaults(fn=do_search)

    p = sub.add_parser("anchor", help="stage 6: anchor an evidence bundle on chain")
    p.add_argument("--evidence", required=True)
    p.add_argument("--cid", default="", help="optional IPFS CID of the full bundle")
    add_chain(p)
    p.set_defaults(fn=do_anchor)

    p = sub.add_parser("verify", help="stage 7: re-verify against the chain")
    p.add_argument("--evidence", required=True)
    p.add_argument("--live-refetch", action="store_true",
                   help="re-download the post image and compare fingerprints")
    add_chain(p)
    p.set_defaults(fn=do_verify)

    p = sub.add_parser("batch-anchor", help="Merkle-batch many bundles into one tx")
    p.add_argument("--evidence", nargs="+", required=True, help="paths or globs")
    p.add_argument("--cid", default="")
    add_chain(p)
    p.set_defaults(fn=do_batch_anchor)

    p = sub.add_parser("tamper-demo", help="edit one character, prove the chain notices")
    p.add_argument("--evidence", required=True)
    p.add_argument("--field", default="title",
                   choices=["title", "page_url", "image_sha256", "image_phash"])
    add_chain(p)
    p.set_defaults(fn=do_tamper_demo, live_refetch=False)

    p = sub.add_parser("run", help="full pipeline end to end")
    p.add_argument("--image", required=True)
    p.add_argument("--i-have-consent", action="store_true",
                   help="required: confirm you may search for this face")
    p.add_argument("--cid", default="")
    p.add_argument("--html", nargs="?", const=True, default=None,
                   help="also write an HTML case report")
    p.add_argument("--live-refetch", action="store_true")
    add_search(p)
    add_chain(p)
    p.set_defaults(fn=do_run)

    p = sub.add_parser("report", help="write an HTML case report")
    p.add_argument("--evidence", required=True)
    p.add_argument("--html", default=None)
    add_chain(p)
    p.set_defaults(fn=do_report)

    p = sub.add_parser("info", help="show providers, chains and thresholds")
    p.set_defaults(fn=do_info)

    return ap


def main(argv=None) -> int:
    args = build_parser().parse_args(argv)
    try:
        args.fn(args)
    except KeyboardInterrupt:
        report.out("\ninterrupted", style="yellow")
        return 130
    except SystemExit:
        raise
    except Exception as e:
        report.out(f"\n{type(e).__name__}: {e}", style="bold red")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
