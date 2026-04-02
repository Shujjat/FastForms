from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as DjangoUserAdmin

from .models import User


@admin.register(User)
class UserAdmin(DjangoUserAdmin):
    list_display = (
        "username",
        "email",
        "role",
        "billing_plan",
        "is_staff",
        "is_active",
        "date_joined",
    )
    list_filter = ("role", "billing_plan", "is_staff", "is_active")
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
                    "billing_plan",
                    "billing_current_period_end",
                    "stripe_customer_id",
                    "stripe_subscription_id",
                )
            },
        ),
    )
    add_fieldsets = DjangoUserAdmin.add_fieldsets + (
        (
            "Profile",
            {"fields": ("role", "phone", "organization")},
        ),
    )
