from django.urls import path

from .api_key_views import UserApiKeyListCreateView, UserApiKeyRevokeView
from .views import MeView, RegisterView

urlpatterns = [
    path("register", RegisterView.as_view(), name="register"),
    path("me", MeView.as_view(), name="me"),
    path("api-keys", UserApiKeyListCreateView.as_view(), name="api-keys-list-create"),
    path("api-keys/<int:pk>", UserApiKeyRevokeView.as_view(), name="api-keys-revoke"),
]
