from __future__ import annotations

import argparse
import io
import json
import re
from dataclasses import dataclass, asdict
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
USER_AGENT = "Banking-RM/0.2 public-data-research"


@dataclass
class SourceDocument:
    name: str
    url: str
    kind: str
    text: str


METRIC_PATTERNS = {
    "cet1_ratio_pct": [
        r"CET1(?:\s+capital)?\s+ratio\s*[:：]?\s*(\d{1,2}\.\d{1,2})\s*%",
        r"Common Equity Tier\s*1(?:\s+capital)?\s+ratio\s*[:：]?\s*(\d{1,2}\.\d{1,2})\s*%",
    ],
    "capital_adequacy_ratio_pct": [
        r"(?:BIS\s+)?capital adequacy ratio\s*[:：]?\s*(\d{1,2}\.\d{1,2})\s*%",
    ],
    "npl_ratio_pct": [
        r"(?:NPL|non[- ]performing loan)\s+ratio\s*[:：]?\s*(\d{1,2}\.\d{1,2})\s*%",
    ],
    "roe_pct": [
        r"(?:ROE|return on equity)\s*[:：]?\s*(\d{1,2}\.\d{1,2})\s*%",
    ],
    "roa_pct": [
        r"(?:ROA|return on assets)\s*[:：]?\s*(\d{1,2}\.\d{1,2})\s*%",
    ],
}

PROGRAMME_PATTERNS = {
    "gmt_programme_usd_bn": r"(?:GMTN|Global Medium Term Note)[^\n]{0,120}?US\$?\s*(\d+(?:\.\d+)?)\s*(?:bn|billion)",
    "uscp_programme_usd_bn": r"USCP[^\n]{0,120}?US\$?\s*(\d+(?:\.\d+)?)\s*(?:bn|billion)",
    "ecp_programme_usd_bn": r"ECP[^\n]{0,120}?US\$?\s*(\d+(?:\.\d+)?)\s*(?:bn|billion)",
}

RATING_PATTERN = re.compile(
    r"\b(Aaa|Aa[123]|A[123]|Baa[123]|AAA|AA[+-]?|A[+-]?|BBB[+-]?)\b",
    re.IGNORECASE,
)


def session() -> requests.Session:
    s = requests.Session()
    s.headers.update({"User-Agent": USER_AGENT})
    return s


def load_config(path: Path) -> dict:
    return json.loads(path.read_text())


def discover_pdf_links(s: requests.Session, page_url: str, keywords: Iterable[str]) -> list[tuple[str, str]]:
    response = s.get(page_url, timeout=30)
    response.raise_for_status()
    soup = BeautifulSoup(response.text, "html.parser")
    keywords = [k.lower() for k in keywords]
    found: list[tuple[str, str]] = []
    for anchor in soup.find_all("a", href=True):
        href = anchor.get("href", "")
        label = " ".join(anchor.stripped_strings).strip()
        haystack = f"{label} {href}".lower()
        if ".pdf" in href.lower() and any(k in haystack for k in keywords):
            found.append((label or Path(href).name, urljoin(page_url, href)))
    return found


def extract_pdf_text(s: requests.Session, url: str) -> str:
    response = s.get(url, timeout=60)
    response.raise_for_status()
    reader = PdfReader(io.BytesIO(response.content))
    chunks: list[str] = []
    for page_number, page in enumerate(reader.pages, start=1):
        text = page.extract_text() or ""
        if text.strip():
            chunks.append(f"\n--- PAGE {page_number} ---\n{text}")
    return "\n".join(chunks)


def extract_html_text(s: requests.Session, url: str) -> str:
    response = s.get(url, timeout=30)
    response.raise_for_status()
    soup = BeautifulSoup(response.text, "html.parser")
    for tag in soup(["script", "style", "noscript"]):
        tag.decompose()
    return "\n".join(line.strip() for line in soup.stripped_strings if line.strip())


def first_float(text: str, patterns: list[str]) -> float | None:
    for pattern in patterns:
        match = re.search(pattern, text, flags=re.IGNORECASE | re.MULTILINE)
        if match:
            return float(match.group(1))
    return None


def parse_metrics(text: str) -> dict:
    values = {name: first_float(text, patterns) for name, patterns in METRIC_PATTERNS.items()}
    for name, pattern in PROGRAMME_PATTERNS.items():
        match = re.search(pattern, text, flags=re.IGNORECASE | re.MULTILINE)
        values[name] = float(match.group(1)) if match else None
    values["ratings_detected"] = sorted(set(m.group(0).upper() for m in RATING_PATTERN.finditer(text)))
    return values


def evidence_snippets(text: str, terms: Iterable[str], radius: int = 180) -> dict[str, list[str]]:
    evidence: dict[str, list[str]] = {}
    compact = re.sub(r"\s+", " ", text)
    for term in terms:
        snippets: list[str] = []
        for match in re.finditer(re.escape(term), compact, flags=re.IGNORECASE):
            start = max(0, match.start() - radius)
            end = min(len(compact), match.end() + radius)
            snippets.append(compact[start:end].strip())
            if len(snippets) >= 3:
                break
        if snippets:
            evidence[term] = snippets
    return evidence


def collect_documents(config: dict) -> list[SourceDocument]:
    s = session()
    documents: list[SourceDocument] = []
    seen: set[str] = set()

    for seed in config.get("seed_pdfs", []):
        url = seed["url"]
        if url in seen:
            continue
        documents.append(SourceDocument(seed["name"], url, seed.get("kind", "pdf"), extract_pdf_text(s, url)))
        seen.add(url)

    for page in config.get("source_pages", []):
        page_url = page["url"]
        try:
            html = extract_html_text(s, page_url)
            documents.append(SourceDocument(page["name"], page_url, "html", html))
        except Exception as exc:
            documents.append(SourceDocument(page["name"], page_url, "html_error", f"ERROR: {exc}"))

        try:
            for label, pdf_url in discover_pdf_links(s, page_url, page.get("keywords", [])):
                if pdf_url in seen:
                    continue
                try:
                    documents.append(SourceDocument(label, pdf_url, "pdf", extract_pdf_text(s, pdf_url)))
                    seen.add(pdf_url)
                except Exception as exc:
                    documents.append(SourceDocument(label, pdf_url, "pdf_error", f"ERROR: {exc}"))
        except Exception:
            pass

    return documents


def build_snapshot(config: dict, documents: list[SourceDocument]) -> dict:
    successful_text = "\n".join(d.text for d in documents if not d.kind.endswith("error"))
    metrics = parse_metrics(successful_text)
    evidence = evidence_snippets(
        successful_text,
        ["government", "funding", "CET1", "NPL", "USD", "GMTN", "USCP", "ECP", "project finance", "Southeast Asia"],
    )
    return {
        "client": config["client"],
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "metrics": metrics,
        "evidence": evidence,
        "sources": [
            {"name": d.name, "url": d.url, "kind": d.kind, "characters_extracted": len(d.text)}
            for d in documents
        ],
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Collect KDB public data and produce a structured RM snapshot.")
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()

    config = load_config(args.config)
    documents = collect_documents(config)
    snapshot = build_snapshot(config, documents)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(snapshot, indent=2, ensure_ascii=False))
    print(f"Wrote {args.output}")


if __name__ == "__main__":
    main()
