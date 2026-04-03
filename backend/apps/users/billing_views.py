import logging
from datetime import datetime, timezone as dt_timezone

import stripe
from django.conf import settings
from django.db.models.deletion import ProtectedError
from django.utils.decorators import method_decorator
from django.views.decorators.csrf import csrf_exempt
from rest_framework import generics, permissions, status
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


def _subscription_primary_price_id(subscription) -> str | None:
    """Stripe Subscription.items.data[0].price.id (dict from webhooks or StripeObject)."""

    def _get(key, obj=None):
        o = subscription if obj is None else obj
        if isinstance(o, dict):
            return o.get(key)
        return getattr(o, key, None)

    items = _get("items")
    if not items:
        return None
    data = _get("data", items)
    if not data:
        return None
    first = data[0] if isinstance(data, (list, tuple)) else None
    if not first:
        return None
    price = _get("price", first)
    if price:
        if isinstance(price, dict):
            pid = price.get("id")
        else:
            pid = getattr(price, "id", None)
        if pid:
            return str(pid)
    return None


def _billing_package_for_stripe_price(price_id: str | None) -> BillingPackage | None:
    if not price_id:
        return None
    pkg = BillingPackage.objects.filter(
        stripe_price_id=price_id,
        is_active=True,
        is_free_tier=False,
    ).first()
    if pkg:
        return pkg
    legacy = (getattr(settings, "STRIPE_PRICE_PRO_MONTHLY", None) or "").strip()
    if legacy and price_id == legacy:
        return _stripe_subscription_package()
    return None


def stripe_checkout_available() -> bool:
    if not settings.STRIPE_SECRET_KEY:
        return False
    if BillingPackage.objects.filter(
        is_active=True,
        is_free_tier=False,
        stripe_price_id__isnull=False,
    ).exists():
        return True
    return bool(settings.STRIPE_PRICE_PRO_MONTHLY)


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
        user.save()
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
        price_id = _subscription_primary_price_id(subscription)
        pkg = _billing_package_for_stripe_price(price_id)
        if not pkg:
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

    # Full save so User.save() resets AI usage when billing_package changes.
    user.save()


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
                "stripe_subscription_active": bool(getattr(request.user, "stripe_subscription_id", None)),
                "stripe_subscription_package_slug": getattr(
                    settings, "STRIPE_SUBSCRIPTION_PACKAGE_SLUG", "plus"
                )
                or "plus",
            }
        )


class SelectBillingPackageView(APIView):
    """
    Let creators/admins pick a package marked allow_self_select (Billing page).
    Blocked while stripe_subscription_id is set — use Stripe portal first.
    """

    permission_classes = [permissions.IsAuthenticated, IsCreatorOrAdmin]

    def post(self, request):
        raw = (request.data or {}).get("billing_package_id")
        if raw is None:
            return Response(
                {"detail": "billing_package_id is required."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        try:
            pk = int(raw)
        except (TypeError, ValueError):
            return Response(
                {"detail": "billing_package_id must be an integer."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        pkg = BillingPackage.objects.filter(pk=pk, is_active=True, allow_self_select=True).first()
        if not pkg:
            return Response(
                {"detail": "That package is not available for self-service or is inactive."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        user = request.user
        if getattr(user, "stripe_subscription_id", None):
            return Response(
                {
                    "detail": (
                        "You have an active subscription on file. Use “Manage subscription” to change or cancel "
                        "in Stripe before choosing a different plan here."
                    )
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        if user.billing_package_id == pkg.pk:
            return Response(
                {
                    "detail": "You already have this package.",
                    "billing_package": BillingPackageSerializer(pkg).data,
                    "billing_plan": pkg.slug,
                },
                status=status.HTTP_200_OK,
            )

        user.billing_package = pkg
        user.save()
        return Response(
            {
                "detail": "Package updated.",
                "billing_package": BillingPackageSerializer(pkg).data,
                "billing_plan": pkg.slug,
            },
            status=status.HTTP_200_OK,
        )


class CheckoutSessionView(APIView):
    permission_classes = [permissions.IsAuthenticated, IsCreatorOrAdmin]

    def post(self, request):
        if not stripe_checkout_available():
            return Response(
                {
                    "detail": (
                        "Stripe checkout is not configured. Set STRIPE_SECRET_KEY and either "
                        "put a Stripe Price ID on a paid billing package or set STRIPE_PRICE_PRO_MONTHLY."
                    )
                },
                status=status.HTTP_503_SERVICE_UNAVAILABLE,
            )
        _set_stripe_key()
        user = request.user
        price_id = None
        meta = {"user_id": str(user.id)}
        raw_pkg = (request.data or {}).get("billing_package_id")
        if raw_pkg is not None:
            try:
                pkg_pk = int(raw_pkg)
            except (TypeError, ValueError):
                return Response(
                    {"detail": "billing_package_id must be an integer."},
                    status=status.HTTP_400_BAD_REQUEST,
                )
            pkg = BillingPackage.objects.filter(
                pk=pkg_pk,
                is_active=True,
                is_free_tier=False,
                stripe_price_id__isnull=False,
            ).first()
            if not pkg:
                return Response(
                    {"detail": "That package is not available for Stripe checkout."},
                    status=status.HTTP_400_BAD_REQUEST,
                )
            price_id = pkg.stripe_price_id
            meta["billing_package_id"] = str(pkg_pk)
        else:
            price_id = (getattr(settings, "STRIPE_PRICE_PRO_MONTHLY", None) or "").strip() or None
            if not price_id:
                return Response(
                    {
                        "detail": (
                            "Choose a plan (billing_package_id) or ask your operator to set "
                            "STRIPE_PRICE_PRO_MONTHLY for legacy single-price checkout."
                        )
                    },
                    status=status.HTTP_400_BAD_REQUEST,
                )

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
            line_items=[{"price": price_id, "quantity": 1}],
            success_url=f"{base}/billing?upgraded=1",
            cancel_url=f"{base}/billing?canceled=1",
            metadata=meta,
            subscription_data={"metadata": dict(meta)},
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
        user.save()

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

    def destroy(self, request, *args, **kwargs):
        instance = self.get_object()
        user_count = User.objects.filter(billing_package=instance).count()
        if user_count:
            return Response(
                {
                    "detail": (
                        f"Cannot delete this package: {user_count} user(s) are assigned to it. "
                        "Reassign them in User management first."
                    )
                },
                status=status.HTTP_400_BAD_REQUEST,
            )
        if BillingPackage.objects.count() <= 1:
            return Response(
                {"detail": "Cannot delete the last billing package."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        if instance.is_free_tier:
            other_free = BillingPackage.objects.exclude(pk=instance.pk).filter(is_free_tier=True).exists()
            if not other_free:
                return Response(
                    {
                        "detail": (
                            "This row is still marked as the free tier. Edit another package, enable "
                            '"Free tier" there first (that clears this one), then delete this package.'
                        )
                    },
                    status=status.HTTP_400_BAD_REQUEST,
                )
        try:
            instance.delete()
        except ProtectedError:
            return Response(
                {
                    "detail": (
                        "This package is still in use (e.g. users assigned). "
                        "Reassign those accounts first."
                    )
                },
                status=status.HTTP_400_BAD_REQUEST,
            )
        return Response(status=status.HTTP_204_NO_CONTENT)
