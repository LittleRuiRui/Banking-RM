from __future__ import annotations

import io
import json
import re
from pathlib import Path

import requests
from pypdf import PdfReader

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_SNAPSHOT = ROOT / "data" / "kdb_public_snapshot.json"
INVESTOR_URL = "https://www.kdb.co.kr/wcmscontents/pdf/IR_Presentation_2025.pdf"
SOURCE_NAME = "Investor Presentation December 2025"
PERIOD = "1H25"
PUBLICATION_PERIOD = "2025-12"
USER_AGENT = "Banking-RM/0.9 quality-controlled-enrichment"


def pdf_pages(url: str = INVESTOR_URL) -> list[str]:
    r = requests.get(url, timeout=60, headers={"User-Agent": USER_AGENT})
    r.raise_for_status()
    return [(p.extract_text() or "") for p in PdfReader(io.BytesIO(r.content)).pages]


def compact(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


def find_page(pages: list[str], heading: str) -> tuple[int, str] | None:
    for i, page in enumerate(pages):
        if heading.lower() in compact(page).lower():
            return i, page
    return None


def parse_capital_chart(page_text: str) -> dict:
    text = compact(page_text)
    if "Capital Adequacy & Recapitalization" not in text or "BIS Capital Ratio Tier 1 Ratio" not in text:
        return {}
    years = re.search(r"2018\s+2019\s+2020\s+2021\s+2022\s+2023\s+2024\s+1H25\s+BIS Capital Ratio Tier 1 Ratio", text)
    if not years:
        return {}
    vals = [float(x) for x in re.findall(r"(\d{1,2}\.\d)%", text[max(0, years.start()-260):years.start()])]
    if len(vals) < 16:
        return {}
    vals = vals[-16:]
    bis_vals, tier1_vals = vals[:8], vals[8:]
    return {
        "periods": ["2018", "2019", "2020", "2021", "2022", "2023", "2024", "1H25"],
        "bis": bis_vals,
        "tier1": tier1_vals,
        "bis_1h25": bis_vals[-1],
        "tier1_1h25": tier1_vals[-1],
    }


def _six_values(text: str, label: str) -> list[float] | None:
    m = re.search(rf"{label}\s+([\d,()]+)\s+([\d,()]+)\s+([\d,()]+)\s+([\d,()]+)\s+([\d,()]+)\s+([\d,()]+)", text, re.I)
    if not m:
        return None
    def num(s: str) -> float:
        neg = s.startswith("(") and s.endswith(")")
        v = float(s.strip("()").replace(",", ""))
        return -v if neg else v
    return [num(x) for x in m.groups()]


def parse_financial_summary(page_text: str) -> dict:
    text = compact(page_text)
    if "Financial Statement Summary" not in text or "Key Income Statement Items" not in text or "1H25" not in text:
        return {}
    profit = _six_values(text, "Profit for the Period")
    assets = _six_values(text, "Total Assets")
    equity = _six_values(text, "Total Equity")
    if not all((profit, assets, equity)):
        return {}
    return {
        "profit_2024_krw_bn": profit[4],
        "profit_1h25_krw_bn": profit[5],
        "assets_2024_krw_bn": assets[4],
        "assets_1h25_krw_bn": assets[5],
        "equity_2024_krw_bn": equity[4],
        "equity_1h25_krw_bn": equity[5],
    }


def annualized_1h25_ratios(fs: dict) -> dict:
    """Derived, annualized indicators; never present them as KDB-reported ROA/ROE."""
    if not fs:
        return {}
    avg_assets = (fs["assets_2024_krw_bn"] + fs["assets_1h25_krw_bn"]) / 2
    avg_equity = (fs["equity_2024_krw_bn"] + fs["equity_1h25_krw_bn"]) / 2
    annualized_profit = fs["profit_1h25_krw_bn"] * 2
    return {
        "roa_pct": round(annualized_profit / avg_assets * 100, 2),
        "roe_pct": round(annualized_profit / avg_equity * 100, 2),
    }


def source_meta(method: str = "extracted"):
    d = {
        "name": SOURCE_NAME,
        "url": INVESTOR_URL,
        "kind": "investor_presentation",
        "trust_score": 90,
        "reporting_period": PERIOD,
        "publication_period": PUBLICATION_PERIOD,
    }
    if method != "extracted":
        d["method"] = method
    return d


def evidence(page: int, section: str, snippet: str, matched: str, method: str = "extracted"):
    return {
        "source_name": SOURCE_NAME,
        "source_url": INVESTOR_URL,
        "source_kind": "investor_presentation",
        "reporting_period": PERIOD,
        "publication_period": PUBLICATION_PERIOD,
        "page": page,
        "section": section,
        "evidence_snippet": compact(snippet),
        "matched_text": matched,
        "method": method,
    }


def normalize_official_ratings(snapshot: dict):
    ev = snapshot.get("metric_evidence", {}).get("ratings_detected", {})
    snippet = ev.get("evidence_snippet", "")
    if "Aa2" in snippet and "AA (Stable)" in snippet and "AA- (Stable)" in snippet:
        snapshot.setdefault("metrics", {})["ratings_detected"] = ["Aa2", "AA", "AA-"]
        ev["matched_text"] = "Aa2, AA, AA-"


def enrich(snapshot: dict, pages: list[str]) -> dict:
    cap_page = find_page(pages, "Capital Adequacy & Recapitalization")
    fs_page = find_page(pages, "Financial Statement Summary")
    capital = parse_capital_chart(cap_page[1]) if cap_page else {}
    fs = parse_financial_summary(fs_page[1]) if fs_page else {}
    ratios = annualized_1h25_ratios(fs)
    metrics = snapshot.setdefault("metrics", {})
    sources = snapshot.setdefault("metric_sources", {})
    evs = snapshot.setdefault("metric_evidence", {})
    normalize_official_ratings(snapshot)

    if capital and cap_page:
        metrics["capital_adequacy_ratio_pct"] = capital["bis_1h25"]
        sources["capital_adequacy_ratio_pct"] = source_meta("chart-extracted")
        evs["capital_adequacy_ratio_pct"] = evidence(
            cap_page[0] + 1,
            "Capital Adequacy & Recapitalization",
            cap_page[1],
            f"1H25 BIS Capital Ratio {capital['bis_1h25']:.1f}%",
            "chart-extracted",
        )
        snapshot.setdefault("supporting_metrics", {})["tier1_ratio_pct"] = capital["tier1_1h25"]

    if ratios and fs_page:
        base = (
            f"1H25 Profit for the Period KRW {fs['profit_1h25_krw_bn']:,.0f}bn; "
            f"Total Assets 2024/1H25 KRW {fs['assets_2024_krw_bn']:,.0f}/{fs['assets_1h25_krw_bn']:,.0f}bn; "
            f"Total Equity 2024/1H25 KRW {fs['equity_2024_krw_bn']:,.0f}/{fs['equity_1h25_krw_bn']:,.0f}bn."
        )
        for key, label, formula in (
            ("roa_pct", "ROA", "2 × 1H25 profit / average(2024, 1H25 total assets)"),
            ("roe_pct", "ROE", "2 × 1H25 profit / average(2024, 1H25 total equity)"),
        ):
            metrics[key] = ratios[key]
            sources[key] = source_meta("annualized-derived")
            evs[key] = evidence(
                fs_page[0] + 1,
                "Financial Statement Summary",
                base,
                f"Annualized derived 1H25 {label} {ratios[key]:.2f}% = {formula}",
                "annualized-derived",
            )

    flags = []
    cet1 = metrics.get("cet1_ratio_pct")
    tier1 = snapshot.get("supporting_metrics", {}).get("tier1_ratio_pct")
    # Both are 13.9% at 1H25 in the Dec-2025 presentation; flag only a real inconsistency.
    if cet1 is not None and tier1 is not None and cet1 > tier1 + 0.01:
        flags.append({
            "severity": "warning",
            "check": "cet1_not_above_tier1",
            "detail": f"CET1 {cet1:.2f}% exceeds Tier 1 {tier1:.2f}% for the same period; verify definitions before credit use.",
        })
    snapshot["consistency_flags"] = flags

    target = [
        "cet1_ratio_pct", "capital_adequacy_ratio_pct", "npl_ratio_pct", "roe_pct", "roa_pct",
        "gmt_programme_usd_bn", "uscp_programme_usd_bn", "ecp_programme_usd_bn", "ratings_detected",
    ]
    populated = sum(bool(metrics.get(k)) if k == "ratings_detected" else metrics.get(k) is not None for k in target)
    q = snapshot.setdefault("data_quality", {})
    q["coverage_pct"] = round(populated / len(target) * 100, 1)
    base_reliability = float(q.get("reliability_score_out_of_10", 10.0))
    q["reliability_score_out_of_10"] = round(max(0.0, base_reliability - (0.5 if flags else 0.0)), 1)
    q["coverage_policy"] = "Latest-period extracted metrics are preferred. Derived metrics count only when formula inputs are explicitly extracted from the same official source and are labelled as derived."
    q["consistency_policy"] = "Official-source contradictions are surfaced and reduce reliability; they are never silently reconciled."
    return snapshot


def main():
    snapshot = json.loads(DEFAULT_SNAPSHOT.read_text())
    enriched = enrich(snapshot, pdf_pages())
    DEFAULT_SNAPSHOT.write_text(json.dumps(enriched, indent=2, ensure_ascii=False))
    q = enriched["data_quality"]
    print(f"Enriched snapshot: reliability={q['reliability_score_out_of_10']}/10 coverage={q['coverage_pct']}%")
    if q["reliability_score_out_of_10"] < 9.0:
        raise SystemExit("Reliability below 9.0/10 gate")


if __name__ == "__main__":
    main()
