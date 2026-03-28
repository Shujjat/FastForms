import json
import logging

import requests
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.throttling import UserRateThrottle
from rest_framework.views import APIView

from apps.forms.permissions import IsCreatorOrAdmin

from .client import chat_completion, is_llm_configured
from .suggest import build_suggest_form_messages, parse_suggest_form_json

logger = logging.getLogger(__name__)


class AiHealthView(APIView):
    """Return whether server-side LLM (Ollama) is enabled via configuration."""

    permission_classes = [IsAuthenticated]

    def get(self, request):
        return Response({"llm_enabled": is_llm_configured()})


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
        if not str(prompt).strip():
            return Response({"detail": "prompt is required."}, status=400)
        if not is_llm_configured():
            return Response(
                {
                    "detail": "AI is not configured. Set LLM_PROVIDER=ollama, OLLAMA_BASE_URL, and OLLAMA_MODEL in the environment."
                },
                status=503,
            )
        try:
            messages = build_suggest_form_messages(str(prompt))
            raw = chat_completion(messages)
            draft = parse_suggest_form_json(raw)
        except RuntimeError as e:
            return Response({"detail": str(e)}, status=503)
        except json.JSONDecodeError as e:
            logger.warning("AI suggest_form JSON parse failed: %s", e)
            return Response({"detail": f"Model did not return valid JSON: {e}"}, status=502)
        except ValueError as e:
            return Response({"detail": str(e)}, status=502)
        except requests.RequestException as e:
            logger.warning("AI suggest_form upstream error: %s", e)
            return Response({"detail": f"Could not reach LLM: {e}"}, status=502)
        return Response(draft)
