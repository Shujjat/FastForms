from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as DjangoUserAdmin

from .models import BillingPackage, User, UserApiKey


@admin.register(BillingPackage)
class BillingPackageAdmin(admin.ModelAdmin):
    list_display = (
        "name",
        "slug",
        "sort_order",
        "max_owned_forms",
        "ai_credits_per_period",
        "ai_usage_period_days",
        "is_active",
        "is_free_tier",
    )
    list_editable = ("sort_order", "is_active", "is_free_tier")
    search_fields = ("name", "slug")
    ordering = ("sort_order", "id")


@admin.register(User)
class UserAdmin(DjangoUserAdmin):
    list_display = (
        "username",
        "email",
        "role",
        "billing_package",
        "is_staff",
        "is_active",
        "date_joined",
    )
    list_filter = ("role", "billing_package", "is_staff", "is_active")
    search_fields = ("username", "email", "stripe_customer_id", "stripe_subscription_id")

    fieldsets = DjangoUserAdmin.fieldsets + (
        (
            "Profile",
            {"fields": ("role", "phone", "organization", "google_sub")},
        ),
        (
            "Billing",
            {
                "fields": (
                    "billing_package",
                    "billing_current_period_end",
                    "ai_credits_used",
                    "ai_usage_period_start",
                    "stripe_customer_id",
                    "stripe_subscription_id",
                )
            },
        ),
    )
    add_fieldsets = DjangoUserAdmin.add_fieldsets + (
        (
            "Profile",
            {"fields": ("role", "phone", "organization", "billing_package")},
        ),
    )


@admin.register(UserApiKey)
class UserApiKeyAdmin(admin.ModelAdmin):
    list_display = ("id", "prefix", "user", "name", "is_active", "created_at", "last_used_at")
    list_filter = ("is_active",)
    search_fields = ("prefix", "name", "user__username", "user__email")
    raw_id_fields = ("user",)
    readonly_fields = ("prefix", "key_hash", "scopes", "created_at", "last_used_at")
