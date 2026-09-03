"""Console + HTML reporting.

The CLI is the product here (no website is required by the task), so the
terminal output has to carry the whole story on camera. `rich` is optional --
everything degrades to plain print if it is not installed.
"""

from __future__ import annotations

import html
import json
from pathlib import Path

from . import config
from .verify import EXACT, PERCEPTUAL, TAMPERED, UNANCHORED

try:
    from rich.console import Console
    from rich.panel import Panel
    from rich.table import Table
    _console = Console()
    HAVE_RICH = True
except ImportError:  # pragma: no cover
    _console = None
    HAVE_RICH = False

VERDICT_STYLE = {
    EXACT: ("bold white on green", "[OK]"),
    PERCEPTUAL: ("bold black on yellow", "[~]"),
    TAMPERED: ("bold white on red", "[X]"),
    UNANCHORED: ("bold white on grey37", "[?]"),
}


def out(msg: str = "", style: str | None = None) -> None:
    if HAVE_RICH:
        _console.print(msg, style=style)
    else:
        print(msg)


def rule(title: str) -> None:
    if HAVE_RICH:
        _console.rule(f"[bold cyan]{title}")
    else:
        print(f"\n=== {title} ===")


def stage(n: int, title: str) -> None:
    rule(f"STAGE {n} - {title}")


def kv_panel(title: str, data: dict) -> None:
    if not HAVE_RICH:
        print(f"\n[{title}]")
        for k, v in data.items():
            print(f"  {k}: {v}")
        return
    t = Table.grid(padding=(0, 2))
    t.add_column(style="dim", justify="right")
    t.add_column(style="bold")
    for k, v in data.items():
        t.add_row(str(k), str(v))
    _console.print(Panel(t, title=title, border_style="cyan", expand=False))


def candidate_table(audit: list[dict], threshold: float) -> None:
    """The re-rank table -- the visual proof that the search engine is untrusted."""
    if not HAVE_RICH:
        print(f"\nRe-rank (threshold {threshold}):")
        for a in audit:
            print(f"  {a['similarity']!s:>9}  {a['status']:<26} {a['page_url'][:70]}")
        return

    t = Table(title=f"Adversarial re-rank  (ArcFace cosine, threshold {threshold})",
              header_style="bold cyan", expand=True)
    t.add_column("cos", justify="right", width=7)
    t.add_column("platform", width=14)
    t.add_column("verdict", width=26)
    t.add_column("url", overflow="fold")
    for a in audit:
        sim = a.get("similarity")
        matched = a["status"] == "MATCH"
        style = "bold green" if matched else "dim"
        t.add_row(f"{sim:.3f}" if sim is not None else "-",
                  a.get("platform", ""), a["status"], a["page_url"], style=style)
    _console.print(t)


def verdict_banner(verdict: str, detail: str = "") -> None:
    style, tag = VERDICT_STYLE.get(verdict, ("bold", "[ ]"))
    text = f" {tag}  {verdict} "
    if HAVE_RICH:
        _console.print()
        _console.print(Panel(text, style=style, expand=False))
        if detail:
            _console.print(detail, style="dim")
    else:
        print(f"\n{'=' * 60}\n{text}\n{'=' * 60}")
        if detail:
            print(detail)


def anchor_panel(receipt: dict) -> None:
    data = {
        "network": receipt["network"],
        "chain id": receipt["chain_id"],
        "contract": receipt["contract"],
        "tx hash": receipt["tx_hash"],
        "block": receipt["block"],
        "gas used": f"{receipt['gas_used']:,}",
        "submitter": receipt["submitter"],
    }
    if receipt.get("explorer"):
        data["explorer"] = receipt["explorer"]
    kv_panel("ANCHORED ON CHAIN", data)


# ------------------------------------------------------------------ HTML

_HTML = """<!doctype html>
<meta charset="utf-8"><title>FaceProof case {sid}</title>
<style>
 body{{font:14px/1.6 system-ui,sans-serif;max-width:960px;margin:2rem auto;padding:0 1rem;
      background:#0f1115;color:#e6e8ee}}
 h1{{font-size:1.4rem}} h2{{font-size:1rem;margin-top:2rem;color:#8ab4f8}}
 code,pre{{font-family:ui-monospace,Consolas,monospace}}
 pre{{background:#171a21;padding:1rem;border-radius:8px;overflow-x:auto}}
 table{{border-collapse:collapse;width:100%}}
 td,th{{border-bottom:1px solid #2a2f3a;padding:.4rem .6rem;text-align:left;
        vertical-align:top;word-break:break-all}}
 th{{color:#9aa4b8;font-weight:600}}
 .v{{display:inline-block;padding:.3rem .9rem;border-radius:6px;font-weight:700}}
 .EXACT{{background:#1b5e20}} .PERCEPTUAL{{background:#8d6e00}}
 .TAMPERED{{background:#8e1616}} .UNANCHORED{{background:#3a3f4b}}
 a{{color:#8ab4f8}}
</style>
<h1>FaceProof case report <code>{sid}</code></h1>
<p>Verdict: <span class="v {verdict}">{verdict}</span></p>
<h2>Evidence hash</h2><pre>{ehash}</pre>
<h2>Matched post</h2>{match}
<h2>On-chain record</h2>{record}
<h2>Re-rank audit ({n} candidates examined)</h2>{audit}
<h2>Canonical bundle</h2><pre>{bundle}</pre>
"""


def _table(rows: dict) -> str:
    body = "".join(
        f"<tr><th>{html.escape(str(k))}</th><td>{_cell(v)}</td></tr>"
        for k, v in rows.items()
    )
    return f"<table>{body}</table>"


def _cell(v) -> str:
    s = html.escape(str(v))
    if str(v).startswith("http"):
        return f'<a href="{s}" target="_blank" rel="noopener">{s}</a>'
    return s


def write_html(env: dict, result: dict | None = None,
               dest: str | Path | None = None) -> Path:
    sid = env.get("scan_id", "?")
    dest = Path(dest or config.OUT / f"case_{sid}.html")
    verdict = (result or {}).get("verdict", "UNANCHORED")

    audit_rows = env.get("audit", {}).get("candidates", [])
    audit_html = "<table><tr><th>cos</th><th>platform</th><th>verdict</th><th>url</th></tr>"
    for a in audit_rows:
        sim = a.get("similarity")
        audit_html += (
            f"<tr><td>{'-' if sim is None else f'{sim:.3f}'}</td>"
            f"<td>{html.escape(a.get('platform',''))}</td>"
            f"<td>{html.escape(a.get('status',''))}</td>"
            f"<td>{_cell(a.get('page_url',''))}</td></tr>"
        )
    audit_html += "</table>"

    rec = (result or {}).get("record")
    dest.write_text(_HTML.format(
        sid=html.escape(sid),
        verdict=html.escape(verdict),
        ehash=html.escape(env.get("evidence_hash", "")),
        match=_table(env["bundle"]["match"]),
        record=_table(rec) if rec else "<p>Not anchored.</p>",
        n=len(audit_rows),
        audit=audit_html,
        bundle=html.escape(json.dumps(env["bundle"], indent=2, ensure_ascii=False)),
    ), encoding="utf-8")
    return dest
