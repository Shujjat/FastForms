from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import override_settings
from django.contrib.auth.tokens import default_token_generator
from django.core import mail
from django.utils.encoding import force_bytes
from django.utils.http import urlsafe_base64_encode
from rest_framework import status
from rest_framework.test import APITestCase

User = get_user_model()


class PasswordResetApiTests(APITestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username="u1", email="u1@example.com", password="Oldpass123!", role="respondent"
        )

    def test_password_reset_request_sends_email_when_user_exists(self):
        res = self.client.post("/api/auth/password-reset", {"email": "u1@example.com"}, format="json")
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertEqual(len(mail.outbox), 1)

    def test_password_reset_confirm_changes_password(self):
        uid = urlsafe_base64_encode(force_bytes(self.user.pk))
        token = default_token_generator.make_token(self.user)
        res = self.client.post(
            "/api/auth/password-reset/confirm",
            {"uid": uid, "token": token, "new_password": "BrandNewPass123!"},
            format="json",
        )
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.user.refresh_from_db()
        self.assertTrue(self.user.check_password("BrandNewPass123!"))

    @override_settings(GOOGLE_OAUTH_CLIENT_ID="test-client-id.apps.googleusercontent.com")
    @patch("google.oauth2.id_token.verify_oauth2_token")
    def test_google_auth_creates_user_and_returns_tokens(self, mock_verify):
        mock_verify.return_value = {
            "iss": "https://accounts.google.com",
            "sub": "google-sub-123",
            "email": "newgoogle@example.com",
            "email_verified": True,
            "given_name": "Test",
            "family_name": "User",
        }
        res = self.client.post(
            "/api/auth/google",
            {"credential": "fake-jwt", "role": "creator"},
            format="json",
        )
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertIn("access", res.data)
        self.assertIn("refresh", res.data)
        u = User.objects.get(email="newgoogle@example.com")
        self.assertEqual(u.google_sub, "google-sub-123")
        self.assertEqual(u.role, "creator")
