from drf_spectacular.utils import extend_schema, extend_schema_view
from rest_framework import generics, permissions, status
from rest_framework.response import Response

from .api_key_serializers import UserApiKeyCreateSerializer, UserApiKeySerializer
from .api_key_utils import generate_api_key_material
from .models import UserApiKey


@extend_schema_view(
    get=extend_schema(
        summary="List API keys",
        description=(
            "Active and revoked keys for the authenticated user. The secret is never returned after creation. "
            "Use JWT: **Authorize** in Swagger with HTTP bearer, or `Authorization: Bearer <access>`."
        ),
        tags=["API keys"],
    ),
    post=extend_schema(
        summary="Create API key",
        description=(
            "Returns the **key** string once in the response body. Store it securely; it cannot be retrieved again. "
            "Default scopes include all integration permissions; pass a smaller `scopes` list to restrict. "
            "Requires JWT (same as GET)."
        ),
        tags=["API keys"],
        request=UserApiKeyCreateSerializer,
        responses={201: UserApiKeySerializer},
    ),
)
class UserApiKeyListCreateView(generics.ListCreateAPIView):
    permission_classes = [permissions.IsAuthenticated]
    pagination_class = None

    def get_serializer_class(self):
        if self.request.method == "POST":
            return UserApiKeyCreateSerializer
        return UserApiKeySerializer

    def get_queryset(self):
        return UserApiKey.objects.filter(user=self.request.user).order_by("-created_at")

    def create(self, request, *args, **kwargs):
        ser = self.get_serializer(data=request.data)
        ser.is_valid(raise_exception=True)
        raw, prefix, digest = generate_api_key_material()
        obj = UserApiKey.objects.create(
            user=request.user,
            name=ser.validated_data.get("name") or "",
            prefix=prefix,
            key_hash=digest,
            scopes=ser.validated_data["scopes"],
        )
        out = UserApiKeySerializer(obj).data
        out["key"] = raw
        return Response(out, status=status.HTTP_201_CREATED)


@extend_schema(
    summary="Revoke API key",
    description="Marks the key inactive. Existing requests with that secret will fail immediately. Requires JWT.",
    tags=["API keys"],
)
class UserApiKeyRevokeView(generics.DestroyAPIView):
    permission_classes = [permissions.IsAuthenticated]
    serializer_class = UserApiKeySerializer

    def get_queryset(self):
        return UserApiKey.objects.filter(user=self.request.user)

    def perform_destroy(self, instance):
        instance.is_active = False
        instance.save(update_fields=["is_active"])
