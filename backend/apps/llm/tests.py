import json
from unittest.mock import patch

from django.test import override_settings
from rest_framework import status
from rest_framework.test import APITestCase

from apps.users.models import User


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

    def test_health_llm_disabled_by_default(self):
        self._login()
        res = self.client.get("/api/ai/health")
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertFalse(res.data.get("llm_enabled"))

    @override_settings(LLM_PROVIDER="ollama")
    def test_health_llm_enabled_when_configured(self):
        self._login()
        res = self.client.get("/api/ai/health")
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertTrue(res.data.get("llm_enabled"))

    @override_settings(LLM_PROVIDER="ollama")
    @patch("apps.llm.views.chat_completion")
    def test_suggest_form_returns_draft(self, mock_chat):
        mock_chat.return_value = json.dumps(
            {
                "title": "Feedback",
                "description": "Short survey",
                "questions": [
                    {
                        "text": "Name",
                        "question_type": "short_text",
                        "required": True,
                        "options": [],
                    }
                ],
            }
        )
        self._login()
        res = self.client.post("/api/ai/suggest_form", {"prompt": "Customer feedback"}, format="json")
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertEqual(res.data["title"], "Feedback")
        self.assertEqual(len(res.data["questions"]), 1)

    def test_suggest_form_503_when_not_configured(self):
        self._login()
        res = self.client.post("/api/ai/suggest_form", {"prompt": "Hello"}, format="json")
        self.assertEqual(res.status_code, status.HTTP_503_SERVICE_UNAVAILABLE)
