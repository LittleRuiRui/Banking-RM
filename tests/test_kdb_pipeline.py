from src.kdb_pipeline import SourceDocument, build_snapshot, locate_metric_evidence, parse_metrics


def test_parse_metrics_from_sample_text():
    text = """
    CET1 ratio: 13.90%
    Capital adequacy ratio: 16.45%
    NPL ratio: 0.85%
    ROE: 5.20%
    ROA: 0.35%
    Global Medium Term Note Programme US$30 billion
    USCP Programme U$5 billion
    ECP Programme U$12 billion
    Moody's Aa2 Stable; S&P AA Stable; Fitch AA- Stable
    """
    metrics = parse_metrics(text)
    assert metrics["cet1_ratio_pct"] == 13.90
    assert metrics["capital_adequacy_ratio_pct"] == 16.45
    assert metrics["npl_ratio_pct"] == 0.85
    assert metrics["roe_pct"] == 5.20
    assert metrics["roa_pct"] == 0.35
    assert metrics["gmt_programme_usd_bn"] == 30.0
    assert metrics["uscp_programme_usd_bn"] == 5.0
    assert metrics["ecp_programme_usd_bn"] == 12.0
    assert "AA-" in metrics["ratings_detected"]


def test_metric_evidence_carries_page_period_and_snippet():
    doc = SourceDocument("Investor Presentation July 2025","investor","investor_presentation","--- PAGE 7 ---\nCapital overview\nCET1 ratio: 13.90%\nMore text",reporting_period="2025-07")
    ev = locate_metric_evidence(doc, "cet1_ratio_pct")
    assert ev is not None
    assert ev["page"] == 7
    assert ev["reporting_period"] == "2025-07"
    assert "13.90%" in ev["evidence_snippet"]


def test_snapshot_uses_authoritative_sources_and_scores_9_plus():
    docs = [
        SourceDocument("KDB International Credit Ratings","ratings","official_ratings","Moody's Aa2 (Stable) S&P AA (Stable) Fitch AA- (Stable)","current","International Credit Ratings"),
        SourceDocument("KDB Funding Programmes","funding","official_funding","Global MTN Programme size of U$ 30bn USCP Programme size of U$ 5bn ECP Programme size of U$ 12bn","current","Funding Programmes"),
        SourceDocument("Investor Presentation July 2025","investor","investor_presentation","--- PAGE 7 ---\nCET1 ratio: 13.90% Capital adequacy ratio: 16.45% NPL ratio: 0.85% ROE: 5.20% ROA: 0.35%","2025-07"),
        SourceDocument("Old document","old","pdf","USCP Programme US$99 billion Fitch BBB Stable CET1 ratio: 1.00%","2020"),
    ]
    snap = build_snapshot({"client":"Korea Development Bank"}, docs)
    assert snap["metrics"]["gmt_programme_usd_bn"] == 30.0
    assert snap["metrics"]["uscp_programme_usd_bn"] == 5.0
    assert snap["metrics"]["ecp_programme_usd_bn"] == 12.0
    assert snap["metric_sources"]["uscp_programme_usd_bn"]["kind"] == "official_funding"
    assert set(snap["metrics"]["ratings_detected"]) == {"AA2","AA","AA-"}
    assert snap["metric_sources"]["ratings_detected"]["kind"] == "official_ratings"
    assert snap["metric_evidence"]["cet1_ratio_pct"]["page"] == 7
    assert snap["metric_evidence"]["cet1_ratio_pct"]["reporting_period"] == "2025-07"
    assert snap["metric_evidence"]["uscp_programme_usd_bn"]["section"] == "Funding Programmes"
    assert snap["data_quality"]["reliability_score_out_of_10"] >= 9.0
    assert snap["data_quality"]["coverage_pct"] == 100.0


def test_kdb_chart_style_npl_extraction():
    text = "--- PAGE 12 ---\n2.5% 1.7% 0.7% 0.8% 0.6% 121.0% 170.1% 365.1% 236.7% 275.4% 2020 2021 2022 2023 2024 NPL Ratio Coverage Ratio"
    metrics = parse_metrics(text)
    assert metrics["npl_ratio_pct"] == 0.6
    doc = SourceDocument("Investor Presentation July 2025","investor","investor_presentation",text,"2025-07")
    ev = locate_metric_evidence(doc,"npl_ratio_pct")
    assert ev["page"] == 12
    assert "2024 NPL Ratio 0.6%" == ev["matched_text"]
