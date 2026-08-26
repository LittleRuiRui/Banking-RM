from __future__ import annotations

import io
import json
import re
from pathlib import Path

import requests
from pypdf import PdfReader

ROOT = Path(__file__).resolve().parents[1]
SNAPSHOT = ROOT / "data" / "kdb_public_snapshot.json"
INVESTOR_URL = "https://www.kdb.co.kr/wcmscontents/pdf/KDB_Investor_Presentation_July_2025.pdf"
SOURCE_NAME = "Investor Presentation July 2025"
USER_AGENT = "Banking-RM/0.8 rm-intelligence"


def compact(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


def pdf_pages(url: str = INVESTOR_URL) -> list[str]:
    r = requests.get(url, timeout=60, headers={"User-Agent": USER_AGENT})
    r.raise_for_status()
    return [(p.extract_text() or "") for p in PdfReader(io.BytesIO(r.content)).pages]


def source(page: int, section: str, reporting_period: str = "2024-12") -> dict:
    return {
        "source_name": SOURCE_NAME,
        "source_url": INVESTOR_URL,
        "source_kind": "investor_presentation",
        "publication_period": "2025-07",
        "reporting_period": reporting_period,
        "page": page,
        "section": section,
    }


def parse_business_framework(page: str) -> dict:
    t = compact(page)
    if "Basic Framework of KDB’s Business Operations" not in t and "Basic Framework of KDB's Business Operations" not in t:
        return {}
    pairs = {
        "wholesale_funding_pct": r"68% of funding through wholesale funding",
        "foreign_currency_industrial_bonds_pct": r"17% Industrial Finance Bonds \(Foreign Currencies\)",
        "krw_industrial_bonds_pct": r"40% Industrial Finance Bonds \(KRW\)",
        "krw_deposits_pct": r"16% Deposits \(KRW\)",
        "foreign_currency_deposits_pct": r"6% Deposits in \(Foreign Currencies\)",
        "borrowings_pct": r"11% Borrowings",
        "manufacturing_exposure_pct": r"45\.3% Manufacturing",
        "finance_insurance_exposure_pct": r"24\.4% Finance and Insurance",
        "transportation_exposure_pct": r"6\.6% Transportation",
        "utilities_exposure_pct": r"3\.5% Electric, Gas and Water Supply",
        "public_admin_exposure_pct": r"Public Administration 0\.5%",
        "other_sector_exposure_pct": r"19\.7% Others",
    }
    out = {}
    for key, pattern in pairs.items():
        if re.search(pattern, t, re.I):
            m = re.search(r"(\d+(?:\.\d+)?)", pattern.replace("\\", ""))
            if m:
                out[key] = float(m.group(1))
    # Explicit values avoid reverse-engineering escaped regex strings.
    fixed = {
        "wholesale_funding_pct": 68.0,
        "foreign_currency_industrial_bonds_pct": 17.0,
        "krw_industrial_bonds_pct": 40.0,
        "krw_deposits_pct": 16.0,
        "foreign_currency_deposits_pct": 6.0,
        "borrowings_pct": 11.0,
        "manufacturing_exposure_pct": 45.3,
        "finance_insurance_exposure_pct": 24.4,
        "transportation_exposure_pct": 6.6,
        "utilities_exposure_pct": 3.5,
        "public_admin_exposure_pct": 0.5,
        "other_sector_exposure_pct": 19.7,
    }
    return {k: v for k, v in fixed.items() if re.search(pairs[k], t, re.I)}


def parse_fx_funding_channels(page: str) -> dict:
    t = compact(page)
    if "Foreign Currency Funding Channels" not in t or "$42.2bn" not in t:
        return {}
    expected = {
        "five_year_fx_bond_issuance_usd_bn": (42.2, r"\$42\.2bn"),
        "usd_share_pct": (68.6, r"USD 68\.6%"),
        "brl_share_pct": (11.0, r"BRL 11\.0%"),
        "eur_share_pct": (4.8, r"EUR 4\.8%"),
        "cnh_share_pct": (4.0, r"CNH 4\.0%"),
        "aud_share_pct": (3.2, r"AUD 3\.2%"),
        "chf_share_pct": (2.3, r"CHF 2\.3%"),
        "other_currency_share_pct": (6.1, r"Others 6\.1%"),
        "benchmark_bonds_per_year_min": (2, r"typically 2-3 benchmark USD/EUR bonds /annually"),
        "benchmark_bonds_per_year_max": (3, r"typically 2-3 benchmark USD/EUR bonds /annually"),
        "benchmark_size_usd_bn_min": (1.0, r"Typical size ranges from 1-3bn"),
        "benchmark_size_usd_bn_max": (3.0, r"Typical size ranges from 1-3bn"),
    }
    return {k: v for k, (v, pat) in expected.items() if re.search(pat, t, re.I)}


def parse_jan2025_deal(page: str) -> dict:
    t = compact(page)
    if "KDB’s Offering of USD3.0bn Senior Unsecured Notes" not in t and "KDB's Offering of USD3.0bn Senior Unsecured Notes" not in t:
        return {}
    checks = [
        r"Issue Date 23 January, 2025",
        r"Currency / Size USD 900mn USD 1\.2bn USD 900mn",
        r"Coupon Rate 4\.625% 4\.875% SOFR\+76bps",
    ]
    if not all(re.search(p, t, re.I) for p in checks):
        return {}
    return {
        "issue_date": "2025-01-23",
        "total_size_usd_bn": 3.0,
        "tranches": [
            {"tenor": "3Y", "type": "fixed", "size_usd_bn": 0.9, "coupon_pct": 4.625, "issue_spread_bps": 57},
            {"tenor": "5Y", "type": "fixed", "size_usd_bn": 1.2, "coupon_pct": 4.875, "issue_spread_bps": 76},
            {"tenor": "5Y", "type": "FRN", "size_usd_bn": 0.9, "coupon": "SOFR+76bps", "issue_spread_bps": 76},
        ],
    }


def parse_funding_outlook(page: str) -> dict:
    t = compact(page)
    if "Funding Outlook/Target" not in t:
        return {}
    m = re.search(r"Total funding volume expected at USD\s*10bn equivalent in 2025", t, re.I)
    if not m:
        return {}
    return {"2025_total_funding_target_usd_bn_equiv": 10.0}


def parse_liquidity_commitment(page: str) -> dict:
    t = compact(page)
    if "Commitment to Liquidity" not in t:
        return {}
    out = {}
    if re.search(r"Continue issuing an average of 3 USD benchmarks annually", t, re.I):
        out["usd_benchmarks_per_year"] = 3
    if re.search(r"more than 130 investors bought KDB’s USD public trades in 2024", t, re.I):
        out["usd_public_trade_investors_2024_min"] = 130
    if re.search(r"US\$1\.25bn .* per tranche", t, re.I):
        out["post_ssa_avg_tranche_usd_bn"] = 1.25
    return out


def validate(info: dict) -> list[dict]:
    checks = []
    def add(name, ok, detail): checks.append({"check": name, "passed": bool(ok), "detail": detail})
    fx = info.get("foreign_currency_funding", {})
    shares = [fx.get(k) for k in ("usd_share_pct","brl_share_pct","eur_share_pct","cnh_share_pct","aud_share_pct","chf_share_pct","other_currency_share_pct")]
    if all(v is not None for v in shares):
        add("fx_currency_mix_sums_100", abs(sum(shares) - 100.0) < 0.11, f"Currency mix sums to {sum(shares):.1f}%")
    sectors = info.get("sector_exposure", {})
    vals = list(sectors.values())
    if vals:
        add("sector_mix_sums_100", abs(sum(vals) - 100.0) < 0.11, f"Sector mix sums to {sum(vals):.1f}%")
    deal = info.get("recent_issuance", {})
    if deal:
        add("jan2025_tranches_sum", abs(sum(x["size_usd_bn"] for x in deal["tranches"]) - deal["total_size_usd_bn"]) < 0.001, "Tranches reconcile to total issue size")
    return checks


def enrich(snapshot: dict, pages: list[str]) -> dict:
    framework = parse_business_framework(pages[6]) if len(pages) > 6 else {}
    fx = parse_fx_funding_channels(pages[16]) if len(pages) > 16 else {}
    recent = parse_jan2025_deal(pages[18]) if len(pages) > 18 else {}
    liquidity = parse_liquidity_commitment(pages[19]) if len(pages) > 19 else {}
    outlook = parse_funding_outlook(pages[20]) if len(pages) > 20 else {}

    info = {
        "funding_structure": {k: v for k, v in framework.items() if "funding" in k or "deposits" in k or "borrowings" in k},
        "sector_exposure": {
            "manufacturing_pct": framework.get("manufacturing_exposure_pct"),
            "finance_insurance_pct": framework.get("finance_insurance_exposure_pct"),
            "transportation_pct": framework.get("transportation_exposure_pct"),
            "utilities_pct": framework.get("utilities_exposure_pct"),
            "public_admin_pct": framework.get("public_admin_exposure_pct"),
            "others_pct": framework.get("other_sector_exposure_pct"),
        },
        "foreign_currency_funding": fx,
        "recent_issuance": recent,
        "liquidity_commitment": liquidity,
        "funding_outlook": outlook,
        "provenance": {
            "funding_structure": source(7, "Basic Framework of KDB’s Business Operations"),
            "sector_exposure": source(7, "Basic Framework of KDB’s Business Operations"),
            "foreign_currency_funding": source(17, "Foreign Currency Funding Channels", "2020-2024"),
            "recent_issuance": source(19, "Foreign Currency Funding Track Record", "2025-01-23"),
            "liquidity_commitment": source(20, "Commitment to Liquidity", "2024 / 2025-YTD"),
            "funding_outlook": source(21, "Funding Outlook/Target", "2025 target"),
        },
    }
    info["sector_exposure"] = {k: v for k, v in info["sector_exposure"].items() if v is not None}
    info["quality_checks"] = validate(info)
    info["signals"] = []
    if outlook.get("2025_total_funding_target_usd_bn_equiv"):
        info["signals"].append({"type":"funding","priority":"high","fact":"KDB targets USD10bn equivalent total funding in 2025.","rm_angle":"Ask how much remains, currency/tenor mix, and whether prefunding is contemplated."})
    if fx.get("usd_share_pct", 0) > 60:
        info["signals"].append({"type":"fx_ccs","priority":"high","fact":f"USD represented {fx['usd_share_pct']:.1f}% of 2020-2024 foreign-currency bond issuance.","rm_angle":"Probe diversification economics and alternative-currency / CCS appetite."})
    if info["sector_exposure"].get("manufacturing_pct", 0) > 40:
        info["signals"].append({"type":"sector","priority":"medium","fact":f"Manufacturing accounts for {info['sector_exposure']['manufacturing_pct']:.1f}% of operating exposure.","rm_angle":"Use Korean manufacturing outbound investment as a route into ASEAN syndication, PF and transaction-banking conversations."})
    snapshot["rm_intelligence"] = info
    return snapshot


def main():
    snapshot = json.loads(SNAPSHOT.read_text())
    pages = pdf_pages()
    snapshot = enrich(snapshot, pages)
    failed = [x for x in snapshot["rm_intelligence"]["quality_checks"] if not x["passed"]]
    if failed:
        raise SystemExit("RM intelligence consistency checks failed: " + json.dumps(failed))
    SNAPSHOT.write_text(json.dumps(snapshot, indent=2, ensure_ascii=False))
    print("Added RM intelligence enrichment and passed consistency checks")


if __name__ == "__main__":
    main()
