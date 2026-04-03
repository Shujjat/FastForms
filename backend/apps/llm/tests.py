import json
from unittest.mock import MagicMock, patch

import requests
from django.test import override_settings
from rest_framework import status
from rest_framework.test import APITestCase

from apps.llm import client as llm_client
from apps.llm.suggest import parse_suggest_form_json
from apps.users.models import BillingPackage, User


class LlmApiTests(APITestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username="creator_ai",
            email="creator_ai@example.com",
            password="Password123!",
            role="creator",
        )

    def _login(self):
        res = self.client.post(
            "/api/auth/login", {"username": "creator_ai", "password": "Password123!"}, format="json"
        )
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {res.data['access']}")

    @override_settings(LLM_PROVIDER="")
    def test_health_llm_disabled_by_default(self):
        """Explicitly unset provider; local .env may set LLM_PROVIDER=ollama."""
        self._login()
        res = self.client.get("/api/ai/health")
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertFalse(res.data.get("llm_enabled"))
        self.assertNotIn("ollama_model", res.data)
        self.assertNotIn("ollama_timeout_sec", res.data)

    @override_settings(LLM_PROVIDER="ollama", OLLAMA_MODEL="phi3:latest", OLLAMA_TIMEOUT=240)
    def test_health_llm_enabled_when_configured(self):
        self._login()
        res = self.client.get("/api/ai/health")
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertTrue(res.data.get("llm_enabled"))
        self.assertEqual(res.data.get("ollama_model"), "phi3:latest")
        self.assertEqual(res.data.get("ollama_timeout_sec"), 240)

    @override_settings(LLM_PROVIDER="ollama")
    @patch("apps.llm.views.chat_completion")
    def test_suggest_form_returns_draft(self, mock_chat):
        mock_chat.return_value = json.dumps(
            {
                "title": "Feedback",
                "description": "Short survey",
                "questions": [
                    {
                        "text": "Your email",
                        "question_type": "short_text",
                        "required": True,
                        "options": [],
                        "validation": {"format": "email", "max_length": 254},
                    }
                ],
            }
        )
        self._login()
        res = self.client.post("/api/ai/suggest_form", {"prompt": "Customer feedback"}, format="json")
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertEqual(res.data["title"], "Feedback")
        self.assertEqual(len(res.data["questions"]), 1)
        self.assertEqual(res.data["questions"][0].get("validation"), {"format": "email", "max_length": 254})

    @override_settings(LLM_PROVIDER="")
    def test_suggest_form_503_when_not_configured(self):
        self._login()
        res = self.client.post("/api/ai/suggest_form", {"prompt": "Hello"}, format="json")
        self.assertEqual(res.status_code, status.HTTP_503_SERVICE_UNAVAILABLE)

    @override_settings(LLM_PROVIDER="ollama")
    @patch("apps.llm.views.chat_completion")
    def test_suggest_form_400_when_ai_credits_exhausted(self, mock_chat):
        mock_chat.return_value = json.dumps({"title": "T", "description": "", "questions": []})
        pkg = BillingPackage.objects.create(
            slug="ai_tiny_test",
            name="AI Tiny Test",
            sort_order=200,
            is_active=True,
            is_free_tier=False,
            max_owned_forms=None,
            ai_credits_per_period=1,
            ai_usage_period_days=30,
        )
        self.user.billing_package = pkg
        self.user.save(update_fields=["billing_package"])
        self.user.ai_credits_used = 1
        self.user.save(update_fields=["ai_credits_used"])
        self._login()
        res = self.client.post("/api/ai/suggest_form", {"prompt": "Hello"}, format="json")
        self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("detail", res.data)

    @override_settings(LLM_PROVIDER="ollama", OLLAMA_MODEL="missing-model:tag")
    @patch("apps.llm.client.requests.post")
    def test_suggest_form_clear_detail_when_ollama_model_missing(self, mock_post):
        mock_resp = MagicMock()
        mock_resp.status_code = 404
        mock_resp.json.return_value = {"error": {"message": "model 'missing-model:tag' not found"}}
        mock_post.return_value = mock_resp
        self._login()
        res = self.client.post("/api/ai/suggest_form", {"prompt": "Hello"}, format="json")
        self.assertEqual(res.status_code, status.HTTP_503_SERVICE_UNAVAILABLE)
        self.assertIn("Ollama does not have model", res.data["detail"])
        self.assertIn("ollama list", res.data["detail"])

    @override_settings(LLM_PROVIDER="ollama", OLLAMA_MODEL="auto")
    @patch("apps.llm.client.requests.post")
    @patch("apps.llm.client.requests.get")
    def test_auto_model_prefers_general_over_code_models(self, mock_get, mock_post):
        llm_client._auto_model_cache.clear()
        tags_resp = MagicMock()
        tags_resp.raise_for_status = MagicMock()
        tags_resp.json.return_value = {
            "models": [
                {"name": "deepseek-coder:6.7b"},
                {"name": "codellama:13b"},
                {"name": "qwen3:latest"},
            ]
        }
        mock_get.return_value = tags_resp
        chat_resp = MagicMock()
        chat_resp.status_code = 200
        chat_resp.json.return_value = {"choices": [{"message": {"content": "ok"}}]}
        mock_post.return_value = chat_resp

        out = llm_client.chat_completion([{"role": "user", "content": "hi"}])
        self.assertEqual(out, "ok")
        body = mock_post.call_args[1]["json"]
        self.assertEqual(body["model"], "qwen3:latest")

    @override_settings(LLM_PROVIDER="ollama", OLLAMA_MODEL="test:tag")
    @patch("apps.llm.client.requests.post")
    def test_suggest_form_friendly_detail_on_read_timeout(self, mock_post):
        mock_post.side_effect = requests.exceptions.ReadTimeout()
        self._login()
        res = self.client.post("/api/ai/suggest_form", {"prompt": "Hello"}, format="json")
        self.assertEqual(res.status_code, status.HTTP_503_SERVICE_UNAVAILABLE)
        self.assertIn("did not respond in time", res.data["detail"])
        self.assertIn("OLLAMA_TIMEOUT", res.data["detail"])

    def test_parse_suggest_drops_invalid_format_preset(self):
        raw = json.dumps(
            {
                "title": "T",
                "description": "",
                "questions": [
                    {
                        "text": "x",
                        "question_type": "short_text",
                        "required": False,
                        "options": [],
                        "validation": {"format": "not_a_real_preset"},
                    }
                ],
            }
        )
        d = parse_suggest_form_json(raw)
        self.assertEqual(d["questions"][0]["validation"], {})

    def test_parse_suggest_rating_validation_min_max(self):
        raw = json.dumps(
            {
                "title": "T",
                "description": "",
                "questions": [
                    {
                        "text": "Score",
                        "question_type": "rating",
                        "required": True,
                        "options": [],
                        "validation": {"min": 1, "max": 10},
                    }
                ],
            }
        )
        d = parse_suggest_form_json(raw)
        self.assertEqual(d["questions"][0]["validation"], {"min": 1, "max": 10})
