"""Parse model output into a form draft (title, description, questions)."""

from __future__ import annotations

import json
import re
from typing import Any

from apps.forms.models import Question

_VALID_TYPES = {c.value for c in Question.Types}


def build_suggest_form_messages(user_prompt: str) -> list[dict[str, str]]:
    system = (
        "You are a form designer. Given a short description, output ONLY valid JSON, no markdown fences, no commentary. "
        "Schema: "
        '{"title": string, "description": string, '
        '"questions": ['
        '{"text": string, "question_type": one of short_text, paragraph, single_choice, multi_choice, dropdown, date, rating, file_upload, '
        '"required": boolean, "options": string[]}'
        "]}. "
        "Use empty options [] for non-choice types. Use at most 12 questions. Keep text concise."
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
    for item in raw_qs[:12]:
        if not isinstance(item, dict):
            continue
        qt = item.get("question_type") or "short_text"
        if qt not in _VALID_TYPES:
            qt = "short_text"
        opts = item.get("options") or []
        if not isinstance(opts, list):
            opts = []
        opts = [str(o)[:500] for o in opts[:50]]
        questions.append(
            {
                "text": str(item.get("text") or "Question")[:500],
                "question_type": qt,
                "required": bool(item.get("required", False)),
                "options": opts if qt in ("single_choice", "multi_choice", "dropdown") else [],
            }
        )

    if not questions:
        raise ValueError("Model returned no usable questions.")

    return {"title": title, "description": description, "questions": questions}
