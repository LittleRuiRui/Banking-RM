from __future__ import annotations

import json
from pathlib import Path

import streamlit as st

from src.upload_ingest import extract_uploaded_file, build_source_pack
from src.rule_customizer import apply_text_rules
from src.fi_credit_checker import check_credit_application

ROOT = Path(__file__).resolve().parent
SNAPSHOT = ROOT / "data" / "kdb_public_snapshot.json"
REPORT = ROOT / "reports" / "kdb_auto_brief.md"
DEMO_SNAPSHOT = ROOT / "data" / "kdb_demo_snapshot.json"
DEMO_REPORT = ROOT / "reports" / "kdb_demo_brief.md"

st.set_page_config(page_title="RM Intelligence", page_icon="🏦", layout="wide")

st.markdown("""
<style>
.block-container{padding-top:1.2rem;max-width:1400px}.card{border:1px solid #e6ebf2;border-radius:14px;padding:.9rem 1rem;background:#fff}.muted{color:#718096;font-size:.82rem}.good{color:#087a47;font-weight:700}.warn{color:#b45c00;font-weight:700}.hero{padding:1rem 1.2rem;border:1px solid #e7edf5;border-radius:16px;background:#f7faff;margin-bottom:1rem}[data-testid="stSidebar"]{background:#0b2545}[data-testid="stSidebar"] *{color:#f3f7fb!important}
</style>
""", unsafe_allow_html=True)


def load_data():
    if SNAPSHOT.exists():
        snap = json.loads(SNAPSHOT.read_text(encoding="utf-8"))
        report = REPORT.read_text(encoding="utf-8") if REPORT.exists() else ""
        return snap, report, "Generated pipeline snapshot"
    return json.loads(DEMO_SNAPSHOT.read_text(encoding="utf-8")), DEMO_REPORT.read_text(encoding="utf-8"), "Committed demo snapshot"


def card(label, value, note=""):
    st.markdown(f'<div class="card"><div class="muted">{label}</div><div style="font-size:1.45rem;font-weight:750;color:#10213b;margin:.2rem 0">{value}</div><div class="muted">{note}</div></div>', unsafe_allow_html=True)


with st.sidebar:
    st.markdown("## 🏦 RM Intelligence")
    workspace = st.radio("Workspace", ["KDB Demo", "FI Credit Checklist", "New Institution", "Customize Report"], label_visibility="collapsed")
    st.divider()
    st.caption("Public-source intelligence. Missing beats guessed. Metric freshness and source freshness are shown separately.")

if workspace == "KDB Demo":
    snap, report, mode = load_data()
    q = snap.get("data_quality", {})
    status = snap.get("source_status", {})
    metric_periods = snap.get("latest_verified_metric_periods", {})

    st.markdown(f'<div class="hero"><h2 style="margin:0">Korea Development Bank (KDB)</h2><div class="muted">Institutional RM Intelligence · {mode}</div></div>', unsafe_allow_html=True)

    c1,c2,c3,c4 = st.columns(4)
    with c1: card("Reliability", f"{q.get('reliability_score_out_of_10','n/a')}/10", "Verified extraction only")
    with c2: card("Coverage", f"{q.get('coverage_pct','n/a')}%", "Core MVP fields")
    with c3: card("Latest Annual Report", status.get("latest_annual_report",{}).get("period","unknown"), "Official KDB source")
    with c4: card("Latest Investor Update", status.get("latest_investor_update",{}).get("period","unknown"), "Separate from financial reporting period")

    if status.get("source_check_status") == "temporarily_unavailable":
        st.warning("Latest-source check was temporarily unavailable. The app retained the last verified source status instead of replacing it with guesses.")
    st.info("Latest public source and latest metric period are different concepts. Each metric keeps its own verified reporting period.")

    overview, credit, current, funding, meeting, evidence = st.tabs(["Overview","Credit","Current Developments","Funding & Business","Meeting Playbook","Evidence & Download"])

    with overview:
        st.markdown("### Source freshness")
        rows=[]
        for label,key in [("Annual report","latest_annual_report"),("IR presentation","latest_ir_presentation"),("Investor update","latest_investor_update"),("Ratings","current_ratings"),("Funding programmes","current_funding_programmes")]:
            x=status.get(key,{})
            rows.append({"source":label,"latest period":x.get("period","unknown"),"verified":x.get("verified_on_official_page", True),"url":x.get("url","")})
        st.dataframe(rows,use_container_width=True,hide_index=True)
        st.markdown("### Latest verified metric periods")
        if metric_periods:
            st.dataframe([{"metric":k,"latest verified period":v} for k,v in metric_periods.items()],use_container_width=True,hide_index=True)
        else:
            st.warning("Per-metric period map is not yet available in this snapshot.")

    with credit:
        st.markdown("### Credit Intelligence")
        metrics=snap.get("metrics",{})
        if isinstance(metrics,dict):
            rows=[]
            for k,v in metrics.items():
                if k=="ratings_detected": rows.append({"metric":"Ratings","value":", ".join(v) if isinstance(v,list) else v,"period":metric_periods.get(k,"current")})
                else: rows.append({"metric":k,"value":v,"period":metric_periods.get(k,"unknown")})
            st.dataframe(rows,use_container_width=True,hide_index=True)
        else:
            st.dataframe(metrics,use_container_width=True,hide_index=True)
        for flag in snap.get("consistency_flags",[]): st.warning(flag.get("detail",str(flag)))

    with current:
        st.markdown("### 2026 Current Developments")
        updates=snap.get("current_developments",[])
        if updates:
            for u in updates:
                st.markdown(f"**{u.get('topic','Update').title()}**")
                st.caption(u.get("evidence_snippet",""))
        else:
            st.info("The official 2026 investor-update source is tracked, but no safe text snippets were parsed into the current snapshot yet.")

    with funding:
        st.markdown("### Funding & Business Intelligence")
        r=snap.get("rm_intelligence",{})
        for name,key in [("Funding structure","funding_structure"),("Funding strategy","funding_strategy"),("Outstanding funding","outstanding_funding"),("Sector exposure","sector_exposure")]:
            block=r.get(key,{})
            if block:
                st.markdown(f"#### {name}")
                st.json(block)
        for sig in r.get("signals",[]):
            st.markdown(f"**{sig.get('priority','').upper()} — {sig.get('type','signal')}**: {sig.get('fact','')}  ")
            st.caption(sig.get("rm_angle",""))

    with meeting:
        st.markdown("### Meeting Discovery Playbook")
        questions=snap.get("meeting_questions") or ["What has changed in your offshore funding plan versus last year?","Which currencies and tenors are currently most attractive at the margin?","Where is international-bank participation most useful in KDB-led overseas financings?","Which sectors or geographies are taking more management attention in 2026?"]
        for i,qx in enumerate(questions,1): st.markdown(f"**{i}.** {qx}")

    with evidence:
        st.markdown("### Evidence & downloads")
        st.download_button("Download snapshot (.json)",json.dumps(snap,indent=2,ensure_ascii=False),file_name="kdb_latest_snapshot.json",mime="application/json",use_container_width=True)
        if report: st.download_button("Download RM report (.md)",report,file_name="kdb_rm_intelligence.md",mime="text/markdown",use_container_width=True)
        st.markdown("#### Metric evidence")
        st.json(snap.get("metric_evidence",{}))

elif workspace == "FI Credit Checklist":
    st.markdown('<div class="hero"><h2 style="margin:0">FI Credit Application Checker</h2><div class="muted">Upload a credit application and run the 18-module completeness / freshness / internal-required check before submission.</div></div>', unsafe_allow_html=True)
    credit_file = st.file_uploader("Upload FI credit application", type=["pdf","txt","md"], key="fi_credit")
    if credit_file:
        try:
            doc = extract_uploaded_file(credit_file)
            result = check_credit_application(doc["text"])
            st.success(f"Checked {credit_file.name}. Latest year detected in document: {result.get('latest_year_detected') or 'unknown'}")
            if result.get("entity_scope_warning"): st.warning(result["entity_scope_warning"])
            st.dataframe(result["rows"], use_container_width=True, hide_index=True)
            st.markdown("### Gap List")
            for bucket in ["Blocking before submission","Should update","Nice to improve"]:
                items=result["gap_list"].get(bucket,[])
                with st.expander(f"{bucket} ({len(items)})", expanded=(bucket=="Blocking before submission")):
                    if items:
                        for item in items: st.markdown(f"- {item}")
                    else: st.caption("No items detected")
            st.markdown("### Critical stale fields")
            if result["outdated_critical_fields"]:
                st.dataframe(result["outdated_critical_fields"], use_container_width=True, hide_index=True)
            else:
                st.caption("No clearly stale critical fields detected by the first-pass checker.")
            st.info("Internal-only fields are never guessed. Missing internal rating, KYC/AML, exposure, country limit, concentration, approval authority, RAROC/EVA, FTP income and pipeline are flagged as INTERNAL REQUIRED.")
            st.download_button("Download gap analysis (.json)", json.dumps(result,indent=2,ensure_ascii=False), file_name="fi_credit_gap_analysis.json", mime="application/json", use_container_width=True)
        except Exception as exc:
            st.error(f"Could not analyze file: {exc}")

elif workspace == "New Institution":
    st.markdown('<div class="hero"><h2 style="margin:0">Analyze another institution</h2><div class="muted">Upload official source documents first; institution-specific validation rules are required before ratios are treated as credit-grade.</div></div>', unsafe_allow_html=True)
    institution=st.text_input("Institution name",placeholder="e.g. DBS Bank, UOB, Maybank, Korea Eximbank")
    uploads=st.file_uploader("Upload annual reports / investor presentations / rating or funding documents",type=["pdf","txt","md","json"],accept_multiple_files=True)
    if uploads:
        docs=[]
        for f in uploads:
            try: docs.append(extract_uploaded_file(f))
            except Exception as exc: st.error(f"Could not parse {f.name}: {exc}")
        if docs:
            pack=build_source_pack(institution or "Unnamed institution",docs)
            st.dataframe([{"file":d["name"],"type":d["type"],"characters":len(d["text"])} for d in docs],use_container_width=True,hide_index=True)
            st.download_button("Download source pack",json.dumps(pack,indent=2,ensure_ascii=False),file_name="institution_source_pack.json",mime="application/json")

else:
    st.markdown('<div class="hero"><h2 style="margin:0">Customize a report</h2><div class="muted">Upload a base report and policy/rule documents, review the changes, then download.</div></div>', unsafe_allow_html=True)
    base=st.file_uploader("Base report",type=["md","txt"],key="base")
    rules=st.file_uploader("Rule / policy files",type=["pdf","txt","md"],accept_multiple_files=True,key="rules")
    manual=st.text_area("Additional rules",placeholder="HIDE: Evidence ledger\nMAX_QUESTIONS: 5\nDISCLAIMER: Internal working draft — verify before client use")
    if base:
        base_text=base.getvalue().decode("utf-8",errors="replace")
        rule_text=[]
        for f in rules or []:
            try: rule_text.append(extract_uploaded_file(f)["text"])
            except Exception as exc: st.error(f"Could not parse {f.name}: {exc}")
        if manual.strip(): rule_text.append(manual)
        if rule_text:
            result=apply_text_rules(base_text,"\n".join(rule_text))
            edited=st.text_area("Preview / manual edit",value=result["report"],height=620)
            st.download_button("Download modified report",edited,file_name="rm_intelligence_customized.md",mime="text/markdown")
