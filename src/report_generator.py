from pathlib import Path
import json

ROOT = Path(__file__).resolve().parents[1]


def render(data: dict) -> str:
    ratings = " / ".join(f"{k}: {v}" for k, v in data["credit"]["ratings"].items())
    opps = "\n".join(
        f"- **{o['theme']} ({o['priority']})** — products: {', '.join(o['possible_products'])}. Trigger: {o['trigger']}."
        for o in data["opportunities"]
    )
    return f"""# {data['client']} — RM Intelligence Generated Brief
**As of:** {data['as_of']}

## Credit
**Overall:** {data['credit']['overall']}  
**Ownership:** {data['credit']['ownership']}  
**Ratings:** {ratings}

## Funding programmes
- GMTN: US${data['funding']['gmt_programme_usd_bn']}bn
- USCP: US${data['funding']['uscp_programme_usd_bn']}bn
- ECP: US${data['funding']['ecp_programme_usd_bn']}bn

## Opportunities
{opps}

## RM principle
Use public facts to generate hypotheses, then use the meeting to discover changes, priorities, buying criteria and pipeline.
"""


if __name__ == "__main__":
    data = json.loads((ROOT / "data" / "kdb_sample.json").read_text())
    output = ROOT / "reports" / "kdb_rm_intelligence_generated.md"
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(render(data))
    print(f"Wrote {output}")
