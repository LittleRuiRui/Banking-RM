from __future__ import annotations

import argparse
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_INPUT = ROOT / "data" / "kdb_public_snapshot.json"
DEFAULT_OUTPUT = ROOT / "reports" / "kdb_auto_brief.md"


def fmt_pct(v): return "n/a" if v is None else f"{v:.2f}%"
def fmt_bn(v): return "n/a" if v is None else f"US${v:g}bn"
def source_name(s,k): return (s.get("metric_sources",{}).get(k) or {}).get("name","n/a")
def method(s,k): return (s.get("metric_evidence",{}).get(k) or {}).get("method","extracted")
def provenance(s,k):
    ev=s.get("metric_evidence",{}).get(k,{})
    bits=[f"period {ev.get('reporting_period','unknown')}"]
    if ev.get("page") is not None: bits.append(f"p.{ev['page']}")
    if ev.get("section"): bits.append(ev["section"])
    return "; ".join(bits)


def credit_notes(s):
    m=s["metrics"]; out=[]
    for label,key in (("CET1","cet1_ratio_pct"),("BIS capital ratio","capital_adequacy_ratio_pct"),("NPL ratio","npl_ratio_pct"),("ROE","roe_pct"),("ROA","roa_pct")):
        if m.get(key) is not None:
            suffix=" (derived from audited-summary inputs)" if method(s,key)=="derived" else ""
            out.append(f"{label} {fmt_pct(m[key])}{suffix} — {source_name(s,key)} ({provenance(s,key)}).")
    if m.get("ratings_detected"):
        out.append("Official long-term ratings: "+", ".join(m["ratings_detected"])+". Sovereign linkage and statutory government support remain first-order credit considerations.")
    return out


def discovery_rows():
    return [
        ("12–18m FX funding pipeline","How are you thinking about benchmark issuance versus opportunistic/private placements over the next 12–18 months?","Has USD versus EUR or other currencies become more or less attractive?","timing, size, tenor, currency, prefunding","DCM / bilateral / FX-CCS"),
        ("Refinancing / maturity management","Which parts of the maturity profile are taking most attention over the next year or so?","Are you prefunding any of that?","maturity wall, liquidity buffer, market-window constraints","DCM / money market"),
        ("High long-end USD yields","Has the current long-end USD rate environment changed tenor or timing?","Are shorter-dated or alternative-currency markets becoming more relevant?","tenor compression, currency diversification, hedge economics","FX-CCS / alternative-currency issuance"),
        ("ASEAN / overseas pipeline","Are you seeing more Korean corporate financing activity in the US, or is Southeast Asia becoming more active?","Which countries and sectors are taking most attention?","country, sector, sponsor, ticket size","PF / syndication / guarantees"),
        ("Partner-bank need","Where is international-bank participation most useful in KDB-led financings?","Is the need mainly balance sheet, distribution, local network or execution?","specific gaps","syndication / risk participation"),
        ("Wallet allocation criteria","For recent offshore transactions, what mattered most when selecting banking partners?","Has that changed from last year?","price, balance sheet, distribution, network, execution certainty","position the pitch"),
    ]


def evidence_rows(s):
    labels={"cet1_ratio_pct":"CET1","capital_adequacy_ratio_pct":"BIS capital ratio","npl_ratio_pct":"NPL ratio","roe_pct":"ROE","roa_pct":"ROA","gmt_programme_usd_bn":"GMTN","uscp_programme_usd_bn":"USCP","ecp_programme_usd_bn":"ECP","ratings_detected":"Ratings"}
    rows=[]
    for key,ev in s.get("metric_evidence",{}).items():
        snippet=ev.get("evidence_snippet","").replace("|","\\|")
        page="—" if ev.get("page") is None else str(ev["page"])
        rows.append(f"| {labels.get(key,key)} | {ev.get('method','extracted')} | {ev.get('reporting_period','unknown')} | {page} | {ev.get('section') or '—'} | {snippet} |")
    return "\n".join(rows)


def quality_warnings(s):
    flags=s.get("consistency_flags",[])
    if not flags: return "No unresolved cross-metric consistency warnings."
    return "\n".join(f"- **{x.get('severity','warning').upper()} — {x.get('check','check')}:** {x.get('detail','')}" for x in flags)


def rm_intelligence_section(s):
    r=s.get("rm_intelligence") or {}
    if not r: return "RM-intelligence enrichment not available."
    f=r.get("funding_structure",{}); x=r.get("foreign_currency_funding",{}); sec=r.get("sector_exposure",{}); deal=r.get("recent_issuance",{}); out=r.get("funding_outlook",{}); liq=r.get("liquidity_commitment",{})
    lines=[]
    if f:
        lines += ["### Funding structure", f"- Wholesale funding: **{f.get('wholesale_funding_pct','n/a')}%** of funding.", f"- KRW Industrial Finance Bonds: **{f.get('krw_industrial_bonds_pct','n/a')}%**; foreign-currency Industrial Finance Bonds: **{f.get('foreign_currency_industrial_bonds_pct','n/a')}%**.", f"- KRW deposits: **{f.get('krw_deposits_pct','n/a')}%**; foreign-currency deposits: **{f.get('foreign_currency_deposits_pct','n/a')}%**; borrowings: **{f.get('borrowings_pct','n/a')}%**."]
    if x:
        lines += ["", "### Foreign-currency funding profile", f"- 2020–2024 foreign-currency bond issuance: **US${x.get('five_year_fx_bond_issuance_usd_bn','n/a')}bn**.", f"- Currency mix: USD **{x.get('usd_share_pct','n/a')}%**, BRL {x.get('brl_share_pct','n/a')}%, EUR {x.get('eur_share_pct','n/a')}%, CNH {x.get('cnh_share_pct','n/a')}%, AUD {x.get('aud_share_pct','n/a')}%, CHF {x.get('chf_share_pct','n/a')}%, others {x.get('other_currency_share_pct','n/a')}%.", f"- Typical annual benchmark strategy: **{x.get('benchmark_bonds_per_year_min','n/a')}–{x.get('benchmark_bonds_per_year_max','n/a')} USD/EUR benchmark bonds**, typical size **US${x.get('benchmark_size_usd_bn_min','n/a')}–{x.get('benchmark_size_usd_bn_max','n/a')}bn**."]
    if out:
        lines += [f"- 2025 total funding target: **US${out.get('2025_total_funding_target_usd_bn_equiv','n/a')}bn equivalent**."]
    if liq:
        lines += [f"- Liquidity commitment: about **{liq.get('usd_benchmarks_per_year','n/a')} USD benchmarks/year**; more than **{liq.get('usd_public_trade_investors_2024_min','n/a')} investors** bought 2024 USD public trades."]
    if deal:
        tr=", ".join(f"{z['tenor']} {z['type']} US${z['size_usd_bn']:g}bn" for z in deal.get("tranches",[]))
        lines += ["", "### Recent issuance example", f"- 23 Jan 2025: **US${deal.get('total_size_usd_bn','n/a')}bn** senior unsecured transaction — {tr}."]
    if sec:
        lines += ["", "### Operating / sector exposure", f"- Manufacturing **{sec.get('manufacturing_pct','n/a')}%**; Finance & Insurance **{sec.get('finance_insurance_pct','n/a')}%**; Transportation **{sec.get('transportation_pct','n/a')}%**; Utilities **{sec.get('utilities_pct','n/a')}%**; Others **{sec.get('others_pct','n/a')}%**."]
    signals=r.get("signals",[])
    if signals:
        lines += ["", "### RM signals"]
        for z in signals:
            lines.append(f"- **{z.get('priority','').upper()} — {z.get('type','signal')}:** {z.get('fact')} **RM angle:** {z.get('rm_angle')}")
    return "\n".join(lines)


def render(s):
    m=s["metrics"]; q=s.get("data_quality",{})
    defs=[("CET1","cet1_ratio_pct",fmt_pct),("BIS capital ratio","capital_adequacy_ratio_pct",fmt_pct),("NPL ratio","npl_ratio_pct",fmt_pct),("ROE","roe_pct",fmt_pct),("ROA","roa_pct",fmt_pct),("GMTN","gmt_programme_usd_bn",fmt_bn),("USCP","uscp_programme_usd_bn",fmt_bn),("ECP","ecp_programme_usd_bn",fmt_bn)]
    table="\n".join(f"| {label} | {fn(m.get(key))} | {method(s,key)} | {source_name(s,key)} | {provenance(s,key)} |" for label,key,fn in defs)
    credit="\n".join(f"- {x}" for x in credit_notes(s))
    disc="\n".join(f"| {a} | {b} | {c} | {d} | {e} |" for a,b,c,d,e in discovery_rows())
    sources="\n".join(f"- [{x['name']}]({x['url']}) — {x['kind']} — period {x.get('reporting_period','unknown')}" for x in s["sources"])
    return f"""# KDB RM Intelligence Brief — Auto-generated prototype
**Generated:** {s['generated_at']}  
**Client:** {s['client']}  
**Reliability:** {q.get('reliability_score_out_of_10','n/a')}/10  
**Coverage:** {q.get('coverage_pct','n/a')}%

> Reliability and coverage are separate. Derived values are labelled; official-source contradictions are surfaced rather than silently reconciled.

## 1. Credit Intelligence
| Metric | Value | Method | Source | Provenance |
|---|---:|---|---|---|
{table}

### RM interpretation
{credit}

### Data-quality warnings
{quality_warnings(s)}

## 2. RM Business Intelligence
{rm_intelligence_section(s)}

## 3. Evidence ledger
| Fact | Method | Reporting period | Page | Section | Evidence / formula inputs |
|---|---|---|---:|---|---|
{evidence_rows(s)}

## 4. Opportunity Intelligence
### Offshore funding / DCM
Recurring international funding creates DCM, bond-investment, bilateral, money-market and FX/CCS opportunities. **Trigger:** benchmark issuance, maturity concentration, funding-cost or currency-mix shift.

### Cross-border project / syndicated finance
KDB's policy mandate and Korean corporate franchise can create overseas financing pipelines. **Trigger:** Korean corporate outbound project, policy-finance programme, ASEAN/US expansion.

### Relationship diversification
Discover what KDB actually values when allocating wallet to external banks. **Trigger:** change in preferred counterparties, regions, currencies or product mix.

## 5. Meeting Discovery Playbook
| Objective | Opening question | Follow-up | Listen for | Potential angle |
|---|---|---|---|---|
{disc}

## 6. RM next action
1. Pick only 2–3 discovery objectives.
2. Start from one verified public fact.
3. Record timing / size / currency / sector / geography / decision maker / incumbent bank / next step.
4. Convert each answer into Monitor / Internal follow-up / Pitch / No action.
5. Do not use a metric carrying a consistency warning in a credit decision until manually verified.

## 7. Sources
{sources}
"""


def main():
    p=argparse.ArgumentParser(); p.add_argument("--input",type=Path,default=DEFAULT_INPUT); p.add_argument("--output",type=Path,default=DEFAULT_OUTPUT); a=p.parse_args()
    s=json.loads(a.input.read_text()); a.output.parent.mkdir(parents=True,exist_ok=True); a.output.write_text(render(s)); print(f"Wrote {a.output}")


if __name__=="__main__": main()
