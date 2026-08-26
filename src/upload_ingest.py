from __future__ import annotations

import io
import json
from datetime import datetime, timezone
from pathlib import Path

from pypdf import PdfReader


def _read_pdf(data: bytes) -> str:
    reader = PdfReader(io.BytesIO(data))
    pages = []
    for i, page in enumerate(reader.pages, start=1):
        text = page.extract_text() or ""
        pages.append(f"\n--- PAGE {i} ---\n{text}")
    return "\n".join(pages)


def extract_uploaded_file(uploaded) -> dict:
    name = uploaded.name
    suffix = Path(name).suffix.lower()
    data = uploaded.getvalue()
    if suffix == ".pdf":
        text = _read_pdf(data)
        kind = "pdf"
    elif suffix in {".txt", ".md"}:
        text = data.decode("utf-8", errors="replace")
        kind = suffix.lstrip(".")
    elif suffix == ".json":
        obj = json.loads(data.decode("utf-8", errors="replace"))
        text = json.dumps(obj, indent=2, ensure_ascii=False)
        kind = "json"
    else:
        raise ValueError(f"Unsupported file type: {suffix}")
    return {"name": name, "type": kind, "text": text}


def build_source_pack(institution: str, docs: list[dict]) -> dict:
    return {
        "institution": institution,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "documents": [
            {
                "name": d["name"],
                "type": d["type"],
                "text": d["text"],
            }
            for d in docs
        ],
        "status": "unverified_source_pack",
        "note": "Source pack only. Do not treat extracted facts as credit-grade until institution/source-specific validation rules are configured.",
    }
