"""Versioned HTTP API for integrations (API key auth)."""

from django.db import IntegrityError, transaction
from django.db.models import Prefetch, Q
from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import (
    OpenApiExample,
    OpenApiParameter,
    OpenApiResponse,
    extend_schema,
    extend_schema_view,
)
from rest_framework import generics, permissions, status
from rest_framework.pagination import PageNumberPagination
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.forms.models import Answer, Form, FormCollaborator, Response as FormResponse
from apps.forms.permissions import IsCreatorOrAdmin
from apps.forms.serializers import (
    FormCreateSerializer,
    FormSerializer,
    ResponseSerializer,
    ResponseSubmitSerializer,
)
from apps.forms.tasks import send_new_response_notification_task
from apps.forms.views import _parse_submitted_bound
from apps.users.billing_limits import assert_can_create_owned_form
from apps.users.models import UserApiKey

from .authentication import ApiKeyAuthentication
from .permissions import HasApiKeyScope
from .throttling import ApiKeyRateThrottle


def _forms_queryset_for_user(user):
    return (
        Form.objects.filter(Q(owner=user) | Q(collaborators__user=user) | Q(responses__respondent=user))
        .distinct()
        .select_related("owner")
        .prefetch_related(
            "questions",
            Prefetch(
                "collaborators",
                queryset=FormCollaborator.objects.filter(user=user),
                to_attr="_my_collaborations",
            ),
        )
    )


class V1Pagination(PageNumberPagination):
    page_size = 20
    page_size_query_param = "page_size"
    max_page_size = 100


@extend_schema_view(
    get=extend_schema(
        summary="List forms",
        description=(
            "Returns forms you own, collaborate on, or have previously submitted to. "
            "Requires scope **forms:read**."
        ),
        tags=["Public API v1"],
    ),
    post=extend_schema(
        summary="Create form",
        description="Requires scope **forms:write** and a creator or admin user account.",
        tags=["Public API v1"],
        request=FormCreateSerializer,
        responses={201: FormSerializer},
    ),
)
class V1FormListCreateView(generics.ListCreateAPIView):
    authentication_classes = [ApiKeyAuthentication]
    throttle_classes = [ApiKeyRateThrottle]
    pagination_class = V1Pagination

    def get_permissions(self):
        if self.request.method == "POST":
            return [HasApiKeyScope(), IsCreatorOrAdmin()]
        return [HasApiKeyScope()]

    def get_required_scopes(self, request):
        if request.method == "POST":
            return (UserApiKey.SCOPE_FORMS_WRITE,)
        return (UserApiKey.SCOPE_FORMS_READ,)

    def get_queryset(self):
        return _forms_queryset_for_user(self.request.user)

    def get_serializer_class(self):
        if self.request.method == "POST":
            return FormCreateSerializer
        return FormSerializer

    def perform_create(self, serializer):
        assert_can_create_owned_form(self.request.user)
        serializer.save(owner=self.request.user)


@extend_schema_view(
    get=extend_schema(
        summary="Get form",
        description="Form definition including questions. Requires **forms:read**.",
        tags=["Public API v1"],
    ),
)
class V1FormDetailView(generics.RetrieveAPIView):
    authentication_classes = [ApiKeyAuthentication]
    permission_classes = [HasApiKeyScope]
    throttle_classes = [ApiKeyRateThrottle]
    required_scopes = (UserApiKey.SCOPE_FORMS_READ,)
    serializer_class = FormSerializer
    lookup_field = "pk"

    def get_queryset(self):
        return _forms_queryset_for_user(self.request.user)


@extend_schema(
    summary="Submit responses",
    description=(
        "Create one submission for the form. The authenticated API key's user is stored as the respondent. "
        "Requires **responses:submit**. Same validation rules as the browser app."
    ),
    tags=["Public API v1"],
    request=ResponseSubmitSerializer,
    responses={
        201: OpenApiResponse(
            response={
                "type": "object",
                "properties": {
                    "status": {"type": "string"},
                    "response_id": {"type": "integer"},
                },
            },
            examples=[
                OpenApiExample("Created", value={"status": "submitted", "response_id": 42}),
            ],
        ),
        409: OpenApiResponse(description="Duplicate response when form enforces one per user."),
    },
)
class V1FormSubmitView(APIView):
    authentication_classes = [ApiKeyAuthentication]
    permission_classes = [HasApiKeyScope]
    throttle_classes = [ApiKeyRateThrottle]
    required_scopes = (UserApiKey.SCOPE_RESPONSES_SUBMIT,)

    def post(self, request, form_id):
        try:
            form = Form.objects.prefetch_related("questions").get(id=form_id)
        except Form.DoesNotExist:
            return Response({"detail": "Form not found."}, status=status.HTTP_404_NOT_FOUND)

        serializer = ResponseSubmitSerializer(data=request.data, context={"form": form})
        serializer.is_valid(raise_exception=True)
        respondent = request.user

        try:
            with transaction.atomic():
                form_response = FormResponse.objects.create(form=form, respondent=respondent)
                answers = serializer.validated_data["answers"]
                question_ids = {str(q.id): q for q in form.questions.all()}
                for qid, value in answers.items():
                    question = question_ids.get(str(qid))
                    if question:
                        Answer.objects.create(response=form_response, question=question, value=value)
        except IntegrityError:
            return Response(
                {"detail": "Duplicate response is not allowed for this form."},
                status=status.HTTP_409_CONFLICT,
            )

        send_new_response_notification_task.delay(form.owner.email, form.title, form_response.id)

        return Response(
            {"status": "submitted", "response_id": form_response.id},
            status=status.HTTP_201_CREATED,
        )


@extend_schema(
    summary="List responses",
    description=(
        "List submitted responses for a form **you own**. Supports optional filters "
        "`search`, `submitted_after`, `submitted_before`, `respondent_id`. Requires **responses:read**."
    ),
    tags=["Public API v1"],
    parameters=[
        OpenApiParameter("search", OpenApiTypes.STR, OpenApiParameter.QUERY, required=False),
        OpenApiParameter("submitted_after", OpenApiTypes.STR, OpenApiParameter.QUERY, required=False),
        OpenApiParameter("submitted_before", OpenApiTypes.STR, OpenApiParameter.QUERY, required=False),
        OpenApiParameter("respondent_id", OpenApiTypes.INT, OpenApiParameter.QUERY, required=False),
    ],
)
class V1FormResponsesListView(generics.ListAPIView):
    authentication_classes = [ApiKeyAuthentication]
    permission_classes = [HasApiKeyScope]
    throttle_classes = [ApiKeyRateThrottle]
    required_scopes = (UserApiKey.SCOPE_RESPONSES_READ,)
    serializer_class = ResponseSerializer
    pagination_class = V1Pagination

    def get_queryset(self):
        form_id = self.kwargs["form_id"]
        user = self.request.user
        qs = FormResponse.objects.filter(form_id=form_id, form__owner=user).prefetch_related(
            "answers", "answers__question"
        )
        rid = self.request.query_params.get("respondent_id")
        if rid:
            qs = qs.filter(respondent_id=rid)
        sa = _parse_submitted_bound(self.request.query_params.get("submitted_after"), end_of_day=False)
        if sa:
            qs = qs.filter(submitted_at__gte=sa)
        sb = _parse_submitted_bound(self.request.query_params.get("submitted_before"), end_of_day=True)
        if sb:
            qs = qs.filter(submitted_at__lte=sb)
        search = (self.request.query_params.get("search") or "").strip()
        if search:
            qs = qs.filter(answers__value__icontains=search).distinct()
        return qs.order_by("-submitted_at")

    def list(self, request, *args, **kwargs):
        if not Form.objects.filter(id=kwargs["form_id"], owner=request.user).exists():
            return Response({"detail": "Form not found."}, status=status.HTTP_404_NOT_FOUND)
        return super().list(request, *args, **kwargs)
