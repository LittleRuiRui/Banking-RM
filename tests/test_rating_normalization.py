from src.coverage_enrichment import normalize_official_ratings


def test_moodys_aa2_case_is_preserved():
    snapshot = {
        "metrics": {"ratings_detected": ["AA2", "AA", "AA-"]},
        "metric_evidence": {"ratings_detected": {"evidence_snippet": "Moody's S&P Fitch Long Term Rating (Outlook) Aa2 (Stable) AA (Stable) AA- (Stable)"}},
    }
    normalize_official_ratings(snapshot)
    assert snapshot["metrics"]["ratings_detected"] == ["Aa2", "AA", "AA-"]
    assert snapshot["metric_evidence"]["ratings_detected"]["matched_text"] == "Aa2, AA, AA-"
