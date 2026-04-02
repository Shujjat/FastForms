from django.contrib.auth.models import AbstractUser
from django.db import models


class User(AbstractUser):
    class Roles(models.TextChoices):
        ADMIN = "admin", "Admin"
        CREATOR = "creator", "Creator"
        ANALYST = "analyst", "Analyst"
        RESPONDENT = "respondent", "Respondent"

    class BillingPlan(models.TextChoices):
        FREE = "free", "Free"
        PRO = "pro", "Pro"

    role = models.CharField(max_length=20, choices=Roles.choices, default=Roles.CREATOR)
    phone = models.CharField(max_length=32, blank=True, default="")
    organization = models.CharField(max_length=255, blank=True, default="")
    google_sub = models.CharField(max_length=255, blank=True, null=True, unique=True)

    billing_plan = models.CharField(
        max_length=20,
        choices=BillingPlan.choices,
        default=BillingPlan.FREE,
        db_index=True,
    )
    stripe_customer_id = models.CharField(max_length=255, blank=True, default="")
    stripe_subscription_id = models.CharField(max_length=255, blank=True, default="")
    billing_current_period_end = models.DateTimeField(null=True, blank=True)
