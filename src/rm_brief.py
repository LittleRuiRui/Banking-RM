from __future__ import annotations

import argparse
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_INPUT = ROOT / "data" / "kdb_public_snapshot.json"
DEFAULT_OUTPUT = ROOT / "reports" / "kdb_auto_brief.md"


def fmt_pct(value):
    return "n/a" if value is None else f"{value:.2f}%"


def fmt_bn(value):
    return "n/a" if value is None else f"US${value:g}bn"


def infer_credit(metrics: dict) -> list[str]:
    notes = []
    if metrics.get("cet1_ratio_pct") is not None:
        notes.append(f"CET1 detected at {fmt_pct(metrics['cet1_ratio_pct'])}; verify against the source page before use.")
    else:
        notes.append("CET1 was not confidently extracted; manual verification required.")
    if metrics.get("npl_ratio_pct") is not None:
        notes.append(f"NPL ratio detected at {fmt_pct(metrics['npl_ratio_pct'])}; trend analysis should be added once multi-year data is available.")
    else:
        notes.append("NPL ratio was not confidently extracted; do not infer a figure.")
    notes.append("For KDB, sovereign linkage and government support remain first-order credit considerations alongside capital, asset quality and market access.")
    return notes


def opportunity_rows(metrics: dict) -> list[dict]:
    rows = []
    if any(metrics.get(k) is not None for k in ("gmt_programme_usd_bn", "uscp_programme_usd_bn", "ecp_programme_usd_bn")):
        rows.append({
            "theme": "Offshore funding / DCM",
            "why": "KDB maintains international funding programmes and is a recurring issuer.",
            "products": "DCM, bond investment, bilateral funding, money market, FX/CCS",
            "question": "How are you thinking about the mix between benchmark issuance and opportunistic/private placements over the next 12–18 months?",
        })
    rows.append({
        "theme": "Cross-border project / syndicated finance",
        "why": "KDB's policy mandate and Korean corporate franchise can create overseas financing pipelines.",
        "products": "Project finance, syndication, risk participation, guarantees",
        "question": "Where are you seeing the strongest need for international-bank participation in KDB-led financings?",
    })
    rows.append({
        "theme": "Relationship diversification",
        "why": "The objective is to understand what KDB values when allocating wallet to external banks.",
        "products": "Treasury, deposits, cross-border referrals, transaction banking",
        "question": "For recent offshore transactions, what has mattered most when selecting banking partners: pricing, balance sheet, distribution, or regional network?",
    })
    return rows


def render(snapshot: dict) -> str:
    m = snapshot["metrics"]
    credit = "\n".join(f"- {x}" for x in infer_credit(m))
    opps = "\n".join(
        f"### {i+1}. {o['theme']}\n**Why it matters:** {o['why']}\n\n**Potential products:** {o['products']}\n\n**Discovery question:** {o['question']}"
        for i, o in enumerate(opportunity_rows(m))
    )
    sources = "\n".join(f"- [{s['name']}]({s['url']}) — {s['kind']}" for s in snapshot["sources"])
    return f"""# KDB RM Intelligence Brief — Auto-generated prototype
**Generated:** {snapshot['generated_at']}  
**Client:** {snapshot['client']}

> Prototype note: all extracted figures must be source-verified before external or credit use. Missing values are intentionally left as `n/a` rather than inferred.

## 1. Credit Intelligence

| Metric | Extracted value |
|---|---:|
| CET1 | {fmt_pct(m.get('cet1_ratio_pct'))} |
| Capital adequacy | {fmt_pct(m.get('capital_adequacy_ratio_pct'))} |
| NPL ratio | {fmt_pct(m.get('npl_ratio_pct'))} |
| ROE | {fmt_pct(m.get('roe_pct'))} |
| ROA | {fmt_pct(m.get('roa_pct'))} |
| GMTN programme | {fmt_bn(m.get('gmt_programme_usd_bn'))} |
| USCP programme | {fmt_bn(m.get('uscp_programme_usd_bn'))} |
| ECP programme | {fmt_bn(m.get('ecp_programme_usd_bn'))} |

### RM interpretation
{credit}

## 2. Opportunity Intelligence

{opps}

## 3. Meeting Discovery Playbook

Use three moves:

1. **Ask about change, not static strategy.**  
   Instead of “What is your funding strategy?”, ask “What has changed in how you think about funding mix compared with last year?”
2. **Offer an informed hypothesis that the client can correct.**  
   “My impression is that USD remains core, but diversification has become more important. Is that still fair?”
3. **Move from market → client → implication.**  
   “Long-end USD yields have stayed elevated. Has that changed how you think about tenor? If so, where would you want more support from banking partners?”

## 4. Sources

{sources}
"""


def main():
    parser = argparse.ArgumentParser(description="Render an RM brief from the KDB public snapshot.")
    parser.add_argument("--input", type=Path, default=DEFAULT_INPUT)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()
    snapshot = json.loads(args.input.read_text())
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(render(snapshot))
    print(f"Wrote {args.output}")


if __name__ == "__main__":
    main()
