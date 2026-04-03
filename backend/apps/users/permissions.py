from rest_framework.permissions import BasePermission


class IsDjangoSuperuser(BasePermission):
    """Django superuser only (platform-level settings, billing package CRUD)."""

    def has_permission(self, request, view):
        user = request.user
        return bool(user and user.is_authenticated and getattr(user, "is_superuser", False))


class IsAdminUser(BasePermission):
    """
    Application admins (role=admin) or Django superusers.
    Superusers can manage staff flags; role=admin covers day-to-day user control.
    """

    def has_permission(self, request, view):
        user = request.user
        if not user or not user.is_authenticated:
            return False
        if getattr(user, "is_superuser", False):
            return True
        return getattr(user, "role", None) == "admin"
