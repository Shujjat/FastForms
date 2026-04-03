from django.conf import settings
from django.contrib import admin
from django.urls import include, path
from drf_spectacular.views import SpectacularAPIView, SpectacularRedocView, SpectacularSwaggerView

from apps.users.auth_views import PasswordResetConfirmView, PasswordResetRequestView
from apps.users.google_views import GoogleAuthView
from apps.users.jwt_views import ThrottledTokenObtainPairView, ThrottledTokenRefreshView

urlpatterns = [
    path("admin/", admin.site.urls),
    path("api/auth/login", ThrottledTokenObtainPairView.as_view(), name="token_obtain_pair"),
    path("api/auth/token/refresh", ThrottledTokenRefreshView.as_view(), name="token_refresh"),
    path("api/auth/google", GoogleAuthView.as_view(), name="auth_google"),
    path("api/auth/password-reset", PasswordResetRequestView.as_view(), name="password_reset_request"),
    path("api/auth/password-reset/confirm", PasswordResetConfirmView.as_view(), name="password_reset_confirm"),
    path("api/auth/", include("apps.users.urls")),
    path("api/users/", include("apps.users.management_urls")),
    path("api/ai/", include("apps.llm.urls")),
    path("api/billing/", include("apps.users.billing_urls")),
    path("api/v1/", include("apps.public_api.urls")),
    path("api/", include("apps.forms.urls")),
]

if getattr(settings, "ENABLE_API_DOCS", True):
    urlpatterns += [
        path("api/schema/", SpectacularAPIView.as_view(), name="schema"),
        path("api/docs/swagger/", SpectacularSwaggerView.as_view(url_name="schema"), name="swagger-ui"),
        path("api/docs/redoc/", SpectacularRedocView.as_view(url_name="schema"), name="redoc"),
    ]
