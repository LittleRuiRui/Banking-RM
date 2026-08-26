from src.provenance_fixups import apply


def test_publication_date_is_not_used_as_metric_reporting_period():
    s = {
        "metric_sources": {"cet1_ratio_pct": {"name": "Investor Presentation July 2025", "reporting_period": "2025-07"}},
        "metric_evidence": {"cet1_ratio_pct": {"reporting_period": "2025-07"}},
    }
    out = apply(s)
    assert out["metric_sources"]["cet1_ratio_pct"]["publication_period"] == "2025-07"
    assert out["metric_sources"]["cet1_ratio_pct"]["reporting_period"] == "2024-12"
    assert out["metric_evidence"]["cet1_ratio_pct"]["reporting_period"] == "2024-12"
