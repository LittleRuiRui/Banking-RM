from __future__ import annotations

import json

import streamlit as st

from src.cacib_credit_audit import audit_cacib_application, demo_findings, load_registry
from src.upload_ingest import extract_uploaded_file

st.set_page_config(page_title="CACIB Credit Refresh", page_icon="🏦", layout="wide")

st.markdown("""
<style>
.block-container{padding-top:1.2rem;max-width:1400px}.card{border:1px solid #e6ebf2;border-radius:14px;padding:.9rem 1rem;background:#fff}.muted{color:#718096;font-size:.82rem}.hero{padding:1rem 1.2rem;border:1px solid #e7edf5;border-radius:16px;background:#f7faff;margin-bottom:1rem}
</style>
""", unsafe_allow_html=True)

registry = load_registry()

st.markdown('<div class="hero"><h2 style="margin:0">CACIB Singapore Branch — Credit Application Refresh</h2><div class="muted">Audit an existing FI credit application against the correct entity, reporting period and latest official source hierarchy.</div></div>', unsafe_allow_html=True)

st.warning("Credit subject ≠ consolidated reporting entity. Singapore-branch/client facts belong to CACIB Singapore Branch; consolidated bank financials belong to CACIB; CASA / Crédit Agricole Group data should only be used for parent-support or group context.")

c1, c2, c3 = st.columns(3)
with c1:
    st.metric("Latest current-performance source", "H1 2026", "CACIB Q2/H1 results")
with c2:
    st.metric("Latest detailed risk disclosure", "FY2025", "CACIB 2025 URD")
with c3:
    st.metric("Source rule", "Entity-tagged", "No silent CASA/CACIB substitution")

source_tab, demo_tab, upload_tab, policy_tab = st.tabs(["Latest sources", "Demo audit", "Upload application", "Audit rules"])

with source_tab:
    st.markdown("### Current official source registry")
    rows = []
    for s in registry.get("sources", []):
        rows.append({
            "source": s["name"],
            "entity": s["entity"],
            "reporting period": s["reporting_period"],
            "published": s["publication_date"],
            "type": s["source_type"],
            "best for": ", ".join(s.get("best_for", [])),
            "url": s["url"],
        })
    st.dataframe(rows, use_container_width=True, hide_index=True)
    st.info("Latest ≠ blindly newest. H1 2026 is preferred for current performance; FY2025 URD remains the preferred detailed source for risk, balance sheet, Stage/NPL, liabilities and other disclosures when H1 does not provide comparable detail.")

with demo_tab:
    st.markdown("### Findings from the CACIB application screenshots")
    findings = demo_findings()
    st.dataframe(findings, use_container_width=True, hide_index=True)
    red = sum(1 for x in findings if x["priority"] == "RED")
    amber = sum(1 for x in findings if x["priority"] == "AMBER")
    st.caption(f"Observed first-pass findings: {red} RED / {amber} AMBER. These are document-review observations from the supplied screenshots, not invented financial facts.")

with upload_tab:
    st.markdown("### Upload the original credit application")
    st.caption("Best result: upload the original PDF. The checker preserves internal-only fields as INTERNAL REQUIRED and does not invent replacement numbers.")
    uploaded = st.file_uploader("FI Credit Application", type=["pdf", "txt", "md"], key="cacib_credit")
    if uploaded:
        try:
            doc = extract_uploaded_file(uploaded)
            result = audit_cacib_application(doc["text"])
            if result.get("entity_scope_warning"):
                st.warning(result["entity_scope_warning"])
            a, b = st.columns(2)
            with a: st.metric("RED", result["counts"].get("RED", 0))
            with b: st.metric("AMBER", result["counts"].get("AMBER", 0))

            st.markdown("### Work queue")
            findings = result.get("findings", [])
            if findings:
                st.dataframe(findings, use_container_width=True, hide_index=True)
            else:
                st.success("No deterministic stale-period or internal-gap findings detected. Manual credit review is still required.")

            st.markdown("### Entity hierarchy")
            for i, entity in enumerate(result["entity_hierarchy"], 1):
                st.markdown(f"**{i}.** {entity}")

            st.download_button(
                "Download CACIB audit (.json)",
                json.dumps(result, indent=2, ensure_ascii=False),
                file_name="cacib_credit_refresh_audit.json",
                mime="application/json",
                use_container_width=True,
            )
        except Exception as exc:
            st.error(f"Could not analyze file: {exc}")

with policy_tab:
    st.markdown("### Source taxonomy")
    for item in registry.get("source_taxonomy", []):
        st.markdown(f"- **{item}**")
    st.markdown("### Core policy")
    st.info(registry["policy"])
    st.markdown("### Replacement policy")
    st.markdown("""
- **Reported facts:** update only from a source belonging to the correct entity and comparable reporting basis.
- **Internal fields:** flag `INTERNAL REQUIRED`; never infer from public data.
- **Base / Stress Case:** classify as `ANALYST ASSUMPTION`; recalibrate against latest actuals but do not auto-replace scenario assumptions.
- **Parent / group data:** label explicitly as parent support or group context; never present CASA or Group ratios as CACIB ratios.
- **Detailed disclosures:** if H1 2026 lacks comparable Stage/NPL/sector/geography detail, retain FY2025 URD as the latest detailed basis instead of forcing a newer but incomplete period.
""")
