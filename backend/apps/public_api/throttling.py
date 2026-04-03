from rest_framework.throttling import SimpleRateThrottle

from apps.users.models import UserApiKey


class ApiKeyRateThrottle(SimpleRateThrottle):
    scope = "api_key"

    def get_cache_key(self, request, view):
        auth = getattr(request, "auth", None)
        if isinstance(auth, UserApiKey):
            return self.cache_format % {"scope": self.scope, "ident": f"k{auth.pk}"}
        return None
