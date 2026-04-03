import logging
from datetime import datetime, timezone as dt_timezone

import stripe
from django.conf import settings
from django.utils.decorators import method_decorator
from django.views.decorators.csrf import csrf_exempt
from rest_framework import generics, permissions, status
from rest_framework.exceptions import ValidationError
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.forms.models import Form
from apps.forms.permissions import IsCreatorOrAdmin

from .models import BillingPackage, User
from .package_usage import ai_period_end_utc, max_owned_forms_cap
from .permissions import IsDjangoSuperuser
from .serializers import BillingPackageSerializer, BillingPackageWriteSerializer

logger = logging.getLogger(__name__)


def _free_billing_package():
    return BillingPackage.objects.filter(slug="free").first()


def _stripe_subscription_package():
    slug = getattr(settings, "STRIPE_SUBSCRIPTION_PACKAGE_SLUG", "plus") or "plus"
    pkg = BillingPackage.objects.filter(slug=slug).first()
    if pkg:
        return pkg
    logger.warning(
        "BillingPackage slug %r missing (STRIPE_SUBSCRIPTION_PACKAGE_SLUG); trying plus, then free.",
        slug,
    )
    return BillingPackage.objects.filter(slug="plus").first() or _free_billing_package()


def stripe_checkout_available() -> bool:
    return bool(settings.STRIPE_SECRET_KEY and settings.STRIPE_PRICE_PRO_MONTHLY)


def _set_stripe_key() -> None:
    stripe.api_key = settings.STRIPE_SECRET_KEY


def subscription_status_grants_paid(sub_status: str) -> bool:
    return sub_status in ("active", "trialing", "past_due")


def apply_subscription_to_user(user: User, subscription) -> None:
    """Update user billing fields from a Stripe Subscription object or dict-like."""
    if subscription is None:
        free = _free_billing_package()
        if free:
            user.billing_package = free
        user.billing_current_period_end = None
        user.save(update_fields=["billing_package", "billing_current_period_end"])
        return

    def _get(key):
        if isinstance(subscription, dict):
            return subscription.get(key)
        return getattr(subscription, key, None)

    sub_status = _get("status") or ""
    cust = _get("customer")
    if cust and not user.stripe_customer_id:
        user.stripe_customer_id = cust
    sub_id = _get("id")
    if sub_id:
        user.stripe_subscription_id = sub_id

    period_end = _get("current_period_end")
    if subscription_status_grants_paid(sub_status):
        pkg = _stripe_subscription_package()
        if pkg:
            user.billing_package = pkg
        if period_end:
            user.billing_current_period_end = datetime.fromtimestamp(
                int(period_end), tz=dt_timezone.utc
            )
    else:
        free = _free_billing_package()
        if free:
            user.billing_package = free
        user.billing_current_period_end = None

    user.save(
        update_fields=[
            "billing_package",
            "billing_current_period_end",
            "stripe_customer_id",
            "stripe_subscription_id",
        ]
    )


class BillingMeView(APIView):
    permission_classes = [permissions.IsAuthenticated, IsCreatorOrAdmin]

    def get(self, request):
        owned = Form.objects.filter(owner=request.user).count()
        pkg = request.user.billing_package
        cap = max_owned_forms_cap(request.user)
        period_end = ai_period_end_utc(request.user)
        return Response(
            {
                "billing_plan": pkg.slug if pkg else "free",
                "billing_package": BillingPackageSerializer(pkg).data if pkg else None,
                "billing_current_period_end": request.user.billing_current_period_end,
                "owned_forms_count": owned,
                "free_tier_max_forms": cap
                if cap is not None
                else settings.FREE_TIER_MAX_FORMS,
                "usage": {
                    "max_owned_forms": cap,
                    "owned_forms_count": owned,
                    "at_owned_forms_limit": cap is not None and owned >= cap,
                    "ai_credits_limit": pkg.ai_credits_per_period if pkg else None,
                    "ai_credits_used": request.user.ai_credits_used,
                    "ai_usage_period_days": (
                        pkg.ai_usage_period_days if pkg and pkg.ai_credits_per_period else None
                    ),
                    "ai_credits_period_ends_at": period_end.isoformat() if period_end else None,
                },
                "stripe_checkout_available": stripe_checkout_available(),
                "stripe_portal_available": bool(request.user.stripe_customer_id),
                "stripe_subscription_package_slug": getattr(
                    settings, "STRIPE_SUBSCRIPTION_PACKAGE_SLUG", "plus"
                )
                or "plus",
            }
        )


class CheckoutSessionView(APIView):
    permission_classes = [permissions.IsAuthenticated, IsCreatorOrAdmin]

    def post(self, request):
        if not stripe_checkout_available():
            return Response(
                {"detail": "Stripe checkout is not configured (keys / price ID)."},
                status=status.HTTP_503_SERVICE_UNAVAILABLE,
            )
        _set_stripe_key()
        user = request.user
        base = settings.FRONTEND_BASE_URL.rstrip("/")
        if not user.stripe_customer_id:
            customer = stripe.Customer.create(
                email=user.email or None,
                metadata={"user_id": str(user.id)},
            )
            user.stripe_customer_id = customer.id
            user.save(update_fields=["stripe_customer_id"])

        session = stripe.checkout.Session.create(
            mode="subscription",
            customer=user.stripe_customer_id,
            line_items=[{"price": settings.STRIPE_PRICE_PRO_MONTHLY, "quantity": 1}],
            success_url=f"{base}/billing?upgraded=1",
            cancel_url=f"{base}/billing?canceled=1",
            metadata={"user_id": str(user.id)},
            subscription_data={"metadata": {"user_id": str(user.id)}},
        )
        return Response({"url": session.url}, status=status.HTTP_201_CREATED)


class PortalSessionView(APIView):
    permission_classes = [permissions.IsAuthenticated, IsCreatorOrAdmin]

    def post(self, request):
        if not settings.STRIPE_SECRET_KEY:
            return Response(
                {"detail": "Stripe is not configured."},
                status=status.HTTP_503_SERVICE_UNAVAILABLE,
            )
        if not request.user.stripe_customer_id:
            return Response(
                {"detail": "No Stripe customer on file."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        _set_stripe_key()
        base = settings.FRONTEND_BASE_URL.rstrip("/")
        session = stripe.billing_portal.Session.create(
            customer=request.user.stripe_customer_id,
            return_url=f"{base}/billing",
        )
        return Response({"url": session.url}, status=status.HTTP_201_CREATED)


@method_decorator(csrf_exempt, name="dispatch")
class StripeWebhookView(APIView):
    authentication_classes = []
    permission_classes = []

    def post(self, request):
        if not settings.STRIPE_WEBHOOK_SECRET:
            logger.warning("Stripe webhook received but STRIPE_WEBHOOK_SECRET is unset")
            return Response(status=status.HTTP_503_SERVICE_UNAVAILABLE)
        payload = request.body
        sig = request.META.get("HTTP_STRIPE_SIGNATURE")
        if not sig:
            return Response(status=status.HTTP_400_BAD_REQUEST)
        _set_stripe_key()
        try:
            event = stripe.Webhook.construct_event(
                payload, sig, settings.STRIPE_WEBHOOK_SECRET
            )
        except ValueError:
            return Response(status=status.HTTP_400_BAD_REQUEST)
        except stripe.SignatureVerificationError:
            return Response(status=status.HTTP_400_BAD_REQUEST)

        etype = event["type"]
        data = event["data"]["object"]

        try:
            if etype == "checkout.session.completed":
                self._on_checkout_completed(data)
            elif etype == "customer.subscription.updated":
                self._on_subscription_updated(data)
            elif etype == "customer.subscription.deleted":
                self._on_subscription_deleted(data)
        except Exception:
            logger.exception("Stripe webhook handler failed for event %s", etype)
            return Response(status=status.HTTP_500_INTERNAL_SERVER_ERROR)

        return Response({"received": True})

    def _on_checkout_completed(self, session):
        meta = session.get("metadata") or {}
        user_id = meta.get("user_id")
        if not user_id:
            return
        user = User.objects.filter(pk=user_id).first()
        if not user:
            return
        customer_id = session.get("customer")
        sub_id = session.get("subscription")
        if customer_id:
            user.stripe_customer_id = customer_id
        if sub_id:
            user.stripe_subscription_id = sub_id
            user.save(
                update_fields=["stripe_customer_id", "stripe_subscription_id"]
            )
            sub = stripe.Subscription.retrieve(sub_id)
            apply_subscription_to_user(user, sub)
        else:
            user.save(update_fields=["stripe_customer_id"])

    def _on_subscription_updated(self, sub_obj):
        customer_id = sub_obj.get("customer")
        sub_id = sub_obj.get("id")
        user = self._user_for_stripe_customer(customer_id, sub_id)
        if user:
            apply_subscription_to_user(user, sub_obj)

    def _on_subscription_deleted(self, sub_obj):
        customer_id = sub_obj.get("customer")
        sub_id = sub_obj.get("id")
        user = self._user_for_stripe_customer(customer_id, sub_id)
        if not user:
            return
        if user.stripe_subscription_id == sub_id:
            user.stripe_subscription_id = ""
        free = _free_billing_package()
        if free:
            user.billing_package = free
        user.billing_current_period_end = None
        user.save(
            update_fields=[
                "stripe_subscription_id",
                "billing_package",
                "billing_current_period_end",
            ]
        )

    def _user_for_stripe_customer(self, customer_id, sub_id):
        if not customer_id:
            return None
        qs = User.objects.filter(stripe_customer_id=customer_id)
        user = qs.first()
        if user:
            return user
        if sub_id:
            return User.objects.filter(stripe_subscription_id=sub_id).first()
        return None


class BillingPackagesListCreateView(generics.ListCreateAPIView):
    """GET: list packages (any authenticated user). POST: create (superuser)."""

    queryset = BillingPackage.objects.all().order_by("sort_order", "id")
    # Global DRF PageNumberPagination would wrap the list in { results, count }; keep a plain array for UIs.
    pagination_class = None

    def get_permissions(self):
        if self.request.method == "POST":
            return [permissions.IsAuthenticated(), IsDjangoSuperuser()]
        return [permissions.IsAuthenticated()]

    def get_serializer_class(self):
        if self.request.method == "POST":
            return BillingPackageWriteSerializer
        return BillingPackageSerializer

    def create(self, request, *args, **kwargs):
        ser = self.get_serializer(data=request.data)
        ser.is_valid(raise_exception=True)
        instance = ser.save()
        return Response(BillingPackageSerializer(instance).data, status=status.HTTP_201_CREATED)


class BillingPackageDetailView(generics.RetrieveUpdateDestroyAPIView):
    """GET: package detail. PATCH/DELETE: superuser."""

    queryset = BillingPackage.objects.all()

    def get_permissions(self):
        if self.request.method == "GET":
            return [permissions.IsAuthenticated()]
        return [permissions.IsAuthenticated(), IsDjangoSuperuser()]

    def get_serializer_class(self):
        if self.request.method in ("PATCH", "PUT"):
            return BillingPackageWriteSerializer
        return BillingPackageSerializer

    def update(self, request, *args, **kwargs):
        partial = kwargs.pop("partial", False)
        instance = self.get_object()
        ser = self.get_serializer(instance, data=request.data, partial=partial)
        ser.is_valid(raise_exception=True)
        ser.save()
        instance.refresh_from_db()
        return Response(BillingPackageSerializer(instance).data)

    def perform_destroy(self, instance):
        user_count = User.objects.filter(billing_package=instance).count()
        if user_count:
            raise ValidationError(
                {
                    "detail": (
                        f"Cannot delete this package: {user_count} user(s) are assigned to it. "
                        "Reassign them in User management first."
                    )
                }
            )
        if BillingPackage.objects.count() <= 1:
            raise ValidationError({"detail": "Cannot delete the last billing package."})
        if instance.is_free_tier:
            other_free = BillingPackage.objects.exclude(pk=instance.pk).filter(is_free_tier=True).exists()
            if not other_free:
                raise ValidationError(
                    {
                        "detail": (
                            "Cannot delete the free-tier package while no other package is marked as free. "
                            "Edit another package and set it as the free tier first."
                        )
                    }
                )
        instance.delete()
