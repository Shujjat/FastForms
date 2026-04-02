import json
import logging
import time

import requests
from django.conf import settings as django_settings
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.throttling import UserRateThrottle
from rest_framework.views import APIView

from apps.forms.permissions import IsCreatorOrAdmin

from .client import chat_completion, is_llm_configured, ollama_health_model_display
from .suggest import build_suggest_form_messages, parse_suggest_form_json

logger = logging.getLogger(__name__)


class AiHealthView(APIView):
    """Return whether server-side LLM (Ollama) is enabled via configuration."""

    permission_classes = [IsAuthenticated]

    def get(self, request):
        enabled = is_llm_configured()
        payload: dict = {"llm_enabled": enabled}
        if enabled:
            payload["ollama_model"] = ollama_health_model_display()
            payload["ollama_timeout_sec"] = int(getattr(django_settings, "OLLAMA_TIMEOUT", 300))
        return Response(payload)


class AiUserThrottle(UserRateThrottle):
    scope = "ai"


class SuggestFormView(APIView):
    """
    POST { "prompt": "..." } -> { title, description, questions: [...] }
    Requires LLM_PROVIDER=ollama and a running Ollama instance.
    """

    permission_classes = [IsAuthenticated, IsCreatorOrAdmin]
    throttle_classes = [AiUserThrottle]

    def post(self, request):
        prompt = (request.data or {}).get("prompt") or ""
        user = request.user
        uname = getattr(user, "username", "?")
        uid = getattr(user, "pk", None)
        p = str(prompt).strip()
        if not p:
            logger.info("AI POST /api/ai/suggest_form rejected: empty prompt user=%s pk=%s", uname, uid)
            return Response({"detail": "prompt is required."}, status=400)
        if not is_llm_configured():
            logger.warning("AI suggest_form rejected: LLM not configured user=%s pk=%s", uname, uid)
            return Response(
                {
                    "detail": "AI is not configured. Set LLM_PROVIDER=ollama and OLLAMA_BASE_URL (optional). Use OLLAMA_MODEL=auto to pick an installed chat model, or set a tag from `ollama list`."
                },
                status=503,
            )
        logger.info(
            "AI suggest_form START user=%s pk=%s prompt_chars=%d configured_model=%r",
            uname,
            uid,
            len(p),
            ollama_health_model_display(),
        )
        if getattr(django_settings, "AI_LOG_VERBOSE", False):
            preview = p[:160] + ("…" if len(p) > 160 else "")
            logger.info("AI suggest_form prompt preview (AI_LOG_VERBOSE): %r", preview)
        t0 = time.monotonic()
        raw = ""
        try:
            messages = build_suggest_form_messages(p)
            raw = chat_completion(messages)
            draft = parse_suggest_form_json(raw)
        except RuntimeError as e:
            elapsed = time.monotonic() - t0
            logger.warning(
                "AI suggest_form FAILED user=%s pk=%s duration_s=%.2f error=%s",
                uname,
                uid,
                elapsed,
                str(e)[:500],
            )
            return Response({"detail": str(e)}, status=503)
        except json.JSONDecodeError as e:
            elapsed = time.monotonic() - t0
            logger.warning(
                "AI suggest_form JSON_PARSE_ERROR user=%s pk=%s duration_s=%.2f raw_chars=%d err=%s",
                uname,
                uid,
                elapsed,
                len(raw),
                e,
            )
            return Response({"detail": f"Model did not return valid JSON: {e}"}, status=502)
        except ValueError as e:
            elapsed = time.monotonic() - t0
            logger.warning(
                "AI suggest_form VALIDATION_ERROR user=%s pk=%s duration_s=%.2f err=%s",
                uname,
                uid,
                elapsed,
                e,
            )
            return Response({"detail": str(e)}, status=502)
        except requests.RequestException as e:
            elapsed = time.monotonic() - t0
            logger.warning(
                "AI suggest_form UPSTREAM_ERROR user=%s pk=%s duration_s=%.2f err=%s",
                uname,
                uid,
                elapsed,
                e,
            )
            return Response({"detail": f"Could not reach LLM: {e}"}, status=502)
        elapsed = time.monotonic() - t0
        nq = len(draft.get("questions") or [])
        title = draft.get("title") or ""
        if getattr(django_settings, "AI_LOG_VERBOSE", False):
            logger.info(
                "AI suggest_form OK user=%s pk=%s duration_s=%.2f title=%r question_count=%d",
                uname,
                uid,
                elapsed,
                (title[:100] + "…") if len(title) > 100 else title,
                nq,
            )
        else:
            logger.info(
                "AI suggest_form OK user=%s pk=%s duration_s=%.2f title_len=%d question_count=%d",
                uname,
                uid,
                elapsed,
                len(title),
                nq,
            )
        return Response(draft)
