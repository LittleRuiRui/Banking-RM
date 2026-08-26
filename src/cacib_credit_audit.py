from __future__ import annotations

import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CONFIG = ROOT / "config" / "cacib_sources.json"

STALE_RULES = [
    {
        "category": "Current performance",
        "terms": ["revenue", "net income", "nbi", "gross operating income", "operating expenses", "cost of risk", "global markets", "financing", "investment banking", "treasury"],
        "preferred_period": "H1 2026",
        "source_id": "cacib_h1_2026",
    },
    {
        "category": "Detailed financial and risk disclosure",
        "terms": ["total assets", "loans and receivables", "npl", "non-performing", "stage 1", "stage 2", "stage 3", "ecl", "provisions", "rwa", "cet1", "tier 1", "total capital", "leverage", "lcr", "nsfr", "liabilities", "equity", "cash flow", "sector", "geographic"],
        "preferred_period": "FY2025",
        "source_id": "cacib_urd_2025",
    },
    {
        "category": "Current strategy and management commentary",
        "terms": ["strategy", "act2028", "management", "business outlook", "market environment"],
        "preferred_period": "H1 2026",
        "source_id": "cacib_h1_2026",
    },
]

INTERNAL_TERMS = [
    "内部评级", "客户号", "kyc", "aml", "已批", "已用", "未用", "敞口", "国别限额", "集中度", "审批权限", "raroc", "eva", "ftp", "pipeline", "客户综合贡献"
]

ASSUMPTION_TERMS = ["base case", "stress case", "压力测试", "预测", "projection", "assumption"]

ENTITY_PATTERNS = {
    "Credit Agricole Group": [r"credit agricole group", r"cr[ée]dit agricole group"],
    "CASA": [r"credit agricole s\.a\.", r"cr[ée]dit agricole s\.a\.", r"\bcasa\b"],
    "CACIB": [r"credit agricole corporate and investment bank", r"cr[ée]dit agricole corporate and investment bank", r"\bcacib\b"],
    "CACIB Singapore Branch": [r"singapore branch", r"cacib singapore"],
}


def load_registry() -> dict:
    return json.loads(CONFIG.read_text(encoding="utf-8"))


def _compact(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


def _years(window: str) -> list[int]:
    return [int(x) for x in re.findall(r"\b(20\d{2})\b", window)]


def _source_map(registry: dict) -> dict:
    return {s["id"]: s for s in registry.get("sources", [])}


def _entity_hits(text: str) -> list[str]:
    hits = []
    for entity, patterns in ENTITY_PATTERNS.items():
        if any(re.search(p, text, re.I) for p in patterns):
            hits.append(entity)
    return hits


def audit_cacib_application(text: str) -> dict:
    registry = load_registry()
    sources = _source_map(registry)
    compact = _compact(text)
    findings = []

    for rule in STALE_RULES:
        source = sources[rule["source_id"]]
        for term in rule["terms"]:
            for m in re.finditer(re.escape(term), compact, re.I):
                window = compact[max(0, m.start() - 220): min(len(compact), m.end() + 320)]
                years = _years(window)
                if not years:
                    continue
                latest_seen = max(years)
                target_year = 2026 if "2026" in rule["preferred_period"] else 2025
                if latest_seen < target_year:
                    findings.append({
                        "priority": "AMBER",
                        "category": rule["category"],
                        "field_or_term": term,
                        "current_period_seen": str(latest_seen),
                        "preferred_latest_basis": rule["preferred_period"],
                        "recommended_source": source["name"],
                        "source_url": source["url"],
                        "action": "UPDATE / VERIFY",
                        "evidence_window": window[:520],
                    })
                break

    internal_present = [x for x in INTERNAL_TERMS if x.lower() in compact.lower()]
    internal_missing = [x for x in INTERNAL_TERMS if x not in internal_present]
    for field in internal_missing:
        findings.append({
            "priority": "RED",
            "category": "Internal-only control",
            "field_or_term": field,
            "current_period_seen": "not detected",
            "preferred_latest_basis": "current internal system",
            "recommended_source": "INTERNAL CLIENT / INTERNAL POLICY",
            "source_url": "",
            "action": "INTERNAL REQUIRED — DO NOT GUESS",
            "evidence_window": "",
        })

    assumptions = []
    for term in ASSUMPTION_TERMS:
        if term.lower() in compact.lower():
            assumptions.append(term)
    if assumptions:
        findings.append({
            "priority": "AMBER",
            "category": "Analyst assumption",
            "field_or_term": ", ".join(sorted(set(assumptions))),
            "current_period_seen": "model / assumption",
            "preferred_latest_basis": "recalibrate to latest actuals",
            "recommended_source": "ANALYST ASSUMPTION",
            "source_url": "",
            "action": "RECALIBRATE, NOT AUTO-REPLACE",
            "evidence_window": "Base/Stress assumptions must remain visibly separate from reported facts.",
        })

    entities = _entity_hits(compact)
    entity_warning = None
    if len(entities) >= 2:
        entity_warning = (
            "Multiple entities detected. Every financial metric should be tagged to the correct entity. "
            "For this credit subject, branch/client facts belong to CACIB Singapore Branch; consolidated bank metrics belong to CACIB; "
            "CASA/Group data should be used only for parent support or group context. Detected: " + ", ".join(entities)
        )

    # Deduplicate similar rule hits while preserving first evidence occurrence.
    deduped = []
    seen = set()
    for f in findings:
        key = (f["priority"], f["category"], f["field_or_term"], f["current_period_seen"])
        if key in seen:
            continue
        seen.add(key)
        deduped.append(f)

    counts = {"RED": 0, "AMBER": 0, "GREEN": 0}
    for f in deduped:
        counts[f["priority"]] = counts.get(f["priority"], 0) + 1

    return {
        "credit_subject": registry["credit_subject"],
        "entity_hierarchy": registry["entity_hierarchy"],
        "source_taxonomy": registry["source_taxonomy"],
        "source_registry": registry["sources"],
        "entity_scope_warning": entity_warning,
        "findings": deduped,
        "counts": counts,
        "policy": registry["policy"],
        "internal_fields_detected": internal_present,
        "note": "First-pass deterministic audit. It flags stale periods, entity-scope risk, internal-only gaps and analyst assumptions. It does not invent replacement numbers.",
    }


def demo_findings() -> list[dict]:
    """Findings observed from the supplied CACIB credit-application screenshots.

    These are document-review observations, not extracted official financial facts.
    """
    return [
        {"priority": "AMBER", "item": "Asset analysis", "observed": "Balance-sheet discussion still uses 31 Dec 2024", "target": "Use FY2025 URD for latest detailed balance-sheet/risk disclosure"},
        {"priority": "AMBER", "item": "Asset quality", "observed": "NPL / Stage / sector / geography discussion is predominantly 2024", "target": "Refresh from FY2025 URD where comparable detail is available"},
        {"priority": "AMBER", "item": "Liabilities and liquidity", "observed": "Liability structure and maturity discussion uses 2024 figures", "target": "Refresh detailed disclosure to FY2025; retain H1 2026 only where directly comparable"},
        {"priority": "AMBER", "item": "Business-line profitability", "observed": "Several business-line revenue paragraphs still reference 2024", "target": "Use H1 2026 results for current performance and H1-on-H1 comparison"},
        {"priority": "AMBER", "item": "Cash-flow analysis", "observed": "Cash-flow text is based on FY2024", "target": "Use FY2025 URD unless a comparable H1 2026 cash-flow disclosure exists"},
        {"priority": "AMBER", "item": "Base / Stress case", "observed": "CET1 downside assumptions are analyst scenarios", "target": "Recalibrate against latest actual capital position; do not auto-replace scenario assumptions"},
        {"priority": "RED", "item": "Internal controls", "observed": "Limit, KYC, rating, exposure, policy eligibility and approval fields depend on bank systems", "target": "INTERNAL REQUIRED — never infer from public sources"},
        {"priority": "RED", "item": "Entity scope", "observed": "CACIB Singapore Branch, CACIB, CASA and Credit Agricole Group appear in one application", "target": "Tag every metric by entity and prohibit silent substitution across entities"},
    ]
