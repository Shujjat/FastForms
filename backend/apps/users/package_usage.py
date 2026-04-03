"""Per-user usage against limits defined on the user's assigned BillingPackage."""

from __future__ import annotations

from datetime import timedelta

from django.contrib.auth import get_user_model
from django.db import transaction
from django.db.models import F
from django.utils import timezone
from rest_framework.exceptions import ValidationError

User = get_user_model()


def _period_days(package) -> int:
    d = getattr(package, "ai_usage_period_days", None) or 30
    return max(1, int(d))


def rollover_ai_period_if_needed(user: User) -> None:
    """
    If the user's AI usage period has elapsed, reset counters.
    Call inside a transaction with the user row locked when enforcing credits.
    """
    package = user.billing_package
    if not package or package.ai_credits_per_period is None:
        return
    now = timezone.now()
    start = user.ai_usage_period_start
    days = _period_days(package)
    if start is None:
        # Start the first billing window; keep existing ai_credits_used (e.g. operator-set or carried over).
        User.objects.filter(pk=user.pk).update(ai_usage_period_start=now)
        user.ai_usage_period_start = now
        return
    if now >= start + timedelta(days=days):
        User.objects.filter(pk=user.pk).update(
            ai_usage_period_start=now,
            ai_credits_used=0,
        )
        user.ai_usage_period_start = now
        user.ai_credits_used = 0


def ai_period_end_utc(user: User):
    """When the current AI credit period rolls over (or None if unlimited)."""
    package = user.billing_package
    if not package or package.ai_credits_per_period is None:
        return None
    start = user.ai_usage_period_start
    if start is None:
        return None
    return start + timedelta(days=_period_days(package))


def assert_ai_credits_available(user: User, cost: int = 1) -> None:
    """Raise ValidationError if the user cannot spend AI credits (before calling the LLM)."""
    package = user.billing_package
    if not package or package.ai_credits_per_period is None:
        return
    if cost < 1:
        return
    with transaction.atomic():
        locked = User.objects.select_for_update().get(pk=user.pk)
        rollover_ai_period_if_needed(locked)
        locked.refresh_from_db(
            fields=["ai_credits_used", "ai_usage_period_start", "billing_package_id"]
        )
        package = locked.billing_package
        if not package or package.ai_credits_per_period is None:
            return
        if locked.ai_credits_used + cost > package.ai_credits_per_period:
            raise ValidationError(
                {
                    "detail": (
                        f"AI credit limit reached for your package ({package.ai_credits_per_period} per "
                        f"{_period_days(package)} day period). Try again after the period resets or upgrade."
                    )
                }
            )


def consume_ai_credits(user: User, cost: int = 1) -> None:
    """Increment AI usage after a successful LLM call. No-op if credits are unlimited."""
    package = user.billing_package
    if not package or package.ai_credits_per_period is None:
        return
    if cost < 1:
        return
    with transaction.atomic():
        locked = User.objects.select_for_update().get(pk=user.pk)
        rollover_ai_period_if_needed(locked)
        package = locked.billing_package
        if not package or package.ai_credits_per_period is None:
            return
        User.objects.filter(pk=locked.pk).update(ai_credits_used=F("ai_credits_used") + cost)


def max_owned_forms_cap(user) -> int | None:
    """None = unlimited owned forms for this user's package."""
    if not user or not user.is_authenticated:
        return None
    pkg = getattr(user, "billing_package", None)
    if pkg is None:
        return None
    cap = pkg.max_owned_forms
    return cap  # may be None
