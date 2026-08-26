from src.rm_intelligence_enrichment import (
    parse_business_framework,
    parse_fx_funding_channels,
    parse_jan2025_deal,
    parse_funding_outlook,
    validate,
)


def test_business_framework_requires_labels():
    text = """Basic Framework of KDB’s Business Operations
    68% of funding through wholesale funding
    17% Industrial Finance Bonds (Foreign Currencies)
    40% Industrial Finance Bonds (KRW)
    16% Deposits (KRW)
    6% Deposits in (Foreign Currencies)
    11% Borrowings
    45.3% Manufacturing 24.4% Finance and Insurance 6.6% Transportation
    3.5% Electric, Gas and Water Supply Public Administration 0.5% 19.7% Others
    """
    got = parse_business_framework(text)
    assert got["wholesale_funding_pct"] == 68.0
    assert got["manufacturing_exposure_pct"] == 45.3
    assert got["other_sector_exposure_pct"] == 19.7


def test_fx_mix_and_benchmark_strategy():
    text = """Foreign Currency Funding Channels Active Foreign Currency Bond Issuance (1)
    $42.2bn as of Dec 2024 BRL 11.0% CNH 4.0% EUR 4.8% AUD 3.2% Others 6.1%
    USD 68.6% CHF 2.3%
    KDB USD and EUR Benchmark Bonds
    Pillar of KDB’s annual financing, typically 2-3 benchmark USD/EUR bonds /annually
    Typical size ranges from 1-3bn, with tranche size at least 1bn+
    """
    got = parse_fx_funding_channels(text)
    assert got["five_year_fx_bond_issuance_usd_bn"] == 42.2
    assert got["usd_share_pct"] == 68.6
    assert got["benchmark_bonds_per_year_min"] == 2
    assert got["benchmark_size_usd_bn_max"] == 3.0


def test_recent_issue_reconciles():
    text = """KDB’s Offering of USD3.0bn Senior Unsecured Notes (Jan 2025)
    Issue Date 23 January, 2025
    Coupon Rate 4.625% 4.875% SOFR+76bps
    Issue Spread SOFR MS + 57bps SOFR MS + 76bps SOFR + 76bps
    Currency / Size USD 900mn USD 1.2bn USD 900mn
    """
    got = parse_jan2025_deal(text)
    assert got["total_size_usd_bn"] == 3.0
    assert sum(x["size_usd_bn"] for x in got["tranches"]) == 3.0


def test_funding_target_is_explicit():
    assert parse_funding_outlook("Funding Outlook/Target Total funding volume expected at USD10bn equivalent in 2025")["2025_total_funding_target_usd_bn_equiv"] == 10.0


def test_quality_checks_detect_bad_mix():
    info = {"foreign_currency_funding": {"usd_share_pct": 90, "brl_share_pct": 11, "eur_share_pct": 4, "cnh_share_pct": 4, "aud_share_pct": 3, "chf_share_pct": 2, "other_currency_share_pct": 6}, "sector_exposure": {}}
    checks = validate(info)
    assert checks and checks[0]["passed"] is False
