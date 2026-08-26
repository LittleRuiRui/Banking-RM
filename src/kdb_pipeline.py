from __future__ import annotations

import argparse
import io
import json
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup
from pypdf import PdfReader

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CONFIG = ROOT / "config" / "kdb_sources.json"
DEFAULT_OUTPUT = ROOT / "data" / "kdb_public_snapshot.json"
USER_AGENT = "Banking-RM/0.4 source-validated-public-research"


@dataclass
class SourceDocument:
    name: str
    url: str
    kind: str
    text: str


METRIC_PATTERNS = {
    "cet1_ratio_pct": [r"CET1(?:\s+capital)?\s+ratio\s*[:：]?\s*(\d{1,2}\.\d{1,2})\s*%", r"Common Equity Tier\s*1(?:\s+capital)?\s+ratio\s*[:：]?\s*(\d{1,2}\.\d{1,2})\s*%"],
    "capital_adequacy_ratio_pct": [r"(?:BIS\s+)?capital adequacy ratio\s*[:：]?\s*(\d{1,2}\.\d{1,2})\s*%", r"total capital(?: adequacy)? ratio\s*[:：]?\s*(\d{1,2}\.\d{1,2})\s*%"],
    "npl_ratio_pct": [r"(?:NPL|non[- ]performing loan)\s+ratio\s*[:：]?\s*(\d{1,2}\.\d{1,2})\s*%"],
    "roe_pct": [r"(?:ROE|return on equity)\s*[:：]?\s*(\d{1,2}\.\d{1,2})\s*%"],
    "roa_pct": [r"(?:ROA|return on assets)\s*[:：]?\s*(\d{1,2}\.\d{1,2})\s*%"],
}
PROGRAMME_PATTERNS = {
    "gmt_programme_usd_bn": [r"(?:GMTN|Global MTN|Global Medium Term Note)[\s\S]{0,220}?(?:programme\s+size\s+of\s+)?U?S?\$\s*(\d+(?:\.\d+)?)\s*(?:bn|billion)", r"U?S?\$\s*(\d+(?:\.\d+)?)\s*(?:bn|billion)[\s\S]{0,120}?(?:GMTN|Global MTN|Global Medium Term Note)"],
    "uscp_programme_usd_bn": [r"USCP[\s\S]{0,180}?(?:programme\s+size\s+of\s+)?U?S?\$\s*(\d+(?:\.\d+)?)\s*(?:bn|billion)"],
    "ecp_programme_usd_bn": [r"(?:^|\s)ECP[\s\S]{0,180}?(?:programme\s+size\s+of\s+)?U?S?\$\s*(\d+(?:\.\d+)?)\s*(?:bn|billion)"],
}
RATING_PATTERN = re.compile(r"(?<![A-Za-z0-9])(?:Aaa|Aa[123]|Baa[123]|AAA|AA[+-]?|A[+-]?|BBB[+-]?|A[123])(?![A-Za-z0-9+-])", re.IGNORECASE)
SOURCE_PRIORITY = {"official_ratings": 100, "official_funding": 100, "investor_presentation": 90, "annual_report": 85, "pdf": 60, "html": 50}
METRIC_ALLOWED_KINDS = {
    "cet1_ratio_pct": {"investor_presentation", "annual_report"}, "capital_adequacy_ratio_pct": {"investor_presentation", "annual_report"},
    "npl_ratio_pct": {"investor_presentation", "annual_report"}, "roe_pct": {"investor_presentation", "annual_report"}, "roa_pct": {"investor_presentation", "annual_report"},
    "gmt_programme_usd_bn": {"official_funding", "investor_presentation"}, "uscp_programme_usd_bn": {"official_funding", "investor_presentation"}, "ecp_programme_usd_bn": {"official_funding", "investor_presentation"},
}


def session():
    s = requests.Session(); s.headers.update({"User-Agent": USER_AGENT}); return s

def load_config(path: Path): return json.loads(path.read_text())

def extract_html_text(s, url):
    r=s.get(url,timeout=30); r.raise_for_status(); soup=BeautifulSoup(r.text,"html.parser")
    for tag in soup(["script","style","noscript"]): tag.decompose()
    return "\n".join(x.strip() for x in soup.stripped_strings if x.strip())

def extract_pdf_text(s, url):
    r=s.get(url,timeout=60); r.raise_for_status(); reader=PdfReader(io.BytesIO(r.content)); chunks=[]
    for n,page in enumerate(reader.pages,start=1):
        text=page.extract_text() or ""
        if text.strip(): chunks.append(f"\n--- PAGE {n} ---\n{text}")
    return "\n".join(chunks)

def discover_pdf_links(s,page_url,keywords):
    r=s.get(page_url,timeout=30); r.raise_for_status(); soup=BeautifulSoup(r.text,"html.parser"); keys=[k.lower() for k in keywords]; out=[]
    for a in soup.find_all("a",href=True):
        href=a.get("href",""); label=" ".join(a.stripped_strings).strip(); hay=f"{label} {href}".lower()
        if ".pdf" in href.lower() and any(k in hay for k in keys): out.append((label or Path(href).name,urljoin(page_url,href)))
    return out

def first_float(text,patterns):
    for p in patterns:
        m=re.search(p,text,flags=re.IGNORECASE|re.MULTILINE)
        if m: return float(m.group(1))
    return None

def parse_metrics(text):
    v={k:first_float(text,p) for k,p in METRIC_PATTERNS.items()}
    for k,p in PROGRAMME_PATTERNS.items(): v[k]=first_float(text,p)
    v["ratings_detected"]=sorted(set(m.group(0).upper() for m in RATING_PATTERN.finditer(text)))
    return v

def evidence_snippets(text,terms:Iterable[str],radius=180):
    evidence={}; compact=re.sub(r"\s+"," ",text)
    for term in terms:
        snippets=[]
        for m in re.finditer(re.escape(term),compact,flags=re.IGNORECASE):
            snippets.append(compact[max(0,m.start()-radius):min(len(compact),m.end()+radius)].strip())
            if len(snippets)>=3: break
        if snippets: evidence[term]=snippets
    return evidence

def collect_documents(config):
    s=session(); docs=[]; seen=set()
    for item in config.get("authoritative_html",[]):
        try: docs.append(SourceDocument(item["name"],item["url"],item["kind"],extract_html_text(s,item["url"])))
        except Exception as exc: docs.append(SourceDocument(item["name"],item["url"],item["kind"]+"_error",f"ERROR: {exc}"))
        seen.add(item["url"])
    for seed in config.get("seed_pdfs",[]):
        try: docs.append(SourceDocument(seed["name"],seed["url"],seed.get("kind","pdf"),extract_pdf_text(s,seed["url"])))
        except Exception as exc: docs.append(SourceDocument(seed["name"],seed["url"],"pdf_error",f"ERROR: {exc}"))
        seen.add(seed["url"])
    for page in config.get("source_pages",[]):
        try:
            for label,url in discover_pdf_links(s,page["url"],page.get("keywords",[])):
                if url in seen: continue
                kind="annual_report" if "annual" in label.lower() else "pdf"
                try: docs.append(SourceDocument(label,url,kind,extract_pdf_text(s,url)))
                except Exception as exc: docs.append(SourceDocument(label,url,kind+"_error",f"ERROR: {exc}"))
                seen.add(url)
        except Exception: pass
    return docs

def _source_meta(d): return {"name":d.name,"url":d.url,"kind":d.kind,"trust_score":SOURCE_PRIORITY.get(d.kind,40)}

def choose_metric(documents,metric):
    allowed=METRIC_ALLOWED_KINDS.get(metric,set()); candidates=[]
    for d in documents:
        if d.kind.endswith("error") or d.kind not in allowed: continue
        value=parse_metrics(d.text).get(metric)
        if value is not None: candidates.append((SOURCE_PRIORITY.get(d.kind,40),value,d))
    if not candidates: return None,None,[]
    candidates.sort(key=lambda x:x[0],reverse=True); score,value,doc=candidates[0]
    corroboration=[{"value":v,"source":_source_meta(d)} for _,v,d in candidates[1:] if abs(v-value)<0.011]
    return value,_source_meta(doc),corroboration

def current_ratings(documents):
    # Ratings must come from KDB's dedicated official ratings page. Do not infer from bond-document rating scales.
    for d in documents:
        if d.kind=="official_ratings":
            text=re.sub(r"\s+"," ",d.text)
            expected=[]
            for pattern in [r"Aa2\s*\(?Stable\)?",r"(?<![A-Z])AA\s*\(?Stable\)?",r"AA-\s*\(?Stable\)?"]:
                m=re.search(pattern,text,re.IGNORECASE)
                if m: expected.append(re.sub(r"\s*\(?Stable\)?","",m.group(0),flags=re.IGNORECASE).upper())
            return expected,_source_meta(d)
    return [],None

def validate_snapshot(metrics,sources):
    checks=[]
    def add(name,ok,detail): checks.append({"check":name,"passed":bool(ok),"detail":detail})
    add("official_ratings_source",sources.get("ratings_detected",{}).get("kind")=="official_ratings","Ratings must come from dedicated KDB ratings page")
    for k,expected in [("gmt_programme_usd_bn",30.0),("uscp_programme_usd_bn",5.0),("ecp_programme_usd_bn",12.0)]:
        val=metrics.get(k); add(f"{k}_official",val==expected and sources.get(k,{}).get("kind")=="official_funding",f"Expected current official programme size {expected:g}bn")
    for k in ["cet1_ratio_pct","capital_adequacy_ratio_pct","npl_ratio_pct","roe_pct","roa_pct"]:
        val=metrics.get(k); add(f"{k}_plausible",val is None or 0<=val<=100,"Ratio must be within 0-100%; missing is safer than guessing")
    return checks

def build_snapshot(config,documents):
    names=list(METRIC_PATTERNS)+list(PROGRAMME_PATTERNS); metrics={}; sources={}; corroboration={}
    for metric in names:
        value,source,cross=choose_metric(documents,metric); metrics[metric]=value
        if source: sources[metric]=source
        if cross: corroboration[metric]=cross
    ratings,source=current_ratings(documents); metrics["ratings_detected"]=ratings
    if source: sources["ratings_detected"]=source
    checks=validate_snapshot(metrics,sources); passed=sum(c["passed"] for c in checks); quality=round(10*passed/len(checks),1) if checks else 0
    successful="\n".join(d.text for d in documents if not d.kind.endswith("error"))
    return {"client":config["client"],"generated_at":datetime.now(timezone.utc).isoformat(),"data_quality":{"score_out_of_10":quality,"checks":checks,"policy":"Only approved source types may populate each metric; missing beats inferred."},"metrics":metrics,"metric_sources":sources,"corroboration":corroboration,"evidence":evidence_snippets(successful,["government","funding","CET1","NPL","USD","GMTN","USCP","ECP","project finance","Southeast Asia"]),"sources":[{"name":d.name,"url":d.url,"kind":d.kind,"trust_score":SOURCE_PRIORITY.get(d.kind,40),"characters_extracted":len(d.text)} for d in documents]}

def main():
    p=argparse.ArgumentParser(); p.add_argument("--config",type=Path,default=DEFAULT_CONFIG); p.add_argument("--output",type=Path,default=DEFAULT_OUTPUT); args=p.parse_args()
    snapshot=build_snapshot(load_config(args.config),collect_documents(load_config(args.config))); args.output.parent.mkdir(parents=True,exist_ok=True); args.output.write_text(json.dumps(snapshot,indent=2,ensure_ascii=False)); print(f"Wrote {args.output}; quality={snapshot['data_quality']['score_out_of_10']}/10")
    # Fail CI if authoritative facts regress. This prevents a green build with low-quality data.
    if snapshot["data_quality"]["score_out_of_10"] < 9.0: raise SystemExit("Data-quality gate failed: score below 9.0/10")

if __name__=="__main__": main()
