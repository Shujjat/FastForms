from django.urls import path

from .admin_views import UserManagementDetailView, UserManagementListCreateView

urlpatterns = [
    path("", UserManagementListCreateView.as_view(), name="user-management-list"),
    path("<int:pk>/", UserManagementDetailView.as_view(), name="user-management-detail"),
]
