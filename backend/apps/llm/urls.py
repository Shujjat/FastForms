from django.urls import path

from .views import AiHealthView, SuggestFormView

urlpatterns = [
    path("health", AiHealthView.as_view(), name="ai-health"),
    path("suggest_form", SuggestFormView.as_view(), name="ai-suggest-form"),
]
