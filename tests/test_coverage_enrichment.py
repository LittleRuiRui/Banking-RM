from src.coverage_enrichment import parse_capital_chart, parse_financial_summary, derived_ratios, enrich


def test_capital_chart_requires_full_labelled_sequence():
    text = """Capital Adequacy & Recapitalization 14.8% 14.1% 16.0% 14.9% 13.4% 14.1% 13.9%
    12.7% 12.1% 14.3% 13.7% 12.3% 12.8% 12.9%
    2018 2019 2020 2021 2022 2023 2024 BIS Capital Ratio Tier 1 Ratio"""
    got = parse_capital_chart(text)
    assert got["bis_2024"] == 13.9
    assert got["tier1_2024"] == 12.9


def test_financial_summary_and_derived_ratios():
    text = """Financial Statement Summary Key Income Statement Items (KRW bn) 2020 2021 2022 2023 2024
    Profit for the Period 488 2,462 465 3,027 2,007
    Key Balance Sheet Items (KRW bn) 2020 2021 2022 2023 2024
    Total Assets 251,852 276,422 312,845 317,066 339,221
    Total Equity 30,383 36,503 35,668 39,431 42,925"""
    fs = parse_financial_summary(text)
    r = derived_ratios(fs)
    assert fs["profit_2024_krw_bn"] == 2007
    assert r["roa_pct"] == 0.61
    assert r["roe_pct"] == 4.87


def test_enrichment_reaches_full_coverage_but_flags_cet1_tier1_conflict():
    snapshot = {
        "metrics": {
            "cet1_ratio_pct": 13.9, "capital_adequacy_ratio_pct": None, "npl_ratio_pct": 0.6,
            "roe_pct": None, "roa_pct": None, "gmt_programme_usd_bn": 30.0,
            "uscp_programme_usd_bn": 5.0, "ecp_programme_usd_bn": 12.0,
            "ratings_detected": ["AA2", "AA", "AA-"]
        },
        "metric_sources": {}, "metric_evidence": {},
        "data_quality": {"reliability_score_out_of_10": 10.0, "coverage_pct": 66.7}
    }
    pages = [""] * 14
    pages[12] = "Capital Adequacy & Recapitalization 14.8% 14.1% 16.0% 14.9% 13.4% 14.1% 13.9% 12.7% 12.1% 14.3% 13.7% 12.3% 12.8% 12.9% 2018 2019 2020 2021 2022 2023 2024 BIS Capital Ratio Tier 1 Ratio"
    pages[13] = "Financial Statement Summary Key Income Statement Items (KRW bn) 2020 2021 2022 2023 2024 Profit for the Period 488 2,462 465 3,027 2,007 Key Balance Sheet Items (KRW bn) 2020 2021 2022 2023 2024 Total Assets 251,852 276,422 312,845 317,066 339,221 Total Equity 30,383 36,503 35,668 39,431 42,925"
    out = enrich(snapshot, pages)
    assert out["data_quality"]["coverage_pct"] == 100.0
    assert out["data_quality"]["reliability_score_out_of_10"] == 9.5
    assert out["consistency_flags"][0]["check"] == "cet1_not_above_tier1"
    assert out["metric_evidence"]["roe_pct"]["method"] == "derived"
