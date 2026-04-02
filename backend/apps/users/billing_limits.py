"""Free-tier limits on resources owned by the billing account (e.g. forms)."""

from django.conf import settings
from django.contrib.auth import get_user_model
from rest_framework.exceptions import ValidationError

from apps.forms.models import Form

User = get_user_model()


def assert_can_create_owned_form(user) -> None:
    """Raise ValidationError if the user cannot create another form they own."""
    if not user or not user.is_authenticated:
        return
    if getattr(user, "billing_plan", User.BillingPlan.FREE) == User.BillingPlan.PRO:
        return
    max_forms = int(getattr(settings, "FREE_TIER_MAX_FORMS", 5))
    owned = Form.objects.filter(owner=user).count()
    if owned >= max_forms:
        raise ValidationError(
            {
                "detail": (
                    f"Free plan allows up to {max_forms} forms you own. "
                    "Upgrade to Pro to create more."
                )
            }
        )
