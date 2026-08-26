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
        ("2026 FX funding plan","The December presentation shows 2025 funding was essentially completed. What has changed in the 2026 funding plan versus last year?","Which currencies and tenors look most attractive now?","size, timing, currency, tenor, prefunding","DCM / bilateral / FX-CCS"),
        ("Refinancing / maturity management","Which parts of the maturity profile are taking most attention over the next year or so?","Are you prefunding any of that?","maturity wall, liquidity buffer, market-window constraints","DCM / money market"),
        ("Funding diversification","USD was still the largest share of foreign-currency bonds outstanding. Has the relative value of USD versus EUR, GBP or AUD changed for you?","Would you swap alternative-currency issuance back, or retain natural exposure?","cross-currency basis, investor demand, natural hedge","FX-CCS / alternative-currency issuance"),
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
    f=r.get("funding_structure",{}); sec=r.get("sector_exposure",{}); strat=r.get("funding_strategy",{}); track=r.get("funding_track_record",{}); liq=r.get("liquidity_commitment",{}); out=r.get("outstanding_funding",{}); deal=r.get("recent_issuance",{}); fresh=r.get("freshness",{})
    lines=[]
    if fresh:
        state=fresh.get("status","unknown").upper()
        lines += ["### Freshness", f"- Latest configured core IR presentation: **{fresh.get('latest_core_ir_publication','unknown')}** — **{state}** ({fresh.get('age_days_approx','n/a')} days approx.).", f"- Policy: {fresh.get('policy','')}" ]
    if f:
        lines += ["", "### Funding structure (Dec-2024 operating mix)", f"- Wholesale funding: **{f.get('wholesale_funding_pct','n/a')}%** of funding.", f"- KRW Industrial Finance Bonds: **{f.get('krw_industrial_bonds_pct','n/a')}%**; foreign-currency Industrial Finance Bonds: **{f.get('foreign_currency_industrial_bonds_pct','n/a')}%**.", f"- KRW deposits: **{f.get('krw_deposits_pct','n/a')}%**; foreign-currency deposits: **{f.get('foreign_currency_deposits_pct','n/a')}%**; borrowings: **{f.get('borrowings_pct','n/a')}%**."]
    if strat or liq:
        lines += ["", "### Funding strategy", f"- Benchmark cadence: **{strat.get('benchmark_bonds_per_year_min',liq.get('benchmark_bonds_per_year_min','n/a'))}–{strat.get('benchmark_bonds_per_year_max',liq.get('benchmark_bonds_per_year_max','n/a'))} USD/EUR benchmarks annually**.", f"- Post-SSA average benchmark tranche: **US${liq.get('post_ssa_avg_tranche_usd_bn','n/a')}bn**.", f"- Relationship bank loans are explicitly described as a backstop funding source: **{'yes' if strat.get('bank_loans_as_backstop') else 'not confirmed'}**."]
    if track or out:
        lines += ["", "### 2025 funding execution / outstanding bonds", f"- 2025 funding target: **US${out.get('2025_target_usd_bn_equiv',track.get('2025_target_usd_bn_equiv','n/a'))}bn equivalent**; achieved by 2 Dec 2025: **US${out.get('2025_achieved_usd_bn','n/a')}bn**.", f"- 2025 mix: public offerings **US${out.get('2025_public_offerings_usd_bn','n/a')}bn**, private placements **US${out.get('2025_private_placement_usd_bn','n/a')}bn**, bank loans **US${out.get('2025_bank_loans_usd_bn','n/a')}bn**.", f"- Foreign-currency bonds outstanding: **US${out.get('foreign_currency_bonds_outstanding_usd_bn_equiv','n/a')}bn equivalent**; USD **{out.get('usd_share_pct','n/a')}%**, EUR {out.get('eur_share_pct','n/a')}%, BRL {out.get('brl_share_pct','n/a')}%, AUD {out.get('aud_share_pct','n/a')}%, GBP {out.get('gbp_share_pct','n/a')}%, others {out.get('other_currency_share_pct','n/a')}%."]
    if deal:
        tr=", ".join(f"{z['tenor']} {z['type']} US${z['size_usd_bn']:g}bn" for z in deal.get("tranches",[]))
        lines += ["", "### Recent issuance example", f"- 23 Jan 2025: **US${deal.get('total_size_usd_bn','n/a')}bn** senior unsecured transaction — {tr}."]
    if sec:
        lines += ["", "### Operating / sector exposure (Dec-2024)", f"- Manufacturing **{sec.get('manufacturing_pct','n/a')}%**; Finance & Insurance **{sec.get('finance_insurance_pct','n/a')}%**; Transportation **{sec.get('transportation_pct','n/a')}%**; Utilities **{sec.get('utilities_pct','n/a')}%**; Public Administration **{sec.get('public_admin_pct','n/a')}%**; Others **{sec.get('others_pct','n/a')}%**."]
    signals=r.get("signals",[])
    if signals:
        lines += ["", "### RM signals"]
        for z in signals: lines.append(f"- **{z.get('priority','').upper()} — {z.get('type','signal')}:** {z.get('fact')} **RM angle:** {z.get('rm_angle')}")
    return "\n".join(lines)


def render(s):
    m=s["metrics"]; q=s.get("data_quality",{})
    defs=[("CET1","cet1_ratio_pct",fmt_pct),("BIS capital ratio","capital_adequacy_ratio_pct",fmt_pct),("NPL ratio","npl_ratio_pct",fmt_pct),("ROE","roe_pct",fmt_pct),("ROA","roa_pct",fmt_pct),("GMTN","gmt_programme_usd_bn",fmt_bn),("USCP","uscp_programme_usd_bn",fmt_bn),("ECP","ecp_programme_usd_bn",fmt_bn)]
    table="\n".join(f"| {label} | {fn(m.get(key))} | {method(s,key)} | {source_name(s,key)} | {provenance(s,key)} |" for label,key,fn in defs)
    credit="\n".join(f"- {x}" for x in credit_notes(s)); disc="\n".join(f"| {a} | {b} | {c} | {d} | {e} |" for a,b,c,d,e in discovery_rows()); sources="\n".join(f"- [{x['name']}]({x['url']}) — {x['kind']} — period {x.get('reporting_period','unknown')}" for x in s["sources"])
    return f"""# KDB RM Intelligence Brief — Auto-generated prototype
**Generated:** {s['generated_at']}  
**Client:** {s['client']}  
**Reliability:** {q.get('reliability_score_out_of_10','n/a')}/10  
**Coverage:** {q.get('coverage_pct','n/a')}%

> Reliability and coverage are separate. Derived values are labelled; official-source contradictions are surfaced rather than silently reconciled. Business-intelligence freshness is tracked separately from financial-metric coverage.

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
2. Start from one verified public fact and state its date.
3. Treat stale IR data as context, not as the client's current plan.
4. Record timing / size / currency / sector / geography / decision maker / incumbent bank / next step.
5. Convert each answer into Monitor / Internal follow-up / Pitch / No action.
6. Do not use a metric carrying a consistency warning in a credit decision until manually verified.

## 7. Sources
{sources}
"""


def main():
    p=argparse.ArgumentParser(); p.add_argument("--input",type=Path,default=DEFAULT_INPUT); p.add_argument("--output",type=Path,default=DEFAULT_OUTPUT); a=p.parse_args()
    s=json.loads(a.input.read_text()); a.output.parent.mkdir(parents=True,exist_ok=True); a.output.write_text(render(s)); print(f"Wrote {a.output}")


if __name__=="__main__": main()
