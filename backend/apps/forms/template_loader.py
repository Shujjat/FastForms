"""Load built-in form templates from JSON files in form_template_catalog/."""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path

_CATALOG_DIR = Path(__file__).resolve().parent / "form_template_catalog"


@lru_cache(maxsize=1)
def _all_template_payloads() -> dict[str, dict]:
    out: dict[str, dict] = {}
    if not _CATALOG_DIR.is_dir():
        return out
    for path in sorted(_CATALOG_DIR.glob("*.json")):
        if path.name.startswith("schema.") or path.name.startswith("_"):
            continue
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            continue
        tid = data.get("id")
        if not tid or not isinstance(tid, str):
            continue
        out[tid] = data
    return out


def list_template_summaries() -> list[dict]:
    """Metadata for gallery (no full question list needed for list UI)."""
    rows = []
    for tid, data in sorted(_all_template_payloads().items(), key=lambda x: x[0]):
        rows.append(
            {
                "id": tid,
                "title": data.get("title") or tid,
                "description": (data.get("description") or "")[:500],
                "category": data.get("category") or "General",
                "tags": data.get("tags") if isinstance(data.get("tags"), list) else [],
                "question_count": len(data.get("questions") or []),
            }
        )
    return rows


def get_template(template_id: str) -> dict | None:
    return _all_template_payloads().get(template_id)
