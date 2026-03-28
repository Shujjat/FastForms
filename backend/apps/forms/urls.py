from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views import FormViewSet, analytics, export_responses, list_responses, submit_response, update_or_delete_question

router = DefaultRouter(trailing_slash=False)
router.register("forms", FormViewSet, basename="forms")

urlpatterns = [
    path("", include(router.urls)),
    path("forms/<int:form_id>/submit", submit_response, name="submit-response"),
    path("forms/<int:form_id>/responses", list_responses, name="list-responses"),
    path("forms/<int:form_id>/analytics", analytics, name="analytics"),
    path("forms/<int:form_id>/export", export_responses, name="export-responses"),
    path("questions/<int:question_id>", update_or_delete_question, name="question-detail"),
]
