from __future__ import annotations

import re


def _remove_markdown_section(report: str, heading: str) -> str:
    pat = re.compile(
        rf"(?ms)^##+\s+{re.escape(heading)}\s*$.*?(?=^##+\s+|\Z)"
    )
    return pat.sub("", report).strip() + "\n"


def _rename_heading(report: str, old: str, new: str) -> str:
    return re.sub(
        rf"(?m)^(#+\s+){re.escape(old)}\s*$",
        rf"\1{new}",
        report,
    )


def _limit_questions(report: str, limit: int) -> str:
    lines = report.splitlines()
    out = []
    in_playbook = False
    question_rows = 0
    for line in lines:
        if re.match(r"^##+\s+.*Meeting Discovery Playbook", line, re.I):
            in_playbook = True
            out.append(line)
            continue
        if in_playbook and re.match(r"^##+\s+", line):
            in_playbook = False
        if in_playbook and line.startswith("|"):
            # Preserve table header/separator; count subsequent data rows.
            if "Objective" in line or re.match(r"^\|[-: |]+\|$", line):
                out.append(line)
                continue
            question_rows += 1
            if question_rows > limit:
                continue
        out.append(line)
    return "\n".join(out) + "\n"


def apply_text_rules(report: str, rules_text: str) -> dict:
    current = report
    applied = []
    required = []

    for raw in rules_text.splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        if line.upper().startswith("HIDE:"):
            heading = line.split(":", 1)[1].strip()
            current = _remove_markdown_section(current, heading)
            applied.append(f"HIDE:{heading}")
        elif line.upper().startswith("RENAME:") and "=>" in line:
            body = line.split(":", 1)[1]
            old, new = [x.strip() for x in body.split("=>", 1)]
            current = _rename_heading(current, old, new)
            applied.append(f"RENAME:{old}=>{new}")
        elif line.upper().startswith("DISCLAIMER:"):
            text = line.split(":", 1)[1].strip()
            current = f"> **Notice:** {text}\n\n" + current
            applied.append("DISCLAIMER")
        elif line.upper().startswith("MAX_QUESTIONS:"):
            try:
                n = int(line.split(":", 1)[1].strip())
            except ValueError:
                continue
            if n >= 0:
                current = _limit_questions(current, n)
                applied.append(f"MAX_QUESTIONS:{n}")
        elif line.upper().startswith("REQUIRE:"):
            fields = [x.strip() for x in line.split(":", 1)[1].split("|") if x.strip()]
            required.extend(fields)
            applied.append("REQUIRE:" + "|".join(fields))

    if required:
        missing = [x for x in required if x.lower() not in current.lower()]
        if missing:
            current = (
                "> **Rule check failed:** missing required concepts: "
                + ", ".join(missing)
                + "\n\n"
                + current
            )

    return {"report": current, "applied": applied, "required": required}
