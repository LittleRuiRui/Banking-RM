from __future__ import annotations

import json
import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "data" / "kdb_public_snapshot.json"
WEB_DATA = ROOT / "web" / "data" / "kdb_public_snapshot.json"


def main() -> None:
    snapshot = json.loads(SOURCE.read_text())
    q = snapshot.get("data_quality", {})
    reliability = float(q.get("reliability_score_out_of_10", 0))
    coverage = float(q.get("coverage_pct", 0))
    if reliability < 9.0:
        raise SystemExit(f"Refusing web export: reliability {reliability}/10 is below 9.0 gate")
    if coverage < 80.0:
        raise SystemExit(f"Refusing web export: coverage {coverage}% is below 80% web-display gate")
    WEB_DATA.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(SOURCE, WEB_DATA)
    print(f"Exported verified snapshot to {WEB_DATA}")


if __name__ == "__main__":
    main()
