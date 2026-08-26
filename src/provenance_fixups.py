from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SNAPSHOT = ROOT / "data" / "kdb_public_snapshot.json"
JULY_2025 = "Investor Presentation July 2025"


def apply(snapshot: dict) -> dict:
    """Correct provenance semantics without changing metric values.

    The July-2025 deck is the publication/source date, while the CET1 and NPL
    observations used by this prototype are explicitly FY2024 / 31-Dec-2024 data.
    """
    for key in ("cet1_ratio_pct", "npl_ratio_pct"):
        src = snapshot.get("metric_sources", {}).get(key, {})
        ev = snapshot.get("metric_evidence", {}).get(key, {})
        if src.get("name") == JULY_2025:
            src["publication_period"] = "2025-07"
            src["reporting_period"] = "2024-12"
            ev["publication_period"] = "2025-07"
            ev["reporting_period"] = "2024-12"
    return snapshot


def main():
    s = json.loads(SNAPSHOT.read_text())
    SNAPSHOT.write_text(json.dumps(apply(s), indent=2, ensure_ascii=False))
    print("Applied KDB provenance fixups: publication date separated from reporting period")


if __name__ == "__main__":
    main()
