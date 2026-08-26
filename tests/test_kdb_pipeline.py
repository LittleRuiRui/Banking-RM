from src.kdb_pipeline import parse_metrics


def test_parse_metrics_from_sample_text():
    text = """
    CET1 ratio: 13.90%
    Capital adequacy ratio: 16.45%
    NPL ratio: 0.85%
    ROE: 5.20%
    ROA: 0.35%
    Global Medium Term Note Programme US$30 billion
    USCP Programme US$5 billion
    ECP Programme US$12 billion
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
    assert "AA" in metrics["ratings_detected"]
    assert "AA-" in metrics["ratings_detected"]
