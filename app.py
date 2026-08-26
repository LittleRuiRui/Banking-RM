from __future__ import annotations

import json
from pathlib import Path

import streamlit as st

from src.upload_ingest import extract_uploaded_file, build_source_pack
from src.rule_customizer import apply_text_rules

ROOT = Path(__file__).resolve().parent
DEMO_SNAPSHOT = ROOT / "data" / "kdb_demo_snapshot.json"
DEMO_REPORT = ROOT / "reports" / "kdb_demo_brief.md"
GENERATED_SNAPSHOT = ROOT / "data" / "kdb_public_snapshot.json"
GENERATED_REPORT = ROOT / "reports" / "kdb_auto_brief.md"

st.set_page_config(page_title="RM Intelligence", page_icon="🏦", layout="wide")

st.markdown(
    """
<style>
    .block-container {padding-top: 1.5rem; padding-bottom: 3rem; max-width: 1450px;}
    [data-testid="stSidebar"] {background: linear-gradient(180deg,#071a33 0%,#0b2545 100%);}
    [data-testid="stSidebar"] * {color: #f3f7fb !important;}
    .hero {padding: 1.3rem 1.5rem; border:1px solid #e7edf5; border-radius:18px; background:linear-gradient(135deg,#ffffff,#f5f9ff); margin-bottom:1rem;}
    .hero h1 {font-size:2rem; margin:0 0 .25rem 0; color:#10213b;}
    .hero p {margin:0; color:#5c6b80;}
    .metric-card {border:1px solid #e6ebf2; border-radius:16px; padding:1rem 1.05rem; min-height:126px; background:white; box-shadow:0 1px 3px rgba(16,33,59,.04);}
    .metric-label {font-size:.8rem; color:#65758b; font-weight:600;}
    .metric-value {font-size:1.65rem; color:#10213b; font-weight:750; margin:.35rem 0;}
    .metric-note {font-size:.78rem; color:#738198;}
    .good {color:#079455; font-weight:700;}
    .warn {color:#e36b00; font-weight:700;}
    .section-title {font-size:1.05rem; font-weight:750; color:#10213b; margin:.2rem 0 .7rem 0;}
    .insight {border-left:4px solid #246bfd; background:#f6f9ff; padding:.8rem 1rem; border-radius:8px; margin:.55rem 0;}
    .opportunity {border:1px solid #e8edf4; border-radius:14px; padding:.9rem 1rem; margin-bottom:.7rem; background:#fff;}
    .priority-high {display:inline-block;background:#e8f7ef;color:#087a47;padding:.15rem .5rem;border-radius:999px;font-size:.72rem;font-weight:700;}
    .priority-medium {display:inline-block;background:#fff4e6;color:#b45c00;padding:.15rem .5rem;border-radius:999px;font-size:.72rem;font-weight:700;}
    .small-muted {font-size:.78rem;color:#76859b;}
    div[data-testid="stDownloadButton"] button {border-radius:10px;}
</style>
""",
    unsafe_allow_html=True,
)


def load_demo():
    if GENERATED_SNAPSHOT.exists() and GENERATED_REPORT.exists():
        return json.loads(GENERATED_SNAPSHOT.read_text(encoding="utf-8")), GENERATED_REPORT.read_text(encoding="utf-8"), "Live generated output"
    return json.loads(DEMO_SNAPSHOT.read_text(encoding="utf-8")), DEMO_REPORT.read_text(encoding="utf-8"), "Committed verified demo"


def metric_card(label: str, value: str, note: str, tone: str = ""):
    tone_html = f'<span class="{tone}">{note}</span>' if tone else f'<span class="metric-note">{note}</span>'
    st.markdown(f'<div class="metric-card"><div class="metric-label">{label}</div><div class="metric-value">{value}</div>{tone_html}</div>', unsafe_allow_html=True)


with st.sidebar:
    st.markdown("## 🏦 RM Intelligence")
    st.caption("Institutional Intelligence Platform")
    st.divider()
    workspace = st.radio("Workspace", ["KDB Demo", "New Institution", "Customize Report"], label_visibility="collapsed")
    st.divider()
    st.markdown("**Data principle**")
    st.caption("Missing beats guessed. Every material fact should carry source, period and evidence before credit use.")

if workspace == "KDB Demo":
    snap, report, output_mode = load_demo()
    q = snap.get("data_quality", {})
    freshness = snap.get("freshness") or snap.get("rm_intelligence", {}).get("freshness", {})

    st.markdown(
        f'<div class="hero"><h1>Korea Development Bank (KDB)</h1><p>RM Intelligence Report · {output_mode} · Public sources only</p></div>',
        unsafe_allow_html=True,
    )

    c1, c2, c3, c4 = st.columns(4)
    with c1:
        metric_card("Reliability", f"{q.get('reliability_score_out_of_10', 9.5)}/10", "High reliability", "good")
    with c2:
        metric_card("Coverage", f"{q.get('coverage_pct', 100):g}%", "Core MVP metrics", "good")
    with c3:
        days = freshness.get("age_days_approx", 268)
        metric_card("Data freshness", f"{days} days", "STALE — refresh 2026 plan", "warn")
    with c4:
        metric_card("Report type", "Institutional RM", "Credit + Business + Meeting")

    overview, credit, funding, opps, meeting, sources = st.tabs([
        "Overview", "Credit Intelligence", "Funding & Business", "Opportunities", "Meeting Playbook", "Evidence & Download"
    ])

    with overview:
        left, right = st.columns([1.45, 1])
        with left:
            st.markdown('<div class="section-title">Key credit metrics</div>', unsafe_allow_html=True)
            metrics = snap.get("metrics", [])
            if metrics and isinstance(metrics[0], dict) and "metric" in metrics[0]:
                st.dataframe(metrics, use_container_width=True, hide_index=True)
            else:
                st.info("Detailed generated metric table is available in the downloadable report.")
        with right:
            st.markdown('<div class="section-title">RM interpretation</div>', unsafe_allow_html=True)
            st.markdown('<div class="insight"><b>Credit:</b> sovereign linkage remains central; headline credit strength is not the main meeting topic.</div>', unsafe_allow_html=True)
            st.markdown('<div class="insight"><b>Commercial:</b> recurring offshore funding creates DCM, bilateral, money-market and FX/CCS angles.</div>', unsafe_allow_html=True)
            st.markdown('<div class="insight"><b>Discovery:</b> ask what changed in 2026 rather than asking KDB to repeat its published 2025 strategy.</div>', unsafe_allow_html=True)

        st.markdown('<div class="section-title">Top opportunities</div>', unsafe_allow_html=True)
        for item in snap.get("opportunities", []):
            css = "priority-high" if item.get("priority") == "High" else "priority-medium"
            st.markdown(
                f'<div class="opportunity"><span class="{css}">{item.get("priority")}</span> <b>{item.get("theme")}</b><br>'
                f'<span class="small-muted">{item.get("why")}</span><br><b>RM action:</b> {item.get("action")}</div>',
                unsafe_allow_html=True,
            )

    with credit:
        st.markdown("### Credit Intelligence")
        st.write("The dashboard separates extracted facts from derived metrics and flags contradictions instead of silently fixing them.")
        st.dataframe(snap.get("metrics", []), use_container_width=True, hide_index=True)
        warning = snap.get("warning")
        if warning:
            st.warning(warning)

    with funding:
        st.markdown("### Funding & Business Intelligence")
        st.dataframe(snap.get("funding", []), use_container_width=True, hide_index=True)
        sectors = snap.get("sector_exposure", [])
        if sectors:
            st.markdown("#### Sector exposure")
            st.bar_chart({x["sector"]: x["pct"] for x in sectors})
        st.caption("Freshness matters: 2025 funding execution is historical context. Client discovery should focus on the 2026 delta.")

    with opps:
        st.markdown("### Opportunity Intelligence")
        for idx, item in enumerate(snap.get("opportunities", []), start=1):
            css = "priority-high" if item.get("priority") == "High" else "priority-medium"
            st.markdown(
                f'<div class="opportunity"><span class="{css}">{item.get("priority")}</span> <b>{idx}. {item.get("theme")}</b><br><br>'
                f'<b>Why now:</b> {item.get("why")}<br><b>Suggested action:</b> {item.get("action")}</div>',
                unsafe_allow_html=True,
            )

    with meeting:
        st.markdown("### Meeting Discovery Playbook")
        st.caption("Pick only 2–3 objectives for a real meeting. The point is to uncover change, pipeline, wallet criteria and decision process — not to interrogate the client.")
        for i, question in enumerate(snap.get("meeting_questions", []), start=1):
            st.markdown(f"**{i}.** {question}")
        st.info("After the meeting, capture: timing · size · currency · sector · geography · decision maker · incumbent bank · next step.")

    with sources:
        st.markdown("### Download / evidence")
        d1, d2 = st.columns(2)
        with d1:
            st.download_button("Download RM report (.md)", report, file_name="kdb_rm_intelligence.md", mime="text/markdown", use_container_width=True)
        with d2:
            st.download_button("Download verified demo data (.json)", json.dumps(snap, indent=2, ensure_ascii=False), file_name="kdb_verified_demo.json", mime="application/json", use_container_width=True)
        with st.expander("Preview full report"):
            st.markdown(report)

elif workspace == "New Institution":
    st.markdown('<div class="hero"><h1>Add another institution</h1><p>Build a source pack first. High-reliability extraction is added only after source-specific validation.</p></div>', unsafe_allow_html=True)
    institution = st.text_input("Institution name", placeholder="e.g. DBS Bank, UOB, Maybank, Korea Eximbank")
    uploads = st.file_uploader("Upload source documents", type=["pdf", "txt", "md", "json"], accept_multiple_files=True)
    if uploads:
        docs = []
        for f in uploads:
            try:
                docs.append(extract_uploaded_file(f))
            except Exception as exc:
                st.error(f"Could not parse {f.name}: {exc}")
        if docs:
            pack = build_source_pack(institution or "Unnamed institution", docs)
            st.success(f"Loaded {len(docs)} document(s).")
            st.dataframe([{"file": d["name"], "type": d["type"], "characters": len(d["text"])} for d in docs], use_container_width=True, hide_index=True)
            st.download_button("Download source pack (.json)", json.dumps(pack, indent=2, ensure_ascii=False), file_name="institution_source_pack.json", mime="application/json")
            st.warning("Source pack created. Ratios remain unverified until this institution's source hierarchy and validation rules are configured.")

else:
    st.markdown('<div class="hero"><h1>Customize a report</h1><p>Upload a report and policy/rule files, apply supported directives, review, then download the modified version.</p></div>', unsafe_allow_html=True)
    base_report_file = st.file_uploader("Base report", type=["md", "txt"], key="base_report")
    rule_files = st.file_uploader("Rule / policy files", type=["pdf", "txt", "md"], accept_multiple_files=True, key="rules")
    manual_rules = st.text_area("Additional rules", placeholder="HIDE: Evidence ledger\nRENAME: Opportunity Intelligence => Business Opportunities\nMAX_QUESTIONS: 5\nDISCLAIMER: Internal working draft — verify before client use", height=140)

    if base_report_file:
        base_report = base_report_file.getvalue().decode("utf-8", errors="replace")
        rule_texts = []
        for f in rule_files or []:
            try:
                rule_texts.append(extract_uploaded_file(f)["text"])
            except Exception as exc:
                st.error(f"Could not parse {f.name}: {exc}")
        if manual_rules.strip():
            rule_texts.append(manual_rules)
        combined_rules = "\n".join(rule_texts)
        if combined_rules.strip():
            result = apply_text_rules(base_report, combined_rules)
            st.success("Rules processed. Review the result before download.")
            edited = st.text_area("Preview / manual edit", value=result["report"], height=620)
            st.caption("Applied directives: " + (", ".join(result["applied"]) if result["applied"] else "none detected"))
            st.download_button("Download modified report", edited, file_name="rm_intelligence_customized.md", mime="text/markdown")
        else:
            st.info("Upload a rule file or enter at least one supported directive.")
