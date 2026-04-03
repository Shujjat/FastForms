from django.db.models import Q
from rest_framework import generics, status
from rest_framework.exceptions import PermissionDenied
from rest_framework.pagination import PageNumberPagination
from rest_framework.response import Response

from django.contrib.auth import get_user_model

from .permissions import IsAdminUser
from .serializers import (
    AdminUserCreateSerializer,
    AdminUserReadSerializer,
    AdminUserUpdateSerializer,
)

User = get_user_model()


class UserManagementPagination(PageNumberPagination):
    page_size = 20
    page_size_query_param = "page_size"
    max_page_size = 100


class UserManagementListCreateView(generics.ListCreateAPIView):
    """
    GET: list users (search, filter). POST: create user with password.
    Admin or Django superuser only.
    """

    permission_classes = [IsAdminUser]
    pagination_class = UserManagementPagination

    def get_serializer_class(self):
        if self.request.method == "POST":
            return AdminUserCreateSerializer
        return AdminUserReadSerializer

    def get_queryset(self):
        qs = User.objects.all().order_by("-date_joined").select_related("billing_package")
        search = (self.request.query_params.get("search") or "").strip()
        if search:
            qs = qs.filter(
                Q(username__icontains=search)
                | Q(email__icontains=search)
                | Q(first_name__icontains=search)
                | Q(last_name__icontains=search)
            )
        role = self.request.query_params.get("role")
        if role in {c[0] for c in User.Roles.choices}:
            qs = qs.filter(role=role)
        active = self.request.query_params.get("is_active")
        if active == "true":
            qs = qs.filter(is_active=True)
        elif active == "false":
            qs = qs.filter(is_active=False)
        return qs

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.save()
        read = AdminUserReadSerializer(user, context={"request": request})
        return Response(read.data, status=status.HTTP_201_CREATED)


class UserManagementDetailView(generics.RetrieveUpdateDestroyAPIView):
    """GET/PATCH/DELETE single user. DELETE soft-deactivates (sets is_active=False)."""

    permission_classes = [IsAdminUser]
    queryset = User.objects.all().select_related("billing_package")

    def get_serializer_class(self):
        if self.request.method in ("PATCH", "PUT"):
            return AdminUserUpdateSerializer
        return AdminUserReadSerializer

    def update(self, request, *args, **kwargs):
        partial = kwargs.pop("partial", False)
        instance = self.get_object()
        serializer = self.get_serializer(instance, data=request.data, partial=partial)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        instance.refresh_from_db()
        read = AdminUserReadSerializer(instance, context={"request": request})
        return Response(read.data)

    def perform_destroy(self, instance):
        if instance.pk == self.request.user.pk:
            raise PermissionDenied("You cannot deactivate your own account this way; use profile settings.")
        if instance.role == User.Roles.ADMIN:
            others = User.objects.filter(role=User.Roles.ADMIN, is_active=True).exclude(pk=instance.pk).count()
            if others == 0:
                raise PermissionDenied("Cannot deactivate the last active admin.")
        instance.is_active = False
        instance.save(update_fields=["is_active"])

    def destroy(self, request, *args, **kwargs):
        instance = self.get_object()
        self.perform_destroy(instance)
        return Response(status=status.HTTP_204_NO_CONTENT)
