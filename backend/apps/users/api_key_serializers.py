from rest_framework import serializers

from .models import UserApiKey


class UserApiKeySerializer(serializers.ModelSerializer):
    class Meta:
        model = UserApiKey
        fields = ("id", "name", "prefix", "scopes", "created_at", "last_used_at", "is_active")
        read_only_fields = fields


class UserApiKeyCreateSerializer(serializers.Serializer):
    name = serializers.CharField(max_length=120, required=False, allow_blank=True, default="")
    scopes = serializers.ListField(child=serializers.CharField(), required=False)

    def validate(self, attrs):
        scopes = attrs.get("scopes")
        if not scopes:
            attrs["scopes"] = list(UserApiKey.ALL_SCOPES)
            return attrs
        allowed = set(UserApiKey.ALL_SCOPES)
        bad = [s for s in scopes if s not in allowed]
        if bad:
            raise serializers.ValidationError({"scopes": f"Unknown scopes: {bad}. Allowed: {sorted(allowed)}"})
        attrs["scopes"] = list(dict.fromkeys(scopes))
        return attrs
