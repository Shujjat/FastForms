from django.urls import path

from .views import (
    V1FormDetailView,
    V1FormListCreateView,
    V1FormResponsesListView,
    V1FormSubmitView,
)

urlpatterns = [
    path("forms", V1FormListCreateView.as_view(), name="v1-form-list"),
    path("forms/<int:pk>", V1FormDetailView.as_view(), name="v1-form-detail"),
    path("forms/<int:form_id>/submit", V1FormSubmitView.as_view(), name="v1-form-submit"),
    path("forms/<int:form_id>/responses", V1FormResponsesListView.as_view(), name="v1-form-responses"),
]
