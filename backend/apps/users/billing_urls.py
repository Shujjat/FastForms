from django.urls import path

from .billing_views import (
    BillingMeView,
    CheckoutSessionView,
    PortalSessionView,
    StripeWebhookView,
)

urlpatterns = [
    path("me", BillingMeView.as_view(), name="billing_me"),
    path("checkout", CheckoutSessionView.as_view(), name="billing_checkout"),
    path("portal", PortalSessionView.as_view(), name="billing_portal"),
    path("stripe-webhook", StripeWebhookView.as_view(), name="stripe_webhook"),
]
