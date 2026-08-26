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
USER_AGENT = "Banking-RM/0.5 traceable-public-research"


@dataclass
class SourceDocument:
    name: str
    url: str
    kind: str
    text: str
    reporting_period: str | None = None
    section: str | None = None


METRIC_PATTERNS = {
    "cet1_ratio_pct": [
        r"CET1(?:\s+capital)?\s+ratio\s*[:：]?\s*(\d{1,2}\.\d{1,2})\s*%",
        r"Common Equity Tier\s*1(?:\s+capital)?\s+ratio\s*[:：]?\s*(\d{1,2}\.\d{1,2})\s*%",
    ],
    "capital_adequacy_ratio_pct": [
        r"(?:BIS\s+)?capital adequacy ratio\s*[:：]?\s*(\d{1,2}\.\d{1,2})\s*%",
        r"total capital(?: adequacy)? ratio\s*[:：]?\s*(\d{1,2}\.\d{1,2})\s*%",
    ],
    "npl_ratio_pct": [r"(?:NPL|non[- ]performing loan)\s+ratio\s*[:：]?\s*(\d{1,2}\.\d{1,2})\s*%"],
    "roe_pct": [r"(?:ROE|return on equity)\s*[:：]?\s*(\d{1,2}\.\d{1,2})\s*%"],
    "roa_pct": [r"(?:ROA|return on assets)\s*[:：]?\s*(\d{1,2}\.\d{1,2})\s*%"],
}

PROGRAMME_PATTERNS = {
    "gmt_programme_usd_bn": [
        r"(?:GMTN|Global MTN|Global Medium Term Note)[\s\S]{0,220}?(?:programme\s+size\s+of\s+)?U?S?\$\s*(\d+(?:\.\d+)?)\s*(?:bn|billion)",
        r"U?S?\$\s*(\d+(?:\.\d+)?)\s*(?:bn|billion)[\s\S]{0,120}?(?:GMTN|Global MTN|Global Medium Term Note)",
    ],
    "uscp_programme_usd_bn": [r"USCP[\s\S]{0,180}?(?:programme\s+size\s+of\s+)?U?S?\$\s*(\d+(?:\.\d+)?)\s*(?:bn|billion)"],
    "ecp_programme_usd_bn": [r"(?:^|\s)ECP[\s\S]{0,180}?(?:programme\s+size\s+of\s+)?U?S?\$\s*(\d+(?:\.\d+)?)\s*(?:bn|billion)"],
}

RATING_PATTERN = re.compile(
    r"(?<![A-Za-z0-9])(?:Aaa|Aa[123]|Baa[123]|AAA|AA[+-]?|A[+-]?|BBB[+-]?|A[123])(?![A-Za-z0-9+-])",
    re.IGNORECASE,
)

SOURCE_PRIORITY = {
    "official_ratings": 100,
    "official_funding": 100,
    "investor_presentation": 90,
    "annual_report": 85,
    "pdf": 60,
    "html": 50,
}

METRIC_ALLOWED_KINDS = {
    "cet1_ratio_pct": {"investor_presentation", "annual_report"},
    "capital_adequacy_ratio_pct": {"investor_presentation", "annual_report"},
    "npl_ratio_pct": {"investor_presentation", "annual_report"},
    "roe_pct": {"investor_presentation", "annual_report"},
    "roa_pct": {"investor_presentation", "annual_report"},
    "gmt_programme_usd_bn": {"official_funding", "investor_presentation"},
    "uscp_programme_usd_bn": {"official_funding", "investor_presentation"},
    "ecp_programme_usd_bn": {"official_funding", "investor_presentation"},
}


def session() -> requests.Session:
    s = requests.Session()
    s.headers.update({"User-Agent": USER_AGENT})
    return s


def load_config(path: Path) -> dict:
    return json.loads(path.read_text())


def extract_html_text(s: requests.Session, url: str) -> str:
    r = s.get(url, timeout=30)
    r.raise_for_status()
    soup = BeautifulSoup(r.text, "html.parser")
    for tag in soup(["script", "style", "noscript"]):
        tag.decompose()
    return "\n".join(x.strip() for x in soup.stripped_strings if x.strip())


def extract_pdf_text(s: requests.Session, url: str) -> str:
    r = s.get(url, timeout=60)
    r.raise_for_status()
    reader = PdfReader(io.BytesIO(r.content))
    chunks: list[str] = []
    for n, page in enumerate(reader.pages, start=1):
        text = page.extract_text() or ""
        if text.strip():
            chunks.append(f"\n--- PAGE {n} ---\n{text}")
    return "\n".join(chunks)


def discover_pdf_links(s: requests.Session, page_url: str, keywords: Iterable[str]) -> list[tuple[str, str]]:
    r = s.get(page_url, timeout=30)
    r.raise_for_status()
    soup = BeautifulSoup(r.text, "html.parser")
    keys = [k.lower() for k in keywords]
    out: list[tuple[str, str]] = []
    for a in soup.find_all("a", href=True):
        href = a.get("href", "")
        label = " ".join(a.stripped_strings).strip()
        hay = f"{label} {href}".lower()
        if ".pdf" in href.lower() and any(k in hay for k in keys):
            out.append((label or Path(href).name, urljoin(page_url, href)))
    return out


def first_float(text: str, patterns: list[str]) -> float | None:
    for pattern in patterns:
        m = re.search(pattern, text, flags=re.IGNORECASE | re.MULTILINE)
        if m:
            return float(m.group(1))
    return None


def parse_metrics(text: str) -> dict:
    values = {k: first_float(text, p) for k, p in METRIC_PATTERNS.items()}
    for k, p in PROGRAMME_PATTERNS.items():
        values[k] = first_float(text, p)
    values["ratings_detected"] = sorted(set(m.group(0).upper() for m in RATING_PATTERN.finditer(text)))
    return values


def _pattern_for_metric(metric: str) -> list[str]:
    if metric in METRIC_PATTERNS:
        return METRIC_PATTERNS[metric]
    return PROGRAMME_PATTERNS.get(metric, [])


def _page_at_position(text: str, pos: int) -> int | None:
    page = None
    for m in re.finditer(r"--- PAGE (\d+) ---", text[:pos]):
        page = int(m.group(1))
    return page


def _compact_snippet(text: str, start: int, end: int, radius: int = 170) -> str:
    raw = text[max(0, start - radius):min(len(text), end + radius)]
    return re.sub(r"\s+", " ", raw).strip()


def _infer_reporting_period(doc: SourceDocument) -> str:
    if doc.reporting_period:
        return doc.reporting_period
    m = re.search(r"(20\d{2})(?:[-_/ ]?(0?[1-9]|1[0-2]))?", doc.name)
    if not m:
        return "unknown"
    return m.group(1) + (f"-{int(m.group(2)):02d}" if m.group(2) else "")


def locate_metric_evidence(doc: SourceDocument, metric: str) -> dict | None:
    for pattern in _pattern_for_metric(metric):
        m = re.search(pattern, doc.text, flags=re.IGNORECASE | re.MULTILINE)
        if not m:
            continue
        return {
            "source_name": doc.name,
            "source_url": doc.url,
            "source_kind": doc.kind,
            "reporting_period": _infer_reporting_period(doc),
            "page": _page_at_position(doc.text, m.start()),
            "section": doc.section or ("Funding Programmes" if doc.kind == "official_funding" else None),
            "evidence_snippet": _compact_snippet(doc.text, m.start(), m.end()),
            "matched_text": re.sub(r"\s+", " ", m.group(0)).strip(),
        }
    return None


def evidence_snippets(text: str, terms: Iterable[str], radius: int = 180) -> dict[str, list[str]]:
    evidence: dict[str, list[str]] = {}
    compact = re.sub(r"\s+", " ", text)
    for term in terms:
        snippets = []
        for m in re.finditer(re.escape(term), compact, flags=re.IGNORECASE):
            snippets.append(compact[max(0, m.start() - radius):min(len(compact), m.end() + radius)].strip())
            if len(snippets) >= 3:
                break
        if snippets:
            evidence[term] = snippets
    return evidence


def collect_documents(config: dict) -> list[SourceDocument]:
    s = session()
    docs: list[SourceDocument] = []
    seen: set[str] = set()

    for item in config.get("authoritative_html", []):
        try:
            text = extract_html_text(s, item["url"])
            docs.append(SourceDocument(item["name"], item["url"], item["kind"], text, item.get("reporting_period"), item.get("section")))
        except Exception as exc:
            docs.append(SourceDocument(item["name"], item["url"], item["kind"] + "_error", f"ERROR: {exc}", item.get("reporting_period"), item.get("section")))
        seen.add(item["url"])

    for seed in config.get("seed_pdfs", []):
        try:
            text = extract_pdf_text(s, seed["url"])
            docs.append(SourceDocument(seed["name"], seed["url"], seed.get("kind", "pdf"), text, seed.get("reporting_period"), seed.get("section")))
        except Exception as exc:
            docs.append(SourceDocument(seed["name"], seed["url"], "pdf_error", f"ERROR: {exc}", seed.get("reporting_period"), seed.get("section")))
        seen.add(seed["url"])

    for page in config.get("source_pages", []):
        try:
            links = discover_pdf_links(s, page["url"], page.get("keywords", []))
            for label, url in links:
                if url in seen:
                    continue
                kind = "annual_report" if "annual" in label.lower() else "pdf"
                try:
                    text = extract_pdf_text(s, url)
                    period = page.get("reporting_period") or _infer_reporting_period(SourceDocument(label, url, kind, ""))
                    docs.append(SourceDocument(label, url, kind, text, period, None))
                except Exception as exc:
                    docs.append(SourceDocument(label, url, kind + "_error", f"ERROR: {exc}", page.get("reporting_period"), None))
                seen.add(url)
        except Exception:
            pass
    return docs


def _source_meta(d: SourceDocument) -> dict:
    return {
        "name": d.name,
        "url": d.url,
        "kind": d.kind,
        "trust_score": SOURCE_PRIORITY.get(d.kind, 40),
        "reporting_period": _infer_reporting_period(d),
    }


def choose_metric(documents: list[SourceDocument], metric: str):
    allowed = METRIC_ALLOWED_KINDS.get(metric, set())
    candidates = []
    for d in documents:
        if d.kind.endswith("error") or d.kind not in allowed:
            continue
        value = parse_metrics(d.text).get(metric)
        if value is None:
            continue
        evidence = locate_metric_evidence(d, metric)
        candidates.append((SOURCE_PRIORITY.get(d.kind, 40), value, d, evidence))
    if not candidates:
        return None, None, [], None
    candidates.sort(key=lambda x: x[0], reverse=True)
    _, value, doc, evidence = candidates[0]
    corroboration = [
        {"value": v, "source": _source_meta(d), "evidence": ev}
        for _, v, d, ev in candidates[1:]
        if abs(v - value) < 0.011
    ]
    return value, _source_meta(doc), corroboration, evidence


def current_ratings(documents: list[SourceDocument]):
    for d in documents:
        if d.kind != "official_ratings":
            continue
        text = re.sub(r"\s+", " ", d.text)
        found: list[str] = []
        snippets: list[str] = []
        for pattern in [r"Aa2\s*\(?Stable\)?", r"(?<![A-Z])AA\s*\(?Stable\)?", r"AA-\s*\(?Stable\)?"]:
            m = re.search(pattern, text, re.IGNORECASE)
            if m:
                rating = re.sub(r"\s*\(?Stable\)?", "", m.group(0), flags=re.IGNORECASE).upper()
                found.append(rating)
                snippets.append(_compact_snippet(text, m.start(), m.end(), 100))
        evidence = {
            "source_name": d.name,
            "source_url": d.url,
            "source_kind": d.kind,
            "reporting_period": _infer_reporting_period(d),
            "page": None,
            "section": d.section or "International Credit Ratings",
            "evidence_snippet": " | ".join(snippets),
            "matched_text": ", ".join(found),
        } if found else None
        return found, _source_meta(d), evidence
    return [], None, None


def validate_snapshot(metrics: dict, sources: dict, metric_evidence: dict) -> list[dict]:
    checks: list[dict] = []

    def add(name: str, ok: bool, detail: str):
        checks.append({"check": name, "passed": bool(ok), "detail": detail})

    add("official_ratings_source", sources.get("ratings_detected", {}).get("kind") == "official_ratings", "Ratings must come from dedicated KDB ratings page")
    add("ratings_traceable", bool(metric_evidence.get("ratings_detected", {}).get("evidence_snippet")), "Ratings require evidence text")

    for k, expected in [("gmt_programme_usd_bn", 30.0), ("uscp_programme_usd_bn", 5.0), ("ecp_programme_usd_bn", 12.0)]:
        val = metrics.get(k)
        add(f"{k}_official", val == expected and sources.get(k, {}).get("kind") == "official_funding", f"Expected current official programme size {expected:g}bn")
        add(f"{k}_traceable", bool(metric_evidence.get(k, {}).get("evidence_snippet")), "Programme size requires evidence text")

    for k in ["cet1_ratio_pct", "capital_adequacy_ratio_pct", "npl_ratio_pct", "roe_pct", "roa_pct"]:
        val = metrics.get(k)
        add(f"{k}_plausible", val is None or 0 <= val <= 100, "Ratio must be within 0-100%; missing is safer than guessing")
        if val is not None:
            ev = metric_evidence.get(k, {})
            add(f"{k}_traceable", bool(ev.get("evidence_snippet")) and ev.get("reporting_period") not in (None, "unknown"), "Extracted ratios require evidence and reporting period")
    return checks


def build_snapshot(config: dict, documents: list[SourceDocument]) -> dict:
    names = list(METRIC_PATTERNS) + list(PROGRAMME_PATTERNS)
    metrics: dict = {}
    sources: dict = {}
    corroboration: dict = {}
    metric_evidence: dict = {}

    for metric in names:
        value, source, cross, evidence = choose_metric(documents, metric)
        metrics[metric] = value
        if source:
            sources[metric] = source
        if cross:
            corroboration[metric] = cross
        if evidence:
            metric_evidence[metric] = evidence

    ratings, source, evidence = current_ratings(documents)
    metrics["ratings_detected"] = ratings
    if source:
        sources["ratings_detected"] = source
    if evidence:
        metric_evidence["ratings_detected"] = evidence

    checks = validate_snapshot(metrics, sources, metric_evidence)
    passed = sum(c["passed"] for c in checks)
    quality = round(10 * passed / len(checks), 1) if checks else 0
    successful = "\n".join(d.text for d in documents if not d.kind.endswith("error"))

    return {
        "client": config["client"],
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "data_quality": {
            "score_out_of_10": quality,
            "checks": checks,
            "policy": "Only approved source types may populate each metric; every populated metric must carry source, reporting period and evidence; missing beats inferred.",
        },
        "metrics": metrics,
        "metric_sources": sources,
        "metric_evidence": metric_evidence,
        "corroboration": corroboration,
        "evidence": evidence_snippets(successful, ["government", "funding", "CET1", "NPL", "USD", "GMTN", "USCP", "ECP", "project finance", "Southeast Asia"]),
        "sources": [
            {
                "name": d.name,
                "url": d.url,
                "kind": d.kind,
                "trust_score": SOURCE_PRIORITY.get(d.kind, 40),
                "reporting_period": _infer_reporting_period(d),
                "characters_extracted": len(d.text),
            }
            for d in documents
        ],
    }


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    p.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = p.parse_args()
    config = load_config(args.config)
    snapshot = build_snapshot(config, collect_documents(config))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(snapshot, indent=2, ensure_ascii=False))
    print(f"Wrote {args.output}; quality={snapshot['data_quality']['score_out_of_10']}/10")
    if snapshot["data_quality"]["score_out_of_10"] < 9.0:
        raise SystemExit("Data-quality gate failed: score below 9.0/10")


if __name__ == "__main__":
    main()
