"""Google Sign-In: verify ID token and issue JWT (same as password login)."""

from django.conf import settings
from rest_framework import permissions, status
from rest_framework.response import Response
from rest_framework.throttling import ScopedRateThrottle
from rest_framework.views import APIView
from rest_framework_simplejwt.tokens import RefreshToken

from .models import User
from .serializers import GoogleAuthSerializer


def _tokens_for_user(user):
    refresh = RefreshToken.for_user(user)
    return {"refresh": str(refresh), "access": str(refresh.access_token)}


class GoogleAuthView(APIView):
    permission_classes = [permissions.AllowAny]
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "auth"

    def post(self, request):
        from google.auth.transport import requests as google_requests
        from google.oauth2 import id_token

        client_id = getattr(settings, "GOOGLE_OAUTH_CLIENT_ID", "") or ""
        if not client_id.strip():
            return Response(
                {"detail": "Google Sign-In is not configured (GOOGLE_OAUTH_CLIENT_ID)."},
                status=status.HTTP_503_SERVICE_UNAVAILABLE,
            )

        ser = GoogleAuthSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        credential = ser.validated_data["credential"]
        role = ser.validated_data.get("role") or User.Roles.RESPONDENT

        try:
            idinfo = id_token.verify_oauth2_token(credential, google_requests.Request(), client_id)
        except ValueError:
            return Response({"detail": "Invalid Google credential."}, status=status.HTTP_401_UNAUTHORIZED)

        if idinfo.get("iss") not in ("accounts.google.com", "https://accounts.google.com"):
            return Response({"detail": "Invalid token issuer."}, status=status.HTTP_401_UNAUTHORIZED)

        sub = idinfo.get("sub")
        email = (idinfo.get("email") or "").strip().lower()
        if not sub or not email:
            return Response({"detail": "Google token missing sub or email."}, status=status.HTTP_400_BAD_REQUEST)

        if not idinfo.get("email_verified", False):
            return Response({"detail": "Google email not verified."}, status=status.HTTP_400_BAD_REQUEST)

        user = User.objects.filter(google_sub=sub).first()
        if not user:
            user = User.objects.filter(email__iexact=email).first()
            if user:
                if not user.google_sub:
                    user.google_sub = sub
                    user.save(update_fields=["google_sub"])

        if not user:
            base_username = email.split("@")[0][:100]
            username = base_username
            n = 0
            while User.objects.filter(username=username).exists():
                n += 1
                username = f"{base_username}_{n}"[:150]

            given = (idinfo.get("given_name") or "").strip()
            family = (idinfo.get("family_name") or "").strip()
            user = User(
                username=username,
                email=email,
                google_sub=sub,
                first_name=given,
                last_name=family,
                role=role if role in dict(User.Roles.choices) else User.Roles.RESPONDENT,
            )
            user.set_unusable_password()
            user.save()

        return Response(_tokens_for_user(user))
