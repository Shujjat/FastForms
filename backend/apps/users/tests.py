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


class UserManagementApiTests(APITestCase):
    def setUp(self):
        self.admin = User.objects.create_user(
            username="adm",
            email="adm@example.com",
            password="Adminpass123!",
            role=User.Roles.ADMIN,
        )
        self.creator = User.objects.create_user(
            username="cr",
            email="cr@example.com",
            password="Creatorpass123!",
            role=User.Roles.CREATOR,
        )

    def _auth(self, user):
        res = self.client.post(
            "/api/auth/login",
            {"username": user.username, "password": "Adminpass123!" if user == self.admin else "Creatorpass123!"},
            format="json",
        )
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {res.data['access']}")

    def test_list_forbidden_for_non_admin(self):
        self._auth(self.creator)
        res = self.client.get("/api/users/")
        self.assertEqual(res.status_code, status.HTTP_403_FORBIDDEN)

    def test_admin_lists_users(self):
        self._auth(self.admin)
        res = self.client.get("/api/users/")
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertIn("results", res.data)
        self.assertGreaterEqual(len(res.data["results"]), 2)

    def test_admin_creates_user(self):
        self._auth(self.admin)
        res = self.client.post(
            "/api/users/",
            {
                "username": "newu",
                "email": "newu@example.com",
                "password": "Longpass123!",
                "role": "respondent",
            },
            format="json",
        )
        self.assertEqual(res.status_code, status.HTTP_201_CREATED)
        self.assertEqual(res.data["username"], "newu")
        self.assertTrue(User.objects.filter(username="newu").exists())

    def test_cannot_demote_last_admin(self):
        User.objects.exclude(pk=self.admin.pk).delete()
        self._auth(self.admin)
        res = self.client.patch(
            f"/api/users/{self.admin.pk}/",
            {"role": User.Roles.CREATOR},
            format="json",
        )
        self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("last active admin", str(res.data).lower())

    def test_soft_delete(self):
        self._auth(self.admin)
        res = self.client.delete(f"/api/users/{self.creator.pk}/")
        self.assertEqual(res.status_code, status.HTTP_204_NO_CONTENT)
        self.creator.refresh_from_db()
        self.assertFalse(self.creator.is_active)
