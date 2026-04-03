from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError as DjangoValidationError
from rest_framework import serializers

from .models import BillingPackage
from .package_usage import ai_period_end_utc, max_owned_forms_cap

User = get_user_model()

_PUBLIC_ROLES = ("creator", "respondent")


class BillingPackageSerializer(serializers.ModelSerializer):
    """
    Read-only package catalog. Checkout still accepts only billing_package_id — never a raw price id from the client.
    stripe_price_id is included so superuser UIs can edit packages; it is not a secret in Stripe’s model.
    """

    stripe_subscribable = serializers.SerializerMethodField()

    class Meta:
        model = BillingPackage
        fields = (
            "id",
            "slug",
            "name",
            "description",
            "sort_order",
            "is_active",
            "is_free_tier",
            "max_owned_forms",
            "ai_credits_per_period",
            "ai_usage_period_days",
            "allow_self_select",
            "stripe_price_id",
            "price_cents",
            "price_currency",
            "stripe_subscribable",
        )
        read_only_fields = ("stripe_price_id",)

    def get_stripe_subscribable(self, obj):
        return bool(obj.stripe_price_id) and not obj.is_free_tier and obj.is_active


class BillingPackageWriteSerializer(serializers.ModelSerializer):
    """Create/update billing packages (superuser API)."""

    max_owned_forms = serializers.IntegerField(required=False, allow_null=True, min_value=1)
    ai_credits_per_period = serializers.IntegerField(required=False, allow_null=True, min_value=1)
    ai_usage_period_days = serializers.IntegerField(required=False, min_value=1, max_value=366)
    stripe_price_id = serializers.CharField(required=False, allow_null=True, allow_blank=True, max_length=255)
    price_currency = serializers.CharField(required=False, allow_blank=True, max_length=3, default="usd")

    class Meta:
        model = BillingPackage
        fields = (
            "slug",
            "name",
            "description",
            "sort_order",
            "is_active",
            "is_free_tier",
            "max_owned_forms",
            "ai_credits_per_period",
            "ai_usage_period_days",
            "allow_self_select",
            "stripe_price_id",
            "price_cents",
            "price_currency",
        )

    def validate_slug(self, value):
        s = str(value).strip().lower()
        if not s:
            raise serializers.ValidationError("Slug is required.")
        allowed = set("abcdefghijklmnopqrstuvwxyz0123456789_-")
        if not all(c in allowed for c in s):
            raise serializers.ValidationError("Use lowercase letters, digits, hyphens, or underscores only.")
        if self.instance is not None and s != self.instance.slug:
            raise serializers.ValidationError("Slug cannot be changed after the package is created.")
        return s

    def validate_stripe_price_id(self, value):
        if value is None or value == "":
            return None
        v = str(value).strip()
        if not v:
            return None
        if not v.startswith("price_"):
            raise serializers.ValidationError("Use a Stripe recurring price ID (starts with price_).")
        return v

    def validate_price_currency(self, value):
        if not value:
            return "usd"
        return str(value).strip().lower()[:3] or "usd"

    def validate(self, attrs):
        inst = self.instance

        def eff(key, default=None):
            if key in attrs:
                return attrs[key]
            return getattr(inst, key, default) if inst is not None else default

        is_free = bool(eff("is_free_tier", False))
        is_act = bool(eff("is_active", True))
        allow_ss = bool(eff("allow_self_select", False))
        if "stripe_price_id" in attrs:
            sp = attrs.get("stripe_price_id")
        else:
            sp = inst.stripe_price_id if inst else None
        sp = sp or None

        try:
            BillingPackage.validate_constraints(
                is_free_tier=is_free,
                is_active=is_act,
                allow_self_select=allow_ss,
                stripe_price_id=sp,
            )
        except DjangoValidationError as e:
            raise serializers.ValidationError(e.message_dict if hasattr(e, "message_dict") else e)

        return attrs

    def create(self, validated_data):
        validated_data.setdefault("ai_usage_period_days", 30)
        if not BillingPackage.objects.filter(is_free_tier=True).exists():
            validated_data["is_free_tier"] = True
        return BillingPackage.objects.create(**validated_data)

    def update(self, instance, validated_data):
        if (
            validated_data.get("is_free_tier") is False
            and instance.is_free_tier
            and not BillingPackage.objects.exclude(pk=instance.pk).filter(is_free_tier=True).exists()
        ):
            raise serializers.ValidationError(
                {"is_free_tier": "Mark another package as the free tier before clearing this one."}
            )
        for attr, val in validated_data.items():
            setattr(instance, attr, val)
        instance.save()
        return instance


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
    billing_plan = serializers.SerializerMethodField()
    package_max_owned_forms = serializers.SerializerMethodField()
    owned_forms_at_package_limit = serializers.SerializerMethodField()
    ai_credits_limit = serializers.SerializerMethodField()
    ai_credits_used = serializers.IntegerField(read_only=True)
    ai_usage_period_days = serializers.SerializerMethodField()
    ai_credits_period_ends_at = serializers.SerializerMethodField()

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
            "package_max_owned_forms",
            "owned_forms_at_package_limit",
            "ai_credits_limit",
            "ai_credits_used",
            "ai_usage_period_days",
            "ai_credits_period_ends_at",
        )
        read_only_fields = (
            "is_superuser",
            "billing_plan",
            "billing_current_period_end",
            "owned_forms_count",
            "free_tier_max_forms",
            "package_max_owned_forms",
            "owned_forms_at_package_limit",
            "ai_credits_limit",
            "ai_credits_used",
            "ai_usage_period_days",
            "ai_credits_period_ends_at",
        )

    def get_billing_plan(self, obj):
        if obj.billing_package_id:
            return obj.billing_package.slug
        return "free"

    def get_owned_forms_count(self, obj):
        from apps.forms.models import Form

        return Form.objects.filter(owner=obj).count()

    def get_free_tier_max_forms(self, obj):
        """Legacy field: same as effective owned-form cap when set, else global default."""
        cap = max_owned_forms_cap(obj)
        if cap is not None:
            return cap
        return int(getattr(settings, "FREE_TIER_MAX_FORMS", 5))

    def get_package_max_owned_forms(self, obj):
        return max_owned_forms_cap(obj)

    def get_owned_forms_at_package_limit(self, obj):
        cap = max_owned_forms_cap(obj)
        if cap is None:
            return False
        return self.get_owned_forms_count(obj) >= cap

    def get_ai_credits_limit(self, obj):
        pkg = obj.billing_package
        if not pkg:
            return None
        return pkg.ai_credits_per_period

    def get_ai_usage_period_days(self, obj):
        pkg = obj.billing_package
        if not pkg or pkg.ai_credits_per_period is None:
            return None
        return pkg.ai_usage_period_days

    def get_ai_credits_period_ends_at(self, obj):
        end = ai_period_end_utc(obj)
        return end.isoformat() if end else None


class AdminUserReadSerializer(serializers.ModelSerializer):
    """List/detail for admin user management."""

    billing_package = BillingPackageSerializer(read_only=True)
    billing_plan = serializers.SerializerMethodField()

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
            "billing_package",
            "billing_plan",
            "billing_current_period_end",
            "date_joined",
            "last_login",
        )
        read_only_fields = ("date_joined", "last_login", "is_superuser", "billing_current_period_end")

    def get_billing_plan(self, obj):
        if obj.billing_package_id:
            return obj.billing_package.slug
        return "free"


class AdminUserCreateSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True, min_length=8)
    billing_package = serializers.PrimaryKeyRelatedField(
        queryset=BillingPackage.objects.all(),
        required=False,
        allow_null=False,
    )

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
            "billing_package",
        )
        read_only_fields = ("id",)

    def validate(self, attrs):
        request = self.context.get("request")
        if attrs.get("is_staff") and request and not request.user.is_superuser:
            raise serializers.ValidationError({"is_staff": "Only superusers can grant staff access."})
        if "billing_package" in attrs and attrs["billing_package"] is not None:
            if not request or not request.user.is_superuser:
                raise serializers.ValidationError(
                    {"billing_package": "Only superusers can set the billing package."}
                )
        return attrs

    def create(self, validated_data):
        billing_package = validated_data.pop("billing_package", None)
        password = validated_data.pop("password")
        user = User(**validated_data)
        if billing_package is not None:
            user.billing_package = billing_package
        user.set_password(password)
        user.save()
        return user


class AdminUserUpdateSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True, required=False, allow_blank=True, default="")
    billing_package = serializers.PrimaryKeyRelatedField(
        queryset=BillingPackage.objects.all(),
        required=False,
        allow_null=False,
    )

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
            "billing_package",
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

        if "billing_package" in attrs and attrs["billing_package"] is not None:
            if not actor or not actor.is_superuser:
                raise serializers.ValidationError(
                    {"billing_package": "Only superusers can change the billing package."}
                )

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
