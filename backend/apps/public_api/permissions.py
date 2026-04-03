from rest_framework.permissions import BasePermission

from apps.users.models import UserApiKey


class HasApiKeyScope(BasePermission):
    """
    Requires request.auth to be a UserApiKey with all scopes returned by
    ``view.get_required_scopes(request)`` or ``view.required_scopes``.
    """

    message = "API key is missing a required scope."

    def has_permission(self, request, view):
        auth = getattr(request, "auth", None)
        if not isinstance(auth, UserApiKey):
            return False
        if getattr(view, "get_required_scopes", None):
            required = view.get_required_scopes(request)
        else:
            required = getattr(view, "required_scopes", ())
        for scope in required:
            if not auth.has_scope(scope):
                return False
        return True
