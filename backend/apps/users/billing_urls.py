from django.urls import path

from .billing_views import (
    BillingMeView,
    BillingPackageDetailView,
    BillingPackagesListCreateView,
    CheckoutSessionView,
    PortalSessionView,
    SelectBillingPackageView,
    StripeWebhookView,
)

urlpatterns = [
    path("select-package", SelectBillingPackageView.as_view(), name="billing_select_package"),
    path("packages", BillingPackagesListCreateView.as_view(), name="billing_packages"),
    # With and without trailing slash — some clients/proxies normalize to a trailing slash on DELETE.
    path("packages/<int:pk>/", BillingPackageDetailView.as_view(), name="billing_package_detail"),
    path("packages/<int:pk>", BillingPackageDetailView.as_view(), name="billing_package_detail_no_slash"),
    path("me", BillingMeView.as_view(), name="billing_me"),
    path("checkout", CheckoutSessionView.as_view(), name="billing_checkout"),
    path("portal", PortalSessionView.as_view(), name="billing_portal"),
    path("stripe-webhook", StripeWebhookView.as_view(), name="stripe_webhook"),
]
