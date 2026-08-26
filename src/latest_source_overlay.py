from __future__ import annotations

import io
import json
import re
import time
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup
from pypdf import PdfReader
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

ROOT = Path(__file__).resolve().parents[1]
SNAPSHOT = ROOT / "data" / "kdb_public_snapshot.json"

ANNUAL_PAGE = "https://www.kdb.co.kr/BZCOWS00N00.act?_mnuId=IHIHEN0024&wcmsPath=%2Fhmp%2Fch%2Fgl%2Fir%2FCHGLIR0100.html"
FUNDING_PAGE = "https://www.kdb.co.kr/BZCOWS00N00.act?_mnuId=IHIHEN0073&wcmsPath=%2Fhmp%2Fch%2Fgl%2Fir%2FCHGLIR0700.html"
NEWSLETTER_PAGE = "https://www.kdb.co.kr/CHGLIR05N00.act?JEX_LANG=EN&_mnuId=IHIHEN0028"
RATINGS_PAGE = "https://www.kdb.co.kr/BZCOWS00N00.act?_mnuId=IHIHEN0025&wcmsPath=%2Fhmp%2Fch%2Fgl%2Fir%2FCHGLIR0200.html"
USER_AGENT = "Banking-RM/1.1 latest-source-policy"


def session() -> requests.Session:
    s = requests.Session()
    s.headers.update({"User-Agent": USER_AGENT, "Accept": "text/html,application/pdf,*/*"})
    retry = Retry(
        total=4,
        connect=4,
        read=4,
        status=4,
        backoff_factor=1.0,
        status_forcelist=(429, 500, 502, 503, 504),
        allowed_methods=frozenset(["GET", "HEAD"]),
        raise_on_status=False,
    )
    s.mount("https://", HTTPAdapter(max_retries=retry))
    s.mount("http://", HTTPAdapter(max_retries=retry))
    return s


def _get(s: requests.Session, url: str, timeout: int = 30) -> requests.Response:
    """Fetch with an application-level retry for intermittent TLS EOFs.

    KDB occasionally closes TLS connections from GitHub-hosted runners. That is
    a source-availability issue, not a data-quality failure.
    """
    last_exc = None
    for attempt in range(3):
        try:
            r = s.get(url, timeout=timeout)
            r.raise_for_status()
            return r
        except requests.RequestException as exc:
            last_exc = exc
            if attempt < 2:
                time.sleep(2 ** attempt)
    raise last_exc  # type: ignore[misc]


def page_links(s: requests.Session, url: str) -> list[dict]:
    r = _get(s, url, 30)
    soup = BeautifulSoup(r.text, "html.parser")
    out = []
    for a in soup.find_all("a", href=True):
        label = " ".join(a.stripped_strings).strip()
        href = urljoin(url, a.get("href", ""))
        out.append({"label": label, "url": href})
    return out


def best_link(links: list[dict], *terms: str) -> dict | None:
    terms = tuple(t.lower() for t in terms)
    candidates = []
    for x in links:
        hay = f"{x['label']} {x['url']}".lower()
        score = sum(1 for t in terms if t in hay)
        if score:
            candidates.append((score, len(x["label"]), x))
    if not candidates:
        return None
    return sorted(candidates, key=lambda z: (z[0], z[1]), reverse=True)[0][2]


def pdf_text(s: requests.Session, url: str) -> str:
    r = _get(s, url, 60)
    reader = PdfReader(io.BytesIO(r.content))
    chunks = []
    for i, p in enumerate(reader.pages, 1):
        txt = p.extract_text() or ""
        if txt.strip():
            chunks.append(f"\n--- PAGE {i} ---\n{txt}")
    return "\n".join(chunks)


def compact(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


def extract_newsletter_signals(text: str) -> list[dict]:
    c = compact(text)
    topics = [
        ("funding", ["funding", "bond", "issuance"]),
        ("strategic finance", ["semiconductor", "battery", "shipbuilding", "AI"]),
        ("overseas", ["overseas", "global", "southeast asia", "ASEAN"]),
        ("sustainable finance", ["green", "social", "sustainable"]),
    ]
    found, used = [], set()
    for topic, terms in topics:
        for term in terms:
            m = re.search(re.escape(term), c, re.I)
            if not m:
                continue
            snippet = c[max(0, m.start() - 150): min(len(c), m.end() + 220)].strip()
            key = snippet[:120]
            if key in used:
                continue
            used.add(key)
            found.append({"topic": topic, "evidence_snippet": snippet})
            break
    return found[:6]


def _metric_periods(snapshot: dict) -> dict:
    return {key: (ev.get("reporting_period") or "unknown") for key, ev in snapshot.get("metric_evidence", {}).items()}


def _fallback_status(previous: dict | None, checked_at: str, warning: str) -> dict:
    prior = (previous or {}).get("source_status") or {}
    status = prior.copy() if prior else {
        "latest_annual_report": {"period": "FY2025", "url": ANNUAL_PAGE, "verified_on_official_page": False},
        "latest_ir_presentation": {"period": "Dec 2025", "url": FUNDING_PAGE, "verified_on_official_page": False},
        "latest_investor_update": {"period": "2026", "url": NEWSLETTER_PAGE, "verified_on_official_page": False},
        "current_ratings": {"period": "current", "url": RATINGS_PAGE},
        "current_funding_programmes": {"period": "current", "url": FUNDING_PAGE},
    }
    status["checked_at"] = checked_at
    status["source_check_status"] = "temporarily_unavailable"
    status["source_check_warning"] = warning[:500]
    return status


def discover_latest(previous: dict | None = None) -> dict:
    s = session()
    checked_at = datetime.now(timezone.utc).isoformat()
    try:
        annual_links = page_links(s, ANNUAL_PAGE)
        funding_links = page_links(s, FUNDING_PAGE)
        newsletter_links = page_links(s, NEWSLETTER_PAGE)
    except requests.RequestException as exc:
        # Network/TLS failure must not destroy a previously verified snapshot.
        return {"source_status": _fallback_status(previous, checked_at, str(exc)), "current_developments": (previous or {}).get("current_developments", [])}

    annual_2025 = best_link(annual_links, "2025", "annual")
    ir_latest = best_link(funding_links, "investor", "presentation")
    newsletter_2026 = best_link(newsletter_links, "2026", "newsletter")

    status = {
        "checked_at": checked_at,
        "source_check_status": "ok",
        "latest_annual_report": {
            "period": "FY2025" if annual_2025 else "unknown",
            "url": annual_2025["url"] if annual_2025 else ANNUAL_PAGE,
            "label": annual_2025["label"] if annual_2025 else "2025 Annual Report listing",
            "verified_on_official_page": bool(annual_2025),
        },
        "latest_ir_presentation": {
            "period": "Dec 2025",
            "data_as_of": "1H25 for core financial metrics",
            "url": ir_latest["url"] if ir_latest else FUNDING_PAGE,
            "label": ir_latest["label"] if ir_latest else "IR Presentation listing",
            "verified_on_official_page": bool(ir_latest),
        },
        "latest_investor_update": {
            "period": "2026",
            "url": newsletter_2026["url"] if newsletter_2026 else NEWSLETTER_PAGE,
            "label": newsletter_2026["label"] if newsletter_2026 else "2026 KDB Investor Newsletter listing",
            "verified_on_official_page": bool(newsletter_2026),
        },
        "current_ratings": {"period": "current", "url": RATINGS_PAGE},
        "current_funding_programmes": {"period": "current", "url": FUNDING_PAGE},
    }

    developments = []
    if newsletter_2026 and newsletter_2026["url"].lower().endswith(".pdf"):
        try:
            developments = extract_newsletter_signals(pdf_text(s, newsletter_2026["url"]))
        except requests.RequestException as exc:
            status["latest_investor_update"]["parse_warning"] = f"Temporary source access failure: {exc}"
        except Exception as exc:
            status["latest_investor_update"]["parse_warning"] = f"Parse warning: {exc}"
    return {"source_status": status, "current_developments": developments}


def apply_overlay(snapshot: dict, discovered: dict) -> dict:
    snapshot["source_status"] = discovered["source_status"]
    snapshot["current_developments"] = discovered.get("current_developments", [])
    snapshot["latest_verified_metric_periods"] = _metric_periods(snapshot)
    snapshot["freshness"] = {
        "status": "current-source-check" if discovered["source_status"].get("source_check_status") == "ok" else "source-check-degraded",
        "checked_at": discovered["source_status"]["checked_at"],
        "latest_public_source_period": "2026",
        "note": "Source freshness and metric freshness are separate. A 2026 investor update does not automatically make an older-period financial metric current.",
    }
    return snapshot


def main() -> None:
    snapshot = json.loads(SNAPSHOT.read_text())
    snapshot = apply_overlay(snapshot, discover_latest(snapshot))
    SNAPSHOT.write_text(json.dumps(snapshot, indent=2, ensure_ascii=False))
    status = snapshot["source_status"].get("source_check_status")
    print(f"Added latest KDB source discovery and per-metric periods; source_check={status}")


if __name__ == "__main__":
    main()
