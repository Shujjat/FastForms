from unittest.mock import MagicMock, patch

import pytest
from django.contrib.auth import get_user_model
from django.test import override_settings
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import RefreshToken

from apps.forms.models import Form
from apps.users.billing_views import apply_subscription_to_user
from apps.users.models import BillingPackage

User = get_user_model()


def _auth_client(user):
    client = APIClient()
    client.credentials(HTTP_AUTHORIZATION=f"Bearer {RefreshToken.for_user(user).access_token}")
    return client


@pytest.mark.django_db
@override_settings(FREE_TIER_MAX_FORMS=2)
def test_free_tier_blocks_form_create_when_at_cap():
    user = User.objects.create_user(
        username="creator1",
        email="c1@example.com",
        password="testpass12",
        role=User.Roles.CREATOR,
    )
    free_pkg = BillingPackage.objects.get(slug="free")
    free_pkg.max_owned_forms = 2
    free_pkg.save(update_fields=["max_owned_forms"])
    for i in range(2):
        Form.objects.create(owner=user, title=f"Form {i}")

    client = _auth_client(user)
    resp = client.post("/api/forms", {"title": "Over limit", "description": ""}, format="json")
    assert resp.status_code == 400
    assert "free" in str(resp.data).lower() or "upgrade" in str(resp.data).lower()


@pytest.mark.django_db
@override_settings(FREE_TIER_MAX_FORMS=2)
def test_paid_package_allows_form_create_past_free_cap():
    plus = BillingPackage.objects.get(slug="plus")
    user = User.objects.create_user(
        username="creator2",
        email="c2@example.com",
        password="testpass12",
        role=User.Roles.CREATOR,
        billing_package=plus,
    )
    for i in range(2):
        Form.objects.create(owner=user, title=f"Form {i}")

    client = _auth_client(user)
    resp = client.post("/api/forms", {"title": "Third", "description": ""}, format="json")
    assert resp.status_code == 201


@pytest.mark.django_db
def test_app_admin_cannot_patch_billing_package():
    admin = User.objects.create_user(
        username="adm1",
        email="adm1@example.com",
        password="testpass12",
        role=User.Roles.ADMIN,
        is_superuser=False,
    )
    target = User.objects.create_user(
        username="tgt1",
        email="tgt1@example.com",
        password="testpass12",
        role=User.Roles.CREATOR,
    )
    premium = BillingPackage.objects.get(slug="premium")
    client = _auth_client(admin)
    r = client.patch(
        f"/api/users/{target.id}/",
        {"billing_package": premium.pk},
        format="json",
    )
    assert r.status_code == 400
    assert "billing_package" in r.data


@pytest.mark.django_db
def test_superuser_can_patch_billing_package():
    su = User.objects.create_user(
        username="su_bp",
        email="su_bp@example.com",
        password="testpass12",
        role=User.Roles.ADMIN,
        is_superuser=True,
        is_staff=True,
    )
    target = User.objects.create_user(
        username="tgt2",
        email="tgt2@example.com",
        password="testpass12",
        role=User.Roles.CREATOR,
    )
    team = BillingPackage.objects.get(slug="team")
    client = _auth_client(su)
    r = client.patch(
        f"/api/users/{target.id}/",
        {"billing_package": team.pk},
        format="json",
    )
    assert r.status_code == 200
    assert r.data.get("billing_plan") == "team"
    assert r.data.get("billing_package", {}).get("slug") == "team"
    target.refresh_from_db()
    assert target.billing_package_id == team.pk


@pytest.mark.django_db
def test_superuser_can_create_billing_package():
    su = User.objects.create_user(
        username="su_pkg",
        email="su_pkg@example.com",
        password="testpass12",
        role=User.Roles.ADMIN,
        is_superuser=True,
        is_staff=True,
    )
    client = _auth_client(su)
    n = BillingPackage.objects.count()
    r = client.post(
        "/api/billing/packages",
        {
            "slug": "enterprise_test",
            "name": "Enterprise Test",
            "description": "For API test",
            "sort_order": 99,
            "is_active": True,
            "is_free_tier": False,
        },
        format="json",
    )
    assert r.status_code == 201
    assert r.data.get("slug") == "enterprise_test"
    assert BillingPackage.objects.count() == n + 1


@pytest.mark.django_db
def test_app_admin_cannot_create_billing_package():
    admin = User.objects.create_user(
        username="adm_pkg",
        email="adm_pkg@example.com",
        password="testpass12",
        role=User.Roles.ADMIN,
        is_superuser=False,
    )
    client = _auth_client(admin)
    r = client.post(
        "/api/billing/packages",
        {
            "slug": "nope",
            "name": "Nope",
            "description": "",
            "sort_order": 1,
            "is_active": True,
            "is_free_tier": False,
        },
        format="json",
    )
    assert r.status_code == 403


@pytest.mark.django_db
@override_settings(STRIPE_WEBHOOK_SECRET="whsec_test_dummy")
def test_stripe_webhook_rejects_missing_or_invalid_signature():
    client = APIClient()
    r = client.post(
        "/api/billing/stripe-webhook",
        data=b"{}",
        content_type="application/json",
    )
    assert r.status_code == 400

    r2 = client.post(
        "/api/billing/stripe-webhook",
        data=b"{}",
        content_type="application/json",
        HTTP_STRIPE_SIGNATURE="invalid",
    )
    assert r2.status_code == 400


@pytest.mark.django_db
@override_settings(STRIPE_WEBHOOK_SECRET="")
def test_stripe_webhook_503_when_secret_unset():
    client = APIClient()
    r = client.post(
        "/api/billing/stripe-webhook",
        data=b"{}",
        content_type="application/json",
        HTTP_STRIPE_SIGNATURE="t=1,v1=abc",
    )
    assert r.status_code == 503


@pytest.mark.django_db
def test_creator_can_select_self_service_package():
    free = BillingPackage.objects.get(slug="free")
    assert free.allow_self_select is True
    plus = BillingPackage.objects.get(slug="plus")
    user = User.objects.create_user(
        username="sel1",
        email="sel1@example.com",
        password="testpass12",
        role=User.Roles.CREATOR,
        billing_package=plus,
    )
    client = _auth_client(user)
    r = client.post("/api/billing/select-package", {"billing_package_id": free.pk}, format="json")
    assert r.status_code == 200
    assert r.data.get("billing_plan") == "free"
    user.refresh_from_db()
    assert user.billing_package_id == free.pk


@pytest.mark.django_db
def test_select_package_rejects_non_self_selectable():
    team = BillingPackage.objects.get(slug="team")
    team.allow_self_select = False
    team.save(update_fields=["allow_self_select"])
    user = User.objects.create_user(
        username="sel2",
        email="sel2@example.com",
        password="testpass12",
        role=User.Roles.CREATOR,
    )
    client = _auth_client(user)
    r = client.post("/api/billing/select-package", {"billing_package_id": team.pk}, format="json")
    assert r.status_code == 400


@pytest.mark.django_db
def test_select_package_blocked_with_stripe_subscription():
    free = BillingPackage.objects.get(slug="free")
    plus = BillingPackage.objects.get(slug="plus")
    user = User.objects.create_user(
        username="sel3",
        email="sel3@example.com",
        password="testpass12",
        role=User.Roles.CREATOR,
        billing_package=plus,
        stripe_subscription_id="sub_test123",
    )
    client = _auth_client(user)
    r = client.post("/api/billing/select-package", {"billing_package_id": free.pk}, format="json")
    assert r.status_code == 400
    assert "subscription" in str(r.data).lower() or "stripe" in str(r.data).lower()


@pytest.mark.django_db
def test_respondent_cannot_select_package():
    free = BillingPackage.objects.get(slug="free")
    user = User.objects.create_user(
        username="sel4",
        email="sel4@example.com",
        password="testpass12",
        role=User.Roles.RESPONDENT,
    )
    client = _auth_client(user)
    r = client.post("/api/billing/select-package", {"billing_package_id": free.pk}, format="json")
    assert r.status_code == 403


@pytest.mark.django_db
def test_apply_subscription_maps_stripe_price_to_package():
    free = BillingPackage.objects.get(slug="free")
    plus = BillingPackage.objects.get(slug="plus")
    plus.stripe_price_id = "price_test_plus_pkg"
    plus.save(update_fields=["stripe_price_id"])
    user = User.objects.create_user(
        username="submap1",
        email="submap1@example.com",
        password="testpass12",
        role=User.Roles.CREATOR,
        billing_package=free,
    )
    sub = {
        "id": "sub_testmap",
        "status": "active",
        "customer": "cus_testmap",
        "current_period_end": 2_000_000_000,
        "items": {"data": [{"price": {"id": "price_test_plus_pkg"}}]},
    }
    apply_subscription_to_user(user, sub)
    user.refresh_from_db()
    assert user.billing_package_id == plus.pk
    assert user.stripe_subscription_id == "sub_testmap"


@pytest.mark.django_db
@override_settings(STRIPE_PRICE_PRO_MONTHLY="price_legacy_env")
def test_apply_subscription_legacy_price_maps_to_slug_package():
    free = BillingPackage.objects.get(slug="free")
    plus = BillingPackage.objects.get(slug="plus")
    plus.stripe_price_id = None
    plus.save(update_fields=["stripe_price_id"])
    user = User.objects.create_user(
        username="submap2",
        email="submap2@example.com",
        password="testpass12",
        role=User.Roles.CREATOR,
        billing_package=free,
    )
    sub = {
        "id": "sub_legacy",
        "status": "active",
        "customer": "cus_legacy",
        "current_period_end": 2_000_000_000,
        "items": {"data": [{"price": {"id": "price_legacy_env"}}]},
    }
    apply_subscription_to_user(user, sub)
    user.refresh_from_db()
    assert user.billing_package_id == plus.pk


@pytest.mark.django_db
@patch("apps.users.billing_views.stripe.checkout.Session.create")
@override_settings(STRIPE_SECRET_KEY="sk_test_dummy", STRIPE_PRICE_PRO_MONTHLY="")
def test_checkout_uses_package_stripe_price(mock_session):
    mock_session.return_value = MagicMock(url="https://checkout.example/session")
    plus = BillingPackage.objects.get(slug="plus")
    plus.stripe_price_id = "price_checkout_pkg"
    plus.save(update_fields=["stripe_price_id"])
    user = User.objects.create_user(
        username="co1",
        email="co1@example.com",
        password="testpass12",
        role=User.Roles.CREATOR,
    )
    user.stripe_customer_id = "cus_existing_test"
    user.save(update_fields=["stripe_customer_id"])
    client = _auth_client(user)
    r = client.post(
        "/api/billing/checkout",
        {"billing_package_id": plus.pk},
        format="json",
    )
    assert r.status_code == 201
    assert r.data.get("url") == "https://checkout.example/session"
    mock_session.assert_called_once()
    _args, kwargs = mock_session.call_args
    assert kwargs["line_items"][0]["price"] == "price_checkout_pkg"
    assert kwargs["metadata"].get("billing_package_id") == str(plus.pk)


@pytest.mark.django_db
@override_settings(STRIPE_SECRET_KEY="sk_test_dummy", STRIPE_PRICE_PRO_MONTHLY="")
def test_checkout_503_when_no_stripe_price_anywhere():
    BillingPackage.objects.all().update(stripe_price_id=None)
    user = User.objects.create_user(
        username="co2",
        email="co2@example.com",
        password="testpass12",
        role=User.Roles.CREATOR,
    )
    client = _auth_client(user)
    r = client.post("/api/billing/checkout", {}, format="json")
    assert r.status_code == 503


@pytest.mark.django_db
def test_saving_package_as_free_clears_other_free_tiers():
    free = BillingPackage.objects.get(slug="free")
    plus = BillingPackage.objects.get(slug="plus")
    assert free.is_free_tier is True
    plus.is_free_tier = True
    plus.save()
    free.refresh_from_db()
    plus.refresh_from_db()
    assert plus.is_free_tier is True
    assert free.is_free_tier is False
    free.is_free_tier = True
    free.save()
    free.refresh_from_db()
    plus.refresh_from_db()
    assert free.is_free_tier is True
    assert plus.is_free_tier is False


@pytest.mark.django_db
def test_superuser_cannot_create_paid_plan_with_stripe_and_self_select():
    su = User.objects.create_user(
        username="su_combo",
        email="su_combo@example.com",
        password="testpass12",
        role=User.Roles.ADMIN,
        is_superuser=True,
        is_staff=True,
    )
    client = _auth_client(su)
    r = client.post(
        "/api/billing/packages",
        {
            "slug": "bad_self_stripe",
            "name": "Bad combo",
            "description": "",
            "sort_order": 77,
            "is_active": True,
            "is_free_tier": False,
            "allow_self_select": True,
            "stripe_price_id": "price_bad_combo",
        },
        format="json",
    )
    assert r.status_code == 400
    assert "allow_self_select" in r.data


@pytest.mark.django_db
def test_superuser_cannot_create_inactive_package_with_self_select():
    su = User.objects.create_user(
        username="su_inact",
        email="su_inact@example.com",
        password="testpass12",
        role=User.Roles.ADMIN,
        is_superuser=True,
        is_staff=True,
    )
    client = _auth_client(su)
    r = client.post(
        "/api/billing/packages",
        {
            "slug": "inactive_self",
            "name": "Inactive self",
            "description": "",
            "sort_order": 78,
            "is_active": False,
            "is_free_tier": False,
            "allow_self_select": True,
        },
        format="json",
    )
    assert r.status_code == 400
    assert "allow_self_select" in r.data


@pytest.mark.django_db
def test_superuser_cannot_deactivate_free_tier():
    free = BillingPackage.objects.get(slug="free")
    su = User.objects.create_user(
        username="su_nofree",
        email="su_nofree@example.com",
        password="testpass12",
        role=User.Roles.ADMIN,
        is_superuser=True,
        is_staff=True,
    )
    client = _auth_client(su)
    r = client.patch(
        f"/api/billing/packages/{free.pk}/",
        {"is_active": False},
        format="json",
    )
    assert r.status_code == 400
    assert "is_active" in r.data


@pytest.mark.django_db
def test_superuser_rejects_non_stripe_price_id_format():
    su = User.objects.create_user(
        username="su_pricefmt",
        email="su_pricefmt@example.com",
        password="testpass12",
        role=User.Roles.ADMIN,
        is_superuser=True,
        is_staff=True,
    )
    client = _auth_client(su)
    r = client.post(
        "/api/billing/packages",
        {
            "slug": "bad_price_fmt",
            "name": "Bad price",
            "description": "",
            "sort_order": 79,
            "is_active": True,
            "is_free_tier": False,
            "stripe_price_id": "notprice_123",
        },
        format="json",
    )
    assert r.status_code == 400
    assert "stripe_price_id" in r.data
