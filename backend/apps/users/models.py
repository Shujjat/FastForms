from django.contrib.auth.models import AbstractUser
from django.core.exceptions import ValidationError
from django.db import models


class BillingPackage(models.Model):
    """Sellable / assignable billing tier; managed in DB and Django admin."""

    slug = models.SlugField(max_length=32, unique=True)
    name = models.CharField(max_length=64)
    description = models.TextField(blank=True, default="")
    sort_order = models.PositiveSmallIntegerField(default=0)
    is_active = models.BooleanField(
        default=True,
        help_text="Inactive packages are hidden from catalog pickers and Billing (except superuser assignment).",
    )
    is_free_tier = models.BooleanField(
        default=False,
        help_text="Mark the single free/default tier (form limits, branding). Saving clears this flag on all other rows.",
    )
    max_owned_forms = models.PositiveIntegerField(
        null=True,
        blank=True,
        help_text="Max forms this user may own; empty = unlimited.",
    )
    ai_credits_per_period = models.PositiveIntegerField(
        null=True,
        blank=True,
        help_text="AI operations allowed per period for this package; empty = unlimited.",
    )
    ai_usage_period_days = models.PositiveIntegerField(
        default=30,
        help_text="Length of each AI credit period (days).",
    )
    allow_self_select = models.BooleanField(
        default=False,
        help_text="Let creators/admins switch to this plan on Billing without a superuser. Not allowed with a Stripe price (use Checkout instead). Requires Active.",
    )
    stripe_price_id = models.CharField(
        max_length=255,
        null=True,
        blank=True,
        unique=True,
        help_text="Stripe recurring Price ID (price_…). Checkout uses this server-side; webhooks map the paid subscription to this package.",
    )
    price_cents = models.PositiveIntegerField(
        null=True,
        blank=True,
        help_text="Display amount in smallest currency unit (e.g. USD cents). Informational only.",
    )
    price_currency = models.CharField(
        max_length=3,
        default="usd",
        help_text="ISO 4217 lowercase currency code for display (e.g. usd, eur).",
    )

    class Meta:
        ordering = ["sort_order", "id"]

    @classmethod
    def validate_constraints(
        cls,
        *,
        is_free_tier: bool,
        is_active: bool,
        allow_self_select: bool,
        stripe_price_id: str | None,
    ) -> None:
        """Shared rules for API, admin, and model forms."""
        errors: dict[str, list[str]] = {}
        sp = (stripe_price_id or "").strip() or None

        def add(field: str, message: str) -> None:
            errors.setdefault(field, []).append(message)

        if is_free_tier and sp:
            add("stripe_price_id", "Free tier cannot have a Stripe price.")
        if is_free_tier and not is_active:
            add("is_active", "The free tier must stay active so new accounts always have a default plan.")
        if allow_self_select:
            if not is_active:
                add(
                    "allow_self_select",
                    "Inactive packages are not shown on Billing. Activate the package or turn off self-select.",
                )
            if sp and not is_free_tier:
                add(
                    "allow_self_select",
                    "Paid plans with a Stripe price must use Checkout or the customer portal, not Billing self-select.",
                )

        if errors:
            raise ValidationError(errors)

    def clean(self) -> None:
        super().clean()
        type(self).validate_constraints(
            is_free_tier=bool(self.is_free_tier),
            is_active=bool(self.is_active),
            allow_self_select=bool(self.allow_self_select),
            stripe_price_id=self.stripe_price_id,
        )

    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)
        if self.is_free_tier:
            BillingPackage.objects.exclude(pk=self.pk).update(is_free_tier=False)

    def __str__(self):
        return self.name


class User(AbstractUser):
    class Roles(models.TextChoices):
        ADMIN = "admin", "Admin"
        CREATOR = "creator", "Creator"
        ANALYST = "analyst", "Analyst"
        RESPONDENT = "respondent", "Respondent"

    role = models.CharField(max_length=20, choices=Roles.choices, default=Roles.CREATOR)
    phone = models.CharField(max_length=32, blank=True, default="")
    organization = models.CharField(max_length=255, blank=True, default="")
    google_sub = models.CharField(max_length=255, blank=True, null=True, unique=True)

    billing_package = models.ForeignKey(
        BillingPackage,
        on_delete=models.PROTECT,
        related_name="users",
    )
    stripe_customer_id = models.CharField(max_length=255, blank=True, default="")
    stripe_subscription_id = models.CharField(max_length=255, blank=True, default="")
    billing_current_period_end = models.DateTimeField(null=True, blank=True)
    ai_credits_used = models.PositiveIntegerField(default=0)
    ai_usage_period_start = models.DateTimeField(
        null=True,
        blank=True,
        help_text="Start of the current AI credit period (UTC).",
    )

    def save(self, *args, **kwargs):
        if self.pk:
            prev = (
                type(self)
                .objects.filter(pk=self.pk)
                .values_list("billing_package_id", flat=True)
                .first()
            )
            if prev is not None and prev != self.billing_package_id:
                self.ai_credits_used = 0
                self.ai_usage_period_start = None
        if self.billing_package_id is None:
            free = BillingPackage.objects.filter(slug="free").first()
            if free is not None:
                self.billing_package = free
        super().save(*args, **kwargs)


class UserApiKey(models.Model):
    """Long-lived API credential; raw secret shown once at creation (only SHA-256 stored)."""

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["key_hash"]),
            models.Index(fields=["user", "is_active"]),
        ]

    user = models.ForeignKey(
        "users.User",
        on_delete=models.CASCADE,
        related_name="api_keys",
    )
    name = models.CharField(max_length=120, blank=True, default="")
    prefix = models.CharField(max_length=16, db_index=True)
    key_hash = models.CharField(max_length=64, unique=True)
    scopes = models.JSONField(default=list)
    created_at = models.DateTimeField(auto_now_add=True)
    last_used_at = models.DateTimeField(null=True, blank=True)
    is_active = models.BooleanField(default=True)

    SCOPE_FORMS_READ = "forms:read"
    SCOPE_FORMS_WRITE = "forms:write"
    SCOPE_RESPONSES_READ = "responses:read"
    SCOPE_RESPONSES_SUBMIT = "responses:submit"
    ALL_SCOPES = (
        SCOPE_FORMS_READ,
        SCOPE_FORMS_WRITE,
        SCOPE_RESPONSES_READ,
        SCOPE_RESPONSES_SUBMIT,
    )

    def __str__(self):
        return f"{self.prefix}… ({self.user_id})"

    def has_scope(self, scope: str) -> bool:
        return scope in (self.scopes or [])
