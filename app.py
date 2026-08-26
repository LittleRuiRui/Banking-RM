from __future__ import annotations

import json
from pathlib import Path

import streamlit as st

from src.upload_ingest import extract_uploaded_file, build_source_pack
from src.rule_customizer import apply_text_rules

ROOT = Path(__file__).resolve().parent
KDB_REPORT = ROOT / "reports" / "kdb_auto_brief.md"
KDB_SNAPSHOT = ROOT / "data" / "kdb_public_snapshot.json"

st.set_page_config(page_title="Banking RM Intelligence", layout="wide")
st.title("Banking RM Intelligence")
st.caption("Public-data intelligence + optional uploaded context. No bank-core-system integration required.")

with st.sidebar:
    st.header("Workspace")
    institution = st.text_input("Institution", value="Korea Development Bank")
    st.info("KDB is the verified automated demo. Other institutions can use the same workflow, but high-reliability extraction requires institution/source-specific validation rules.")

home, new_inst, customize = st.tabs(["KDB Demo", "New Institution", "Customize Report"])

with home:
    st.subheader("KDB verified demo")
    if KDB_REPORT.exists():
        report = KDB_REPORT.read_text(encoding="utf-8")
        st.markdown(report)
        st.download_button("Download report (.md)", report, file_name="kdb_rm_intelligence.md", mime="text/markdown")
    else:
        st.warning("Run the pipeline first: python -m src.kdb_pipeline && python -m src.coverage_enrichment && python -m src.provenance_fixups && python -m src.rm_intelligence_enrichment && python -m src.rm_brief")

    if KDB_SNAPSHOT.exists():
        raw = KDB_SNAPSHOT.read_text(encoding="utf-8")
        st.download_button("Download verified snapshot (.json)", raw, file_name="kdb_public_snapshot.json", mime="application/json")

with new_inst:
    st.subheader("Create a source pack for another institution")
    st.write("Upload annual reports, investor presentations, rating reports, funding documents or your approved internal/public notes. The app extracts text and creates a source inventory. It does not invent metrics from unsupported documents.")
    uploads = st.file_uploader(
        "Upload source documents",
        type=["pdf", "txt", "md", "json"],
        accept_multiple_files=True,
        key="institution_sources",
    )
    if uploads:
        docs = []
        for f in uploads:
            try:
                docs.append(extract_uploaded_file(f))
            except Exception as exc:
                st.error(f"Could not parse {f.name}: {exc}")
        if docs:
            pack = build_source_pack(institution, docs)
            st.success(f"Loaded {len(docs)} document(s).")
            st.dataframe(
                [{"file": d["name"], "type": d["type"], "characters": len(d["text"])} for d in docs],
                use_container_width=True,
                hide_index=True,
            )
            st.download_button(
                "Download source pack (.json)",
                json.dumps(pack, indent=2, ensure_ascii=False),
                file_name=f"{institution.lower().replace(' ', '_')}_source_pack.json",
                mime="application/json",
            )
            st.caption("Next production step: add validated extraction rules for this institution/source family before treating extracted ratios as credit-grade facts.")

with customize:
    st.subheader("Upload a report + rules and modify the output")
    st.write("Supported rule directives: HIDE, RENAME, DISCLAIMER, MAX_QUESTIONS, REQUIRE. Natural-language policy files are also extracted and shown for review, but only supported directives are applied automatically in this prototype.")

    base_report_file = st.file_uploader("Upload base report (.md/.txt)", type=["md", "txt"], key="base_report")
    rule_files = st.file_uploader("Upload rule / policy files", type=["pdf", "txt", "md"], accept_multiple_files=True, key="rules")
    manual_rules = st.text_area(
        "Additional rules",
        placeholder="HIDE: Evidence ledger\nRENAME: Opportunity Intelligence => Business Opportunities\nMAX_QUESTIONS: 5\nDISCLAIMER: Internal working draft — verify before client use",
        height=140,
    )

    if base_report_file:
        base_report = base_report_file.getvalue().decode("utf-8", errors="replace")
        rule_texts = []
        for f in rule_files or []:
            parsed = extract_uploaded_file(f)
            rule_texts.append(parsed["text"])
        if manual_rules.strip():
            rule_texts.append(manual_rules)

        combined_rules = "\n".join(rule_texts)
        if combined_rules.strip():
            result = apply_text_rules(base_report, combined_rules)
            st.markdown("### Modified report")
            st.text_area("Preview / manual edit", value=result["report"], height=600, key="modified_report")
            st.caption("Applied directives: " + (", ".join(result["applied"]) if result["applied"] else "none detected"))
            st.download_button(
                "Download modified report",
                result["report"],
                file_name="rm_intelligence_customized.md",
                mime="text/markdown",
            )
        else:
            st.info("Upload a rule file or enter at least one rule.")
