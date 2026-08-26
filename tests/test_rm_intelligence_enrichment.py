from src.rm_intelligence_enrichment import (
    parse_business_framework,
    parse_dec_funding_strategy,
    parse_dec_outstanding,
    parse_jan2025_deal,
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
    assert got["foreign_currency_industrial_bonds_pct"] == 17.0
    assert got["krw_industrial_bonds_pct"] == 40.0
    assert got["manufacturing_exposure_pct"] == 45.3


def test_dec_funding_strategy():
    text = """KDB’s Funding Strategy
    Issuing large and highly liquid bonds, typically 2-3 benchmark USD / EUR bonds annually.
    Maintaining and expanding relationship-based loans which provide a reliable backstop funding source during periods of market stress.
    """
    got = parse_dec_funding_strategy(text)
    assert got["benchmark_bonds_per_year_min"] == 2
    assert got["benchmark_bonds_per_year_max"] == 3
    assert got["bank_loans_as_backstop"] is True


def test_dec_outstanding_funding_and_mix():
    text = """Funding Target and Outstanding Funding Details
    We have reached our total funding target of USD 10bn equivalent in 2025.
    Public Offerings USD 6.3bn USD 5.3bn
    Private Placement USD 3.3bn USD 3.1bn
    Bank Loans USD 300mn USD 650mn
    Total USD 9.9bn USD 9.1bn
    KRW 73.4% Foreign Currency 26.6% USD 122.1bn equivalent
    USD 65.2% BRL 10.3% EUR 10.2% AUD 2.8% GBP 2.3% Others 9.1%
    USD 32.4bn equivalent Outstanding Bonds
    """
    got = parse_dec_outstanding(text)
    assert got["2025_achieved_usd_bn"] == 9.9
    assert got["usd_share_pct"] == 65.2
    assert got["foreign_currency_bonds_outstanding_usd_bn_equiv"] == 32.4


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


def test_quality_checks_detect_bad_outstanding_mix():
    info = {"outstanding_funding": {"usd_share_pct": 90, "brl_share_pct": 11, "eur_share_pct": 4, "aud_share_pct": 3, "gbp_share_pct": 2, "other_currency_share_pct": 6}, "sector_exposure": {}}
    checks = validate(info)
    assert checks and checks[0]["passed"] is False
