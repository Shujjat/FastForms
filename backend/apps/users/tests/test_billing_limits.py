import pytest
from django.contrib.auth import get_user_model
from django.test import override_settings
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import RefreshToken

from apps.forms.models import Form
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
