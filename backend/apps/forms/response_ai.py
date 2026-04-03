"""LLM-backed summaries for individual responses and for all responses on a form."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from django.conf import settings
from django.utils import timezone

from apps.llm.client import chat_completion

if TYPE_CHECKING:
    from .models import Form, Response as FormResponse

logger = logging.getLogger(__name__)

MAX_ANSWER_CHARS = 900
MAX_STORED_NARRATION_CHARS = 12_000
MAX_AGGREGATE_PROMPT_CHARS = 28_000


def _format_answer_value(value) -> str:
    if value is None:
        return ""
    if isinstance(value, list):
        return ", ".join(str(x) for x in value)
    if isinstance(value, dict):
        return str(value)
    return str(value)


def response_qa_block(form: Form, response: FormResponse) -> str:
    answers = list(
        response.answers.select_related("question").order_by("question__order_index", "question_id")
    )
    lines = []
    for a in answers:
        q = a.question
        raw = _format_answer_value(a.value)
        if len(raw) > MAX_ANSWER_CHARS:
            raw = raw[: MAX_ANSWER_CHARS - 3] + "..."
        lines.append(f"Q: {q.text.strip()}\nA: {raw}")
    return "\n\n".join(lines)


def build_single_narration_messages(form: Form, response: FormResponse) -> list[dict[str, str]]:
    block = response_qa_block(form, response)
    title = (form.title or "").strip() or "Untitled form"
    desc = (form.description or "").strip()[:800]
    user_msg = (
        f"Form title: {title}\n"
        f"Form description: {desc or '(none)'}\n\n"
        f"Submission (question and answer pairs):\n{block or '(no answers)'}\n\n"
        "Write a short neutral summary (2–5 sentences) of this one submission in third person. "
        "Only use information from the answers above; do not invent details."
    )
    return [
        {"role": "system", "content": "You help form owners understand submissions. Be concise and factual."},
        {"role": "user", "content": user_msg},
    ]


def build_aggregate_summary_messages(form: Form, responses: list) -> list[dict[str, str]]:
    title = (form.title or "").strip() or "Untitled form"
    desc = (form.description or "").strip()[:600]
    n = len(responses)
    parts = [f"Form title: {title}\nForm description: {desc or '(none)'}\n\nSubmissions ({n} total):\n"]
    total_chars = len(parts[0])
    max_per = max(400, min(2500, 14_000 // max(n, 1)))
    omitted = 0
    for i, r in enumerate(responses, 1):
        block = response_qa_block(form, r)
        if len(block) > max_per:
            block = block[: max_per - 20] + "\n…(truncated)"
        piece = f"--- Response #{i} (id {r.id}, submitted {r.submitted_at.isoformat()}) ---\n{block}\n\n"
        if total_chars + len(piece) > MAX_AGGREGATE_PROMPT_CHARS:
            omitted = n - i + 1
            break
        parts.append(piece)
        total_chars += len(piece)
    if omitted:
        parts.append(f"\n({omitted} more response(s) omitted because the prompt length limit was reached.)\n")
    user_msg = "".join(parts) + (
        "Summarize all submissions for the form owner: overall themes, patterns, and notable "
        "highlights or outliers. Use a short opening paragraph and bullet points where helpful. "
        "Do not invent data beyond the text above."
    )
    return [
        {"role": "system", "content": "You summarize survey/form data for the form owner. Be accurate and concise."},
        {"role": "user", "content": user_msg},
    ]


def generate_and_save_response_narration(form: Form, response: FormResponse) -> str:
    messages = build_single_narration_messages(form, response)
    if getattr(settings, "AI_LOG_VERBOSE", False):
        logger.info(
            "response_ai single narration form_id=%s response_id=%s prompt_chars=%d",
            form.id,
            response.id,
            sum(len(m.get("content") or "") for m in messages),
        )
    text = chat_completion(messages, temperature=0.25).strip()
    text = text[:MAX_STORED_NARRATION_CHARS]
    response.ai_narration = text
    response.ai_narration_generated_at = timezone.now()
    response.save(update_fields=["ai_narration", "ai_narration_generated_at"])
    return text


def generate_and_save_form_responses_summary(form: Form, responses: list) -> str:
    messages = build_aggregate_summary_messages(form, responses)
    if getattr(settings, "AI_LOG_VERBOSE", False):
        logger.info(
            "response_ai aggregate form_id=%s response_count=%s prompt_chars=%d",
            form.id,
            len(responses),
            sum(len(m.get("content") or "") for m in messages),
        )
    text = chat_completion(messages, temperature=0.25).strip()
    text = text[:MAX_STORED_NARRATION_CHARS]
    form.responses_ai_summary = text
    form.responses_ai_summary_generated_at = timezone.now()
    form.save(update_fields=["responses_ai_summary", "responses_ai_summary_generated_at"])
    return text
