"""Limits on resources owned by the billing account, driven by BillingPackage."""

from rest_framework.exceptions import ValidationError

from apps.forms.models import Form

from .package_usage import max_owned_forms_cap


def assert_can_create_owned_form(user) -> None:
    """Raise ValidationError if the user cannot create another form they own."""
    if not user or not user.is_authenticated:
        return
    cap = max_owned_forms_cap(user)
    if cap is None:
        return
    owned = Form.objects.filter(owner=user).count()
    if owned >= cap:
        raise ValidationError(
            {
                "detail": (
                    f"Your package allows up to {cap} forms you own. "
                    "Upgrade your package or delete forms you no longer need."
                )
            }
        )
