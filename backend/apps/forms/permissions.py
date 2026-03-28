from rest_framework.permissions import BasePermission, SAFE_METHODS

from .models import FormCollaborator


class IsOwnerOrReadOnly(BasePermission):
    def has_object_permission(self, request, view, obj):
        if request.method in SAFE_METHODS:
            return True
        return getattr(obj, "owner_id", None) == getattr(request.user, "id", None)


class IsCreatorOrAdmin(BasePermission):
    def has_permission(self, request, view):
        user = request.user
        if not user or not user.is_authenticated:
            return False
        return user.role in {"creator", "admin"}


class CanEditForm(BasePermission):
    def has_object_permission(self, request, view, obj):
        if not request.user or not request.user.is_authenticated:
            return False
        if request.user.role not in {"creator", "admin"}:
            return False
        if obj.owner_id == request.user.id:
            return True
        return FormCollaborator.objects.filter(
            form=obj, user=request.user, role=FormCollaborator.Roles.EDITOR
        ).exists()
