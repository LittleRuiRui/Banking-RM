from __future__ import annotations

import argparse
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_INPUT = ROOT / "data" / "kdb_public_snapshot.json"
DEFAULT_OUTPUT = ROOT / "reports" / "kdb_auto_brief.md"


def fmt_pct(value): return "n/a" if value is None else f"{value:.2f}%"
def fmt_bn(value): return "n/a" if value is None else f"US${value:g}bn"

def source_name(snapshot,key):
    s=snapshot.get("metric_sources",{}).get(key); return "n/a" if not s else s.get("name","source")

def provenance(snapshot,key):
    ev=snapshot.get("metric_evidence",{}).get(key,{})
    bits=[f"period {ev.get('reporting_period','unknown')}"]
    if ev.get("page") is not None: bits.append(f"p.{ev['page']}")
    if ev.get("section"): bits.append(ev["section"])
    return "; ".join(bits)

def infer_credit(snapshot):
    m=snapshot["metrics"]; notes=[]
    if m.get("cet1_ratio_pct") is not None: notes.append(f"CET1 {fmt_pct(m['cet1_ratio_pct'])} — {source_name(snapshot,'cet1_ratio_pct')} ({provenance(snapshot,'cet1_ratio_pct')}).")
    else: notes.append("CET1 not confidently extracted; manual verification required.")
    if m.get("npl_ratio_pct") is not None: notes.append(f"NPL ratio {fmt_pct(m['npl_ratio_pct'])} — {source_name(snapshot,'npl_ratio_pct')} ({provenance(snapshot,'npl_ratio_pct')}).")
    else: notes.append("NPL ratio not confidently extracted; do not infer a figure.")
    if m.get("ratings_detected"): notes.append("Official long-term ratings detected: "+", ".join(m["ratings_detected"])+". Sovereign linkage and statutory government support remain first-order credit considerations.")
    return notes

def opportunity_rows(m):
    rows=[]
    if any(m.get(k) is not None for k in ("gmt_programme_usd_bn","uscp_programme_usd_bn","ecp_programme_usd_bn")):
        rows.append(("Offshore funding / DCM","Recurring international funding creates DCM, bond-investment, bilateral, money-market and FX/CCS opportunities.","new benchmark issue, maturity concentration, funding-cost or currency-mix shift"))
    rows.append(("Cross-border project / syndicated finance","KDB's policy mandate and Korean corporate franchise can create overseas financing pipelines.","new Korean corporate outbound project, policy-finance programme, ASEAN/US expansion"))
    rows.append(("Relationship diversification","Discover what KDB actually values when allocating wallet to external banks.","change in preferred counterparties, regions, currencies or product mix"))
    return rows

def discovery_rows():
    return [
        ("12–18m FX funding pipeline","How are you thinking about benchmark issuance versus opportunistic/private placements over the next 12–18 months?","Has USD versus EUR or other currencies become more or less attractive?","timing, size, tenor, currency, prefunding","DCM / bilateral / FX-CCS"),
        ("Refinancing / maturity management","Which parts of the maturity profile are taking most attention over the next year or so?","Are you prefunding any of that?","maturity wall, liquidity buffer, market-window constraints","DCM / money market"),
        ("High long-end USD yields","Has the current long-end USD rate environment changed tenor or timing?","Are shorter-dated or alternative-currency markets becoming more relevant?","tenor compression, currency diversification, hedge economics","FX-CCS / alternative-currency issuance"),
        ("ASEAN / overseas pipeline","Are you seeing more Korean corporate financing activity in the US, or is Southeast Asia becoming more active?","Which countries and sectors are taking most attention?","country, sector, sponsor, ticket size","PF / syndication / guarantees"),
        ("Partner-bank need","Where is international-bank participation most useful in KDB-led financings?","Is the need mainly balance sheet, distribution, local network or execution?","specific gaps","syndication / risk participation"),
        ("Wallet allocation criteria","For recent offshore transactions, what mattered most when selecting banking partners?","Has that changed from last year?","price, balance sheet, distribution, network, execution certainty","position the pitch"),
    ]

def evidence_rows(snapshot):
    labels={"cet1_ratio_pct":"CET1","capital_adequacy_ratio_pct":"Capital adequacy","npl_ratio_pct":"NPL ratio","roe_pct":"ROE","roa_pct":"ROA","gmt_programme_usd_bn":"GMTN","uscp_programme_usd_bn":"USCP","ecp_programme_usd_bn":"ECP","ratings_detected":"Ratings"}
    rows=[]
    for key,ev in snapshot.get("metric_evidence",{}).items():
        snippet=ev.get("evidence_snippet","").replace("|","\\|")
        page="—" if ev.get("page") is None else str(ev["page"])
        rows.append(f"| {labels.get(key,key)} | {ev.get('reporting_period','unknown')} | {page} | {ev.get('section') or '—'} | {snippet} |")
    return "\n".join(rows)

def render(snapshot):
    m=snapshot["metrics"]; q=snapshot.get("data_quality",{})
    metric_defs=[("CET1","cet1_ratio_pct",fmt_pct),("Capital adequacy","capital_adequacy_ratio_pct",fmt_pct),("NPL ratio","npl_ratio_pct",fmt_pct),("ROE","roe_pct",fmt_pct),("ROA","roa_pct",fmt_pct),("GMTN","gmt_programme_usd_bn",fmt_bn),("USCP","uscp_programme_usd_bn",fmt_bn),("ECP","ecp_programme_usd_bn",fmt_bn)]
    metric_table="\n".join(f"| {label} | {formatter(m.get(key))} | {source_name(snapshot,key)} | {provenance(snapshot,key)} |" for label,key,formatter in metric_defs)
    credit="\n".join(f"- {x}" for x in infer_credit(snapshot))
    opps="\n".join(f"### {i+1}. {t}\n{why}\n\n**Trigger:** {trig}" for i,(t,why,trig) in enumerate(opportunity_rows(m)))
    discovery="\n".join(f"| {a} | {b} | {c} | {d} | {e} |" for a,b,c,d,e in discovery_rows())
    sources="\n".join(f"- [{s['name']}]({s['url']}) — {s['kind']} — period {s.get('reporting_period','unknown')}" for s in snapshot["sources"])
    return f"""# KDB RM Intelligence Brief — Auto-generated prototype
**Generated:** {snapshot['generated_at']}  
**Client:** {snapshot['client']}  
**Reliability:** {q.get('reliability_score_out_of_10','n/a')}/10  
**Coverage:** {q.get('coverage_pct','n/a')}%

> Reliability and completeness are separate. A blank field is preferable to an unsupported number.

## 1. Credit Intelligence
| Metric | Value | Source | Provenance |
|---|---:|---|---|
{metric_table}

### RM interpretation
{credit}

## 2. Evidence ledger
| Fact | Reporting period | Page | Section | Evidence snippet |
|---|---|---:|---|---|
{evidence_rows(snapshot)}

## 3. Opportunity Intelligence
{opps}

## 4. Meeting Discovery Playbook
| Objective | Opening question | Follow-up | Listen for | Potential angle |
|---|---|---|---|---|
{discovery}

## 5. RM next action
1. Pick only 2–3 discovery objectives.
2. Start from one verified public fact.
3. Record timing / size / currency / sector / geography / decision maker / incumbent bank / next step.
4. Convert each answer into Monitor / Internal follow-up / Pitch / No action.

## 6. Sources
{sources}
"""

def main():
    p=argparse.ArgumentParser(); p.add_argument("--input",type=Path,default=DEFAULT_INPUT); p.add_argument("--output",type=Path,default=DEFAULT_OUTPUT); args=p.parse_args(); snapshot=json.loads(args.input.read_text()); args.output.parent.mkdir(parents=True,exist_ok=True); args.output.write_text(render(snapshot)); print(f"Wrote {args.output}")

if __name__=="__main__": main()
