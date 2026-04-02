import pytest
from django.contrib.auth import get_user_model
from django.test import override_settings
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import RefreshToken

from apps.forms.models import Form

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
    for i in range(2):
        Form.objects.create(owner=user, title=f"Form {i}")

    client = _auth_client(user)
    resp = client.post("/api/forms", {"title": "Over limit", "description": ""}, format="json")
    assert resp.status_code == 400
    assert "free" in str(resp.data).lower() or "upgrade" in str(resp.data).lower()


@pytest.mark.django_db
@override_settings(FREE_TIER_MAX_FORMS=2)
def test_pro_plan_allows_form_create_past_free_cap():
    user = User.objects.create_user(
        username="creator2",
        email="c2@example.com",
        password="testpass12",
        role=User.Roles.CREATOR,
        billing_plan=User.BillingPlan.PRO,
    )
    for i in range(2):
        Form.objects.create(owner=user, title=f"Form {i}")

    client = _auth_client(user)
    resp = client.post("/api/forms", {"title": "Third", "description": ""}, format="json")
    assert resp.status_code == 201


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
