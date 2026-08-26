from src.rule_customizer import apply_text_rules


def test_hide_and_rename_and_disclaimer():
    report = """# Report

## Evidence ledger
secret table

## Opportunity Intelligence
text
"""
    rules = """HIDE: Evidence ledger
RENAME: Opportunity Intelligence => Business Opportunities
DISCLAIMER: Internal only
"""
    out = apply_text_rules(report, rules)["report"]
    assert "secret table" not in out
    assert "## Business Opportunities" in out
    assert "Internal only" in out


def test_require_flags_missing_concept():
    out = apply_text_rules("# Report\nSource: KDB\n", "REQUIRE: source | reporting period | reliability")["report"]
    assert "Rule check failed" in out
    assert "reporting period" in out
    assert "reliability" in out


def test_limit_questions_in_playbook_table():
    report = """## Meeting Discovery Playbook
| Objective | Question |
|---|---|
| A | Q1 |
| B | Q2 |
| C | Q3 |

## Next
Done
"""
    out = apply_text_rules(report, "MAX_QUESTIONS: 2")["report"]
    assert "| A | Q1 |" in out
    assert "| B | Q2 |" in out
    assert "| C | Q3 |" not in out
    assert "## Next" in out
