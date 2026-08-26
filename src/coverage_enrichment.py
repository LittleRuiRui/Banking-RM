from __future__ import annotations

import io
import json
import re
from pathlib import Path

import requests
from pypdf import PdfReader

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_SNAPSHOT = ROOT / "data" / "kdb_public_snapshot.json"
INVESTOR_URL = "https://www.kdb.co.kr/wcmscontents/pdf/KDB_Investor_Presentation_July_2025.pdf"
SOURCE_NAME = "Investor Presentation July 2025"
PERIOD = "2024"
USER_AGENT = "Banking-RM/0.7 coverage-enrichment"


def pdf_pages(url: str = INVESTOR_URL) -> list[str]:
    r = requests.get(url, timeout=60, headers={"User-Agent": USER_AGENT})
    r.raise_for_status()
    return [(p.extract_text() or "") for p in PdfReader(io.BytesIO(r.content)).pages]


def compact(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


def parse_capital_chart(page_text: str) -> dict:
    """Parse the labelled 2018-2024 BIS/Tier-1 chart on the Capital Adequacy page.

    PDF text extraction lists the seven BIS observations followed by the seven Tier-1
    observations, then the seven year labels. We require all labels and all 14 values;
    otherwise nothing is accepted.
    """
    text = compact(page_text)
    if "Capital Adequacy & Recapitalization" not in text or "BIS Capital Ratio Tier 1 Ratio" not in text:
        return {}
    years = re.search(r"2018\s+2019\s+2020\s+2021\s+2022\s+2023\s+2024\s+BIS Capital Ratio Tier 1 Ratio", text)
    if not years:
        return {}
    prefix = text[max(0, years.start() - 220):years.start()]
    vals = [float(x) for x in re.findall(r"(\d{1,2}\.\d)%", prefix)]
    if len(vals) < 14:
        return {}
    vals = vals[-14:]
    bis, tier1 = vals[:7], vals[7:]
    return {
        "years": list(range(2018, 2025)),
        "bis": bis,
        "tier1": tier1,
        "bis_2024": bis[-1],
        "tier1_2024": tier1[-1],
    }


def parse_financial_summary(page_text: str) -> dict:
    """Extract only explicitly labelled 2023/2024 summary items needed for derived ratios."""
    text = compact(page_text)
    if "Financial Statement Summary" not in text or "Key Income Statement Items" not in text:
        return {}

    def last_two(label: str):
        m = re.search(rf"{label}\s+([\d,()]+)\s+([\d,()]+)\s+([\d,()]+)\s+([\d,()]+)\s+([\d,()]+)", text, re.I)
        if not m:
            return None
        def n(s):
            neg = s.startswith("(") and s.endswith(")")
            v = float(s.strip("()").replace(",", ""))
            return -v if neg else v
        values = [n(x) for x in m.groups()]
        return values[-2], values[-1]

    profit = last_two("Profit for the Period")
    assets = last_two("Total Assets")
    equity = last_two("Total Equity")
    if not all((profit, assets, equity)):
        return {}
    return {
        "profit_2024_krw_bn": profit[1],
        "assets_2023_krw_bn": assets[0],
        "assets_2024_krw_bn": assets[1],
        "equity_2023_krw_bn": equity[0],
        "equity_2024_krw_bn": equity[1],
    }


def derived_ratios(fs: dict) -> dict:
    if not fs:
        return {}
    avg_assets = (fs["assets_2023_krw_bn"] + fs["assets_2024_krw_bn"]) / 2
    avg_equity = (fs["equity_2023_krw_bn"] + fs["equity_2024_krw_bn"]) / 2
    return {
        "roa_pct": round(fs["profit_2024_krw_bn"] / avg_assets * 100, 2),
        "roe_pct": round(fs["profit_2024_krw_bn"] / avg_equity * 100, 2),
    }


def source_meta():
    return {"name": SOURCE_NAME, "url": INVESTOR_URL, "kind": "investor_presentation", "trust_score": 90, "reporting_period": PERIOD}


def evidence(page: int, section: str, snippet: str, matched: str, method: str = "extracted"):
    return {
        "source_name": SOURCE_NAME,
        "source_url": INVESTOR_URL,
        "source_kind": "investor_presentation",
        "reporting_period": PERIOD,
        "page": page,
        "section": section,
        "evidence_snippet": compact(snippet),
        "matched_text": matched,
        "method": method,
    }


def enrich(snapshot: dict, pages: list[str]) -> dict:
    # PDF page 13 is index 12; financial summary page 14 is index 13.
    capital = parse_capital_chart(pages[12]) if len(pages) > 12 else {}
    fs = parse_financial_summary(pages[13]) if len(pages) > 13 else {}
    ratios = derived_ratios(fs)
    metrics = snapshot.setdefault("metrics", {})
    sources = snapshot.setdefault("metric_sources", {})
    evs = snapshot.setdefault("metric_evidence", {})

    if capital:
        metrics["capital_adequacy_ratio_pct"] = capital["bis_2024"]
        sources["capital_adequacy_ratio_pct"] = source_meta()
        evs["capital_adequacy_ratio_pct"] = evidence(
            13, "Capital Adequacy & Recapitalization", pages[12],
            f"2024 BIS Capital Ratio {capital['bis_2024']:.1f}%", "chart-extracted"
        )
        snapshot.setdefault("supporting_metrics", {})["tier1_ratio_pct"] = capital["tier1_2024"]

    if ratios:
        formula_base = (
            f"2024 Profit for the Period KRW {fs['profit_2024_krw_bn']:,.0f}bn; "
            f"Total Assets 2023/2024 KRW {fs['assets_2023_krw_bn']:,.0f}/{fs['assets_2024_krw_bn']:,.0f}bn; "
            f"Total Equity 2023/2024 KRW {fs['equity_2023_krw_bn']:,.0f}/{fs['equity_2024_krw_bn']:,.0f}bn."
        )
        for key, label in (("roa_pct", "ROA"), ("roe_pct", "ROE")):
            metrics[key] = ratios[key]
            meta = source_meta(); meta["method"] = "derived"
            sources[key] = meta
            formula = "profit / average total assets" if key == "roa_pct" else "profit / average total equity"
            evs[key] = evidence(14, "Financial Statement Summary", formula_base,
                                f"Derived 2024 {label} {ratios[key]:.2f}% = {formula}", "derived")

    # Official-source consistency control. Do not hide contradictions.
    flags = snapshot.setdefault("consistency_flags", [])
    cet1 = metrics.get("cet1_ratio_pct")
    tier1 = snapshot.get("supporting_metrics", {}).get("tier1_ratio_pct")
    if cet1 is not None and tier1 is not None and cet1 > tier1 + 0.01:
        flags.append({
            "severity": "warning",
            "check": "cet1_not_above_tier1",
            "detail": f"Official presentation yields CET1 {cet1:.2f}% but Tier 1 {tier1:.2f}% for 2024; this is definitionally unusual and requires manual source verification before credit use."
        })

    # Recompute completeness. Nine target fields: 5 ratios + 3 programmes + ratings.
    target = ["cet1_ratio_pct", "capital_adequacy_ratio_pct", "npl_ratio_pct", "roe_pct", "roa_pct",
              "gmt_programme_usd_bn", "uscp_programme_usd_bn", "ecp_programme_usd_bn", "ratings_detected"]
    populated = sum(bool(metrics.get(k)) if k == "ratings_detected" else metrics.get(k) is not None for k in target)
    q = snapshot.setdefault("data_quality", {})
    q["coverage_pct"] = round(populated / len(target) * 100, 1)
    # Reliability is evidence/source quality, with an explicit penalty for unresolved cross-metric inconsistencies.
    base = float(q.get("reliability_score_out_of_10", 10.0))
    q["reliability_score_out_of_10"] = round(max(0.0, base - (0.5 if flags else 0.0)), 1)
    q["coverage_policy"] = "Derived metrics count only when formula inputs are explicitly extracted from the same dated official source."
    q["consistency_policy"] = "Official-source contradictions are surfaced and reduce reliability; they are never silently reconciled."
    return snapshot


def main():
    snapshot = json.loads(DEFAULT_SNAPSHOT.read_text())
    pages = pdf_pages()
    enriched = enrich(snapshot, pages)
    DEFAULT_SNAPSHOT.write_text(json.dumps(enriched, indent=2, ensure_ascii=False))
    q = enriched["data_quality"]
    print(f"Enriched snapshot: reliability={q['reliability_score_out_of_10']}/10 coverage={q['coverage_pct']}%")
    if q["reliability_score_out_of_10"] < 9.0:
        raise SystemExit("Reliability below 9.0/10 gate")


if __name__ == "__main__":
    main()
