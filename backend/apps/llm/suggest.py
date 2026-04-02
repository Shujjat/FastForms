"""Parse model output into a form draft (title, description, questions)."""

from __future__ import annotations

import json
import re
from typing import Any

from rest_framework import serializers as drf_serializers

from apps.forms.models import Question
from apps.forms.serializers import QuestionSerializer, _ALLOWED_FORMATS

_VALID_TYPES = {c.value for c in Question.Types}

# Which validation keys apply per question_type (matches submit-time rules in forms.serializers).
_VALIDATION_BY_TYPE: dict[str, frozenset[str]] = {
    "short_text": frozenset({"min_length", "max_length", "format", "pattern"}),
    "paragraph": frozenset({"min_length", "max_length", "format", "pattern"}),
    "date": frozenset({"min_date", "max_date"}),
    "rating": frozenset({"min", "max"}),
}


def build_suggest_form_messages(user_prompt: str) -> list[dict[str, str]]:
    fmt_list = "|".join(sorted(_ALLOWED_FORMATS))
    system = (
        "You are a form designer. Given a short description, output ONLY compact valid JSON, no markdown fences, no commentary. "
        "Schema: "
        '{"title": string, "description": string, '
        '"questions": ['
        '{"text": string, "question_type": one of short_text, paragraph, single_choice, multi_choice, dropdown, date, rating, file_upload, '
        '"required": boolean, "options": string[], '
        '"validation": object}'
        "]}. "
        "Use empty options [] for non-choice types. validation is optional; use {} when none. "
        "Per-type validation (omit keys you do not need): "
        f"short_text/paragraph: min_length, max_length, format ({fmt_list}), pattern (regex string). "
        "date: min_date, max_date as YYYY-MM-DD. "
        "rating: min, max as integers (e.g. 1 and 5 or 1 and 10). "
        "For email/phone/URL fields use short_text with the matching format preset. "
        "At most 8 questions; keep text short."
    )
    return [
        {"role": "system", "content": system},
        {"role": "user", "content": user_prompt.strip()[:4000]},
    ]


def _strip_code_fence(text: str) -> str:
    t = text.strip()
    if t.startswith("```"):
        lines = t.split("\n")
        if lines and lines[0].startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]
        t = "\n".join(lines).strip()
    return t


def _sanitize_validation(item: dict[str, Any], question_type: str) -> dict[str, Any]:
    """Build a Question.validation dict safe for QuestionSerializer and storage."""
    allowed_qt = _VALIDATION_BY_TYPE.get(question_type)
    if not allowed_qt:
        return {}

    raw = item.get("validation")
    if not isinstance(raw, dict):
        return {}

    d: dict[str, Any] = {}
    for k, v in raw.items():
        if k not in allowed_qt:
            continue
        if k in ("min_length", "max_length"):
            try:
                n = int(v)
                if n >= 0:
                    d[k] = n
            except (TypeError, ValueError):
                pass
        elif k in ("min", "max"):
            try:
                if isinstance(v, bool):
                    continue
                if isinstance(v, int):
                    d[k] = v
                elif isinstance(v, float):
                    d[k] = int(v) if v.is_integer() else v
                else:
                    s = str(v).strip()
                    d[k] = int(s) if s.lstrip("-").isdigit() else float(s)
            except (TypeError, ValueError):
                pass
        elif k == "pattern" and isinstance(v, str) and v.strip():
            d[k] = v.strip()[:500]
        elif k in ("min_date", "max_date") and isinstance(v, str) and v.strip():
            d[k] = v.strip()[:32]
        elif k == "format":
            s = str(v).strip().lower() if v is not None else ""
            if s in _ALLOWED_FORMATS:
                d[k] = s

    if not d:
        return {}
    try:
        return QuestionSerializer().validate_validation(d)
    except drf_serializers.ValidationError:
        return {}


def parse_suggest_form_json(raw: str) -> dict[str, Any]:
    """Parse assistant output into a validated draft dict."""
    t = _strip_code_fence(raw)
    # Some models wrap JSON in extra text — try to find outermost { ... }
    if not t.startswith("{"):
        m = re.search(r"\{[\s\S]*\}\s*$", t)
        if m:
            t = m.group(0)
    data = json.loads(t)
    if not isinstance(data, dict):
        raise ValueError("Root must be a JSON object.")

    title = (data.get("title") or "Untitled form")[:255]
    description = str(data.get("description") or "")[:2000]
    raw_qs = data.get("questions") or []
    if not isinstance(raw_qs, list):
        raise ValueError("questions must be an array.")

    questions: list[dict[str, Any]] = []
    for item in raw_qs[:8]:
        if not isinstance(item, dict):
            continue
        qt = item.get("question_type") or "short_text"
        if qt not in _VALID_TYPES:
            qt = "short_text"
        opts = item.get("options") or []
        if not isinstance(opts, list):
            opts = []
        opts = [str(o)[:500] for o in opts[:50]]
        validation = _sanitize_validation(item, qt)
        questions.append(
            {
                "text": str(item.get("text") or "Question")[:500],
                "question_type": qt,
                "required": bool(item.get("required", False)),
                "options": opts if qt in ("single_choice", "multi_choice", "dropdown") else [],
                "validation": validation,
            }
        )

    if not questions:
        raise ValueError("Model returned no usable questions.")

    return {"title": title, "description": description, "questions": questions}
