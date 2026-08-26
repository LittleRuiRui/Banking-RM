from src.kdb_pipeline import SourceDocument, build_snapshot, parse_metrics


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


def test_snapshot_uses_authoritative_sources_and_scores_9_plus():
    docs = [
        SourceDocument("KDB International Credit Ratings", "ratings", "official_ratings", "Moody's Aa2 (Stable) S&P AA (Stable) Fitch AA- (Stable)"),
        SourceDocument("KDB Funding Programmes", "funding", "official_funding", "Global MTN Programme size of U$ 30bn USCP Programme size of U$ 5bn ECP Programme size of U$ 12bn"),
        SourceDocument("Investor Presentation July 2025", "investor", "investor_presentation", "CET1 ratio: 13.90% Capital adequacy ratio: 16.45% NPL ratio: 0.85% ROE: 5.20% ROA: 0.35%"),
        # Historical/noisy PDF must not override authoritative sources.
        SourceDocument("Old document", "old", "pdf", "USCP Programme US$99 billion Fitch BBB Stable CET1 ratio: 1.00%"),
    ]
    snap = build_snapshot({"client": "Korea Development Bank"}, docs)
    assert snap["metrics"]["gmt_programme_usd_bn"] == 30.0
    assert snap["metrics"]["uscp_programme_usd_bn"] == 5.0
    assert snap["metrics"]["ecp_programme_usd_bn"] == 12.0
    assert snap["metric_sources"]["uscp_programme_usd_bn"]["kind"] == "official_funding"
    assert set(snap["metrics"]["ratings_detected"]) == {"AA2", "AA", "AA-"}
    assert snap["metric_sources"]["ratings_detected"]["kind"] == "official_ratings"
    assert snap["data_quality"]["score_out_of_10"] >= 9.0
