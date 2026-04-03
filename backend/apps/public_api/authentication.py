import hashlib
import logging

from django.utils import timezone
from rest_framework.authentication import BaseAuthentication
from rest_framework.exceptions import AuthenticationFailed

from apps.users.models import UserApiKey

logger = logging.getLogger(__name__)


class ApiKeyAuthentication(BaseAuthentication):
    """
    Expects either:
    - Header ``X-Api-Key: <secret>``
    - Header ``Authorization: Api-Key <secret>``
    """

    def authenticate(self, request):
        key = (request.headers.get("X-Api-Key") or "").strip()
        if not key:
            auth = request.headers.get("Authorization") or ""
            if len(auth) > 9 and auth[:8].lower() == "api-key ":
                key = auth[8:].strip()
        if not key:
            return None

        digest = hashlib.sha256(key.encode("utf-8")).hexdigest()
        try:
            api_key = UserApiKey.objects.select_related("user").get(key_hash=digest, is_active=True)
        except UserApiKey.DoesNotExist:
            logger.warning("api_key auth failed: unknown or inactive key digest prefix=%s", digest[:8])
            raise AuthenticationFailed("Invalid or revoked API key.")

        UserApiKey.objects.filter(pk=api_key.pk).update(last_used_at=timezone.now())
        return (api_key.user, api_key)
