"""Billing package helpers (shared across limits, Stripe, serializers)."""


def plan_is_free(user_or_pkg) -> bool:
    """True if the user (or BillingPackage) is on the free tier."""
    if user_or_pkg is None:
        return True
    pkg = getattr(user_or_pkg, "billing_package", None)
    if pkg is not None:
        return bool(pkg.is_free_tier)
    if hasattr(user_or_pkg, "is_free_tier"):
        return bool(user_or_pkg.is_free_tier)
    return False


def plan_unlocks_paid_features(user) -> bool:
    return not plan_is_free(user)
