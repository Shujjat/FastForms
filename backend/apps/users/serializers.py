from django.conf import settings
from django.contrib.auth import get_user_model
from rest_framework import serializers

User = get_user_model()

_PUBLIC_ROLES = ("creator", "respondent")


class RegisterSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True, min_length=8, required=True)
    username = serializers.CharField(required=True, max_length=150)
    email = serializers.EmailField(required=True)
    role = serializers.ChoiceField(choices=[(r, r) for r in _PUBLIC_ROLES], required=True)
    first_name = serializers.CharField(required=False, allow_blank=True, default="")
    last_name = serializers.CharField(required=False, allow_blank=True, default="")
    phone = serializers.CharField(required=False, allow_blank=True, default="", max_length=32)
    organization = serializers.CharField(required=False, allow_blank=True, default="", max_length=255)

    class Meta:
        model = User
        fields = (
            "id",
            "username",
            "email",
            "password",
            "role",
            "first_name",
            "last_name",
            "phone",
            "organization",
        )
        read_only_fields = ("id",)

    def create(self, validated_data):
        password = validated_data.pop("password")
        user = User(**validated_data)
        user.set_password(password)
        user.save()
        return user


class UserSerializer(serializers.ModelSerializer):
    """Current user profile (`/api/auth/me`)."""

    owned_forms_count = serializers.SerializerMethodField()
    free_tier_max_forms = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = (
            "id",
            "username",
            "email",
            "role",
            "first_name",
            "last_name",
            "phone",
            "organization",
            "is_superuser",
            "billing_plan",
            "billing_current_period_end",
            "owned_forms_count",
            "free_tier_max_forms",
        )
        read_only_fields = (
            "is_superuser",
            "billing_plan",
            "billing_current_period_end",
            "owned_forms_count",
            "free_tier_max_forms",
        )

    def get_owned_forms_count(self, obj):
        from apps.forms.models import Form

        return Form.objects.filter(owner=obj).count()

    def get_free_tier_max_forms(self, obj):
        return int(getattr(settings, "FREE_TIER_MAX_FORMS", 5))


class AdminUserReadSerializer(serializers.ModelSerializer):
    """List/detail for admin user management."""

    class Meta:
        model = User
        fields = (
            "id",
            "username",
            "email",
            "role",
            "first_name",
            "last_name",
            "phone",
            "organization",
            "is_active",
            "is_staff",
            "is_superuser",
            "date_joined",
            "last_login",
        )
        read_only_fields = ("date_joined", "last_login", "is_superuser")


class AdminUserCreateSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True, min_length=8)

    class Meta:
        model = User
        fields = (
            "id",
            "username",
            "email",
            "password",
            "role",
            "first_name",
            "last_name",
            "phone",
            "organization",
            "is_active",
            "is_staff",
        )
        read_only_fields = ("id",)

    def validate(self, attrs):
        request = self.context.get("request")
        if attrs.get("is_staff") and request and not request.user.is_superuser:
            raise serializers.ValidationError({"is_staff": "Only superusers can grant staff access."})
        return attrs

    def create(self, validated_data):
        password = validated_data.pop("password")
        user = User(**validated_data)
        user.set_password(password)
        user.save()
        return user


class AdminUserUpdateSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True, required=False, allow_blank=True, default="")

    class Meta:
        model = User
        fields = (
            "username",
            "email",
            "role",
            "first_name",
            "last_name",
            "phone",
            "organization",
            "is_active",
            "is_staff",
            "password",
        )

    def validate_username(self, value):
        inst = self.instance
        qs = User.objects.filter(username__iexact=value)
        if inst:
            qs = qs.exclude(pk=inst.pk)
        if qs.exists():
            raise serializers.ValidationError("A user with this username already exists.")
        return value

    def validate_email(self, value):
        inst = self.instance
        qs = User.objects.filter(email__iexact=value)
        if inst:
            qs = qs.exclude(pk=inst.pk)
        if qs.exists():
            raise serializers.ValidationError("A user with this email already exists.")
        return value

    def validate_password(self, value):
        if value and len(str(value)) < 8:
            raise serializers.ValidationError("Password must be at least 8 characters.")
        return value

    def validate(self, attrs):
        request = self.context.get("request")
        actor = request.user if request else None
        inst = self.instance
        if not inst:
            return attrs

        final_role = attrs.get("role", inst.role)
        final_active = attrs.get("is_active", inst.is_active)

        if actor and inst.pk == actor.pk and "is_active" in attrs and attrs["is_active"] is False:
            raise serializers.ValidationError({"is_active": "You cannot deactivate your own account."})

        if attrs.get("is_staff") is not None and actor and not actor.is_superuser:
            if attrs.get("is_staff") != inst.is_staff:
                raise serializers.ValidationError({"is_staff": "Only superusers can change staff access."})

        if inst.role == User.Roles.ADMIN:
            others = User.objects.filter(role=User.Roles.ADMIN, is_active=True).exclude(pk=inst.pk).count()
            if final_role != User.Roles.ADMIN and others == 0:
                raise serializers.ValidationError({"role": "Cannot remove the last active admin."})
            if final_active is False and others == 0:
                raise serializers.ValidationError({"is_active": "Cannot deactivate the last active admin."})

        return attrs

    def update(self, instance, validated_data):
        password = validated_data.pop("password", None)
        for attr, val in validated_data.items():
            setattr(instance, attr, val)
        if password and str(password).strip():
            instance.set_password(password)
        instance.save()
        return instance


class GoogleAuthSerializer(serializers.Serializer):
    credential = serializers.CharField(required=True, trim_whitespace=False)
    role = serializers.ChoiceField(choices=[(r, r) for r in _PUBLIC_ROLES], required=False, default="respondent")
