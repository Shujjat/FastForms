from django.urls import path

from .billing_views import (
    BillingMeView,
    BillingPackageDetailView,
    BillingPackagesListCreateView,
    CheckoutSessionView,
    PortalSessionView,
    StripeWebhookView,
)

urlpatterns = [
    path("packages", BillingPackagesListCreateView.as_view(), name="billing_packages"),
    path("packages/<int:pk>", BillingPackageDetailView.as_view(), name="billing_package_detail"),
    path("me", BillingMeView.as_view(), name="billing_me"),
    path("checkout", CheckoutSessionView.as_view(), name="billing_checkout"),
    path("portal", PortalSessionView.as_view(), name="billing_portal"),
    path("stripe-webhook", StripeWebhookView.as_view(), name="stripe_webhook"),
]
