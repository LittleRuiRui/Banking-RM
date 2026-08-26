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


def source_name(snapshot: dict, key: str) -> str:
    source = snapshot.get("metric_sources", {}).get(key)
    return "n/a" if not source else source.get("name", "source")


def infer_credit(snapshot: dict) -> list[str]:
    metrics = snapshot["metrics"]
    notes = []
    if metrics.get("cet1_ratio_pct") is not None:
        notes.append(
            f"CET1 detected at {fmt_pct(metrics['cet1_ratio_pct'])} from {source_name(snapshot, 'cet1_ratio_pct')}; source date must travel with the fact."
        )
    else:
        notes.append("CET1 was not confidently extracted; manual verification required.")
    if metrics.get("npl_ratio_pct") is not None:
        notes.append(
            f"NPL ratio detected at {fmt_pct(metrics['npl_ratio_pct'])} from {source_name(snapshot, 'npl_ratio_pct')}; do not blend it with older annual-report figures."
        )
    else:
        notes.append("NPL ratio was not confidently extracted; do not infer a figure.")
    if metrics.get("ratings_detected"):
        notes.append(
            "Current-source ratings detected: "
            + ", ".join(metrics["ratings_detected"])
            + ". For KDB, sovereign linkage and statutory government support remain first-order credit considerations alongside capital, asset quality and market access."
        )
    else:
        notes.append("Ratings were not confidently extracted from the current investor source.")
    return notes


def opportunity_rows(metrics: dict) -> list[dict]:
    rows = []
    if any(metrics.get(k) is not None for k in ("gmt_programme_usd_bn", "uscp_programme_usd_bn", "ecp_programme_usd_bn")):
        rows.append({
            "theme": "Offshore funding / DCM",
            "why": "KDB maintains international funding programmes and is a recurring issuer. Funding is therefore both a liquidity topic and a recurring wallet opportunity.",
            "products": "DCM, bond investment, bilateral funding, money market, FX/CCS",
            "trigger": "new benchmark issue, maturity concentration, relative funding-cost shift, or currency-mix change",
        })
    rows.append({
        "theme": "Cross-border project / syndicated finance",
        "why": "KDB's policy mandate and Korean corporate franchise can create overseas financing pipelines where an international bank contributes local balance sheet, distribution or network access.",
        "products": "Project finance, syndication, risk participation, guarantees",
        "trigger": "new Korean corporate outbound project, policy-finance programme, ASEAN/US expansion",
    })
    rows.append({
        "theme": "Relationship diversification",
        "why": "The objective is to discover the criteria KDB actually uses when allocating wallet to external banks, not to assume price is the only driver.",
        "products": "Treasury, deposits, cross-border referrals, transaction banking",
        "trigger": "change in preferred counterparties, regions, currencies or product mix",
    })
    return rows


def discovery_rows() -> list[dict]:
    return [
        {
            "objective": "12–18m foreign-currency funding pipeline",
            "opening": "How are you thinking about the mix between benchmark issuance and more opportunistic/private placements over the next 12–18 months?",
            "probe": "Has the relative attractiveness of USD versus EUR or other currencies changed for you?",
            "listen_for": "timing, size, tenor, currency, prefunding, private placement appetite",
            "angle": "DCM, bilateral funding, bond investment, FX/CCS",
        },
        {
            "objective": "Refinancing pressure / maturity management",
            "opening": "Which parts of the maturity profile are taking most of the team's attention over the next year or so?",
            "probe": "Are you considering prefunding any of that, or waiting for better market windows?",
            "listen_for": "maturity wall, liquidity buffer, timing flexibility, execution constraints",
            "angle": "DCM, money market, bilateral liquidity",
        },
        {
            "objective": "Impact of high long-end USD yields",
            "opening": "Has the current long-end USD rate environment changed how you think about tenor or timing?",
            "probe": "Are shorter-dated or alternative-currency markets becoming more relevant?",
            "listen_for": "tenor compression, currency diversification, hedge economics",
            "angle": "FX/CCS, alternative-currency issuance, deposits",
        },
        {
            "objective": "ASEAN / overseas financing pipeline",
            "opening": "Are you seeing more Korean corporate financing activity in the US, or is Southeast Asia becoming more active?",
            "probe": "Which countries and sectors are taking most of your team's attention?",
            "listen_for": "Indonesia/Vietnam/Singapore, infra, energy, batteries, semis, shipbuilding",
            "angle": "PF, syndication, guarantees, local network support",
        },
        {
            "objective": "Where KDB actually wants partner-bank participation",
            "opening": "Where do you see the greatest need for international-bank participation in KDB-led financings?",
            "probe": "Is the need mainly balance sheet, distribution, local network, or execution capability?",
            "listen_for": "specific gaps rather than generic willingness to collaborate",
            "angle": "Syndication, PF, risk participation, referrals",
        },
        {
            "objective": "Wallet allocation criteria",
            "opening": "For recent offshore transactions, what has mattered most when selecting banking partners: pricing, balance sheet, distribution, or regional network?",
            "probe": "Has that changed compared with last year?",
            "listen_for": "buying criteria, pain points, incumbent-bank strengths/weaknesses",
            "angle": "Position CCB pitch around the actual buying criterion",
        },
        {
            "objective": "Decision maker / stakeholder map",
            "opening": "When you evaluate a new international banking partner, which teams normally need to be comfortable before business can scale?",
            "probe": "Is treasury, funding, the business division or credit usually the key sponsor?",
            "listen_for": "economic buyer, gatekeeper, influencer, approval sequence",
            "angle": "Relationship mapping and next-contact plan",
        },
        {
            "objective": "What changed this year",
            "opening": "What has moved up KDB's priority list this year compared with last year?",
            "probe": "What is driving that change?",
            "listen_for": "new mandate, policy shift, sector priority, geographic push",
            "angle": "Opens the broadest pipeline-discovery path",
        },
    ]


def render(snapshot: dict) -> str:
    m = snapshot["metrics"]
    credit = "\n".join(f"- {x}" for x in infer_credit(snapshot))
    opps = "\n".join(
        f"### {i+1}. {o['theme']}\n**Why it matters:** {o['why']}\n\n**Potential products:** {o['products']}\n\n**Trigger to monitor:** {o['trigger']}"
        for i, o in enumerate(opportunity_rows(m))
    )
    sources = "\n".join(f"- [{s['name']}]({s['url']}) — {s['kind']}" for s in snapshot["sources"])

    metric_rows = [
        ("CET1", fmt_pct(m.get("cet1_ratio_pct")), source_name(snapshot, "cet1_ratio_pct")),
        ("Capital adequacy", fmt_pct(m.get("capital_adequacy_ratio_pct")), source_name(snapshot, "capital_adequacy_ratio_pct")),
        ("NPL ratio", fmt_pct(m.get("npl_ratio_pct")), source_name(snapshot, "npl_ratio_pct")),
        ("ROE", fmt_pct(m.get("roe_pct")), source_name(snapshot, "roe_pct")),
        ("ROA", fmt_pct(m.get("roa_pct")), source_name(snapshot, "roa_pct")),
        ("GMTN programme", fmt_bn(m.get("gmt_programme_usd_bn")), source_name(snapshot, "gmt_programme_usd_bn")),
        ("USCP programme", fmt_bn(m.get("uscp_programme_usd_bn")), source_name(snapshot, "uscp_programme_usd_bn")),
        ("ECP programme", fmt_bn(m.get("ecp_programme_usd_bn")), source_name(snapshot, "ecp_programme_usd_bn")),
    ]
    metric_table = "\n".join(f"| {label} | {value} | {src} |" for label, value, src in metric_rows)

    discovery_table = "\n".join(
        f"| {r['objective']} | {r['opening']} | {r['probe']} | {r['listen_for']} | {r['angle']} |"
        for r in discovery_rows()
    )

    return f"""# KDB RM Intelligence Brief — Auto-generated prototype
**Generated:** {snapshot['generated_at']}  
**Client:** {snapshot['client']}

> Prototype note: extracted figures are only as current as their cited source. Missing values remain `n/a`; historical and current documents are not blended without attribution.

## 1. Credit Intelligence

| Metric | Extracted value | Source used |
|---|---:|---|
{metric_table}

### RM interpretation
{credit}

## 2. Opportunity Intelligence

{opps}

## 3. Meeting Discovery Playbook

### The rule
Do not ask the client to recite information that is already public. Use public facts to form a hypothesis, then use the meeting to discover what is **not** public: changes, timing, priorities, buying criteria, pipeline and decision process.

| What you really want to know | Opening question | Follow-up probe | Listen for | Potential angle |
|---|---|---|---|---|
{discovery_table}

### Three conversation techniques
1. **Ask about change, not static strategy.**  
   Instead of “What is your funding strategy?”, ask “What has changed in how you think about funding mix compared with last year?”
2. **Offer an informed hypothesis that the client can correct.**  
   “My impression is that USD remains core, but diversification has become more important. Is that still fair?”
3. **Move market → client → implication.**  
   “Long-end USD yields have stayed elevated. Has that changed how you think about tenor? If so, where would you want more support from banking partners?”

### Avoid these low-yield questions
- “Can you introduce KDB's strategy?”
- “Do you have any upcoming transactions?”
- “Who are your main banks?”
- “Do you need financing?”

They are too broad, too sales-led, or invite a generic answer.

### Four things the RM should leave the meeting knowing
- What changed in KDB's 12–18 month foreign-currency funding plan?
- Which overseas sectors/geographies are generating the strongest financing pipeline?
- Where does KDB actively want international-bank participation?
- What criteria determine wallet allocation to banking partners?

## 4. Suggested RM next action
1. Pick only **2–3 discovery objectives** for the next meeting; do not ask all eight.
2. Start from one verified public fact so the question feels informed rather than intrusive.
3. Record the answer as structured fields: **timing / size / currency / sector / geography / decision maker / incumbent bank / next step**.
4. Convert each useful answer into either **Monitor**, **Internal follow-up**, **Pitch**, or **No action**.

## 5. Sources

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
