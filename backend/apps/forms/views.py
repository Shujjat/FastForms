import csv
import logging

from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.mail import send_mail
from django.db import IntegrityError, transaction
from django.db.models import Max, Prefetch, Q
from django.http import HttpResponse
from django.utils import timezone
from django.utils.dateparse import parse_datetime
from rest_framework import permissions, status, viewsets
from rest_framework.decorators import action, api_view, permission_classes, throttle_classes
from rest_framework.exceptions import ValidationError
from rest_framework.response import Response

from .models import Answer, Form, FormCollaborator, Question, Response as FormResponse
from .permissions import CanEditForm, IsCreatorOrAdmin, IsOwnerOrReadOnly
from .serializers import (
    CollaboratorCreateSerializer,
    CollaboratorSerializer,
    FormCreateSerializer,
    FormSerializer,
    InviteEmailsSerializer,
    QuestionSerializer,
    ResponseSerializer,
    ResponseSubmitSerializer,
)
from .tasks import send_new_response_notification_task
from .template_loader import get_template, list_template_summaries
from apps.llm.client import is_llm_configured
from apps.llm.views import AiUserThrottle
from apps.users.avatar import gravatar_url
from apps.users.billing_limits import assert_can_create_owned_form
from apps.users.package_usage import assert_ai_credits_available, consume_ai_credits

from .response_ai import generate_and_save_form_responses_summary, generate_and_save_response_narration

logger = logging.getLogger(__name__)


class FormViewSet(viewsets.ModelViewSet):
    queryset = Form.objects.all().select_related("owner").prefetch_related("questions")
    permission_classes = [permissions.IsAuthenticatedOrReadOnly, IsOwnerOrReadOnly]

    def get_queryset(self):
        user = self.request.user
        if user.is_authenticated:
            # Only forms this user owns, collaborates on, or has submitted to (not every public form).
            qs = self.queryset.filter(
                Q(owner=user) | Q(collaborators__user=user) | Q(responses__respondent=user)
            ).distinct()
            return qs.select_related("owner").prefetch_related(
                "questions",
                Prefetch(
                    "collaborators",
                    queryset=FormCollaborator.objects.filter(user=user),
                    to_attr="_my_collaborations",
                ),
            )
        return self.queryset.filter(status=Form.Status.PUBLISHED, visibility=Form.Visibility.PUBLIC)

    def get_serializer_class(self):
        if self.action in {"create", "update", "partial_update"}:
            return FormCreateSerializer
        return FormSerializer

    def get_permissions(self):
        if self.action in {"create"}:
            return [permissions.IsAuthenticated(), IsCreatorOrAdmin()]
        if self.action in {
            "update",
            "partial_update",
            "destroy",
            "publish",
            "questions",
            "reorder_questions",
            "clear_responses",
            "invite",
            "duplicate",
            "collaborator_search",
            "collaborator_candidates",
        }:
            return [permissions.IsAuthenticated(), CanEditForm()]
        return [permissions.IsAuthenticated(), IsOwnerOrReadOnly()]

    def perform_create(self, serializer):
        assert_can_create_owned_form(self.request.user)
        serializer.save(owner=self.request.user)

    @action(detail=True, methods=["post"], permission_classes=[permissions.IsAuthenticated, CanEditForm])
    def duplicate(self, request, pk=None):
        source = self.get_object()
        assert_can_create_owned_form(request.user)
        with transaction.atomic():
            new_form = Form.objects.create(
                owner=request.user,
                title=f"{source.title} (copy)",
                description=source.description,
                thank_you_message=source.thank_you_message or "",
                appearance=dict(source.appearance) if source.appearance else {},
                fill_mode=source.fill_mode,
                visibility=source.visibility,
                status=Form.Status.DRAFT,
                one_response_per_user=source.one_response_per_user,
                opens_at=source.opens_at,
                closes_at=source.closes_at,
            )
            for q in source.questions.order_by("order_index", "id"):
                Question.objects.create(
                    form=new_form,
                    order_index=q.order_index,
                    question_type=q.question_type,
                    text=q.text,
                    required=q.required,
                    disabled=q.disabled,
                    options=list(q.options) if q.options else [],
                    validation=dict(q.validation) if q.validation else {},
                )
        new_form = (
            Form.objects.select_related("owner")
            .prefetch_related("questions")
            .get(pk=new_form.pk)
        )
        return Response(
            FormSerializer(new_form, context={"request": request}).data,
            status=status.HTTP_201_CREATED,
        )

    @action(detail=True, methods=["post"], permission_classes=[permissions.IsAuthenticated, CanEditForm])
    def publish(self, request, pk=None):
        form = self.get_object()
        form.status = Form.Status.PUBLISHED
        form.save(update_fields=["status", "updated_at"])
        return Response({"status": "published"})

    @action(detail=True, methods=["post"], permission_classes=[permissions.IsAuthenticated, CanEditForm])
    def questions(self, request, pk=None):
        form = self.get_object()
        serializer = QuestionSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        # Assign order index server-side to avoid client-side race issues.
        next_index = (form.questions.aggregate(max_idx=Max("order_index")).get("max_idx") or -1) + 1
        serializer.save(form=form, order_index=next_index)
        return Response(serializer.data, status=status.HTTP_201_CREATED)

    @action(detail=True, methods=["put"], permission_classes=[permissions.IsAuthenticated, CanEditForm])
    def reorder_questions(self, request, pk=None):
        form = self.get_object()
        order = request.data.get("question_ids", [])
        question_map = {str(q.id): q for q in form.questions.all()}
        for idx, qid in enumerate(order):
            q = question_map.get(str(qid))
            if q:
                q.order_index = idx
                q.save(update_fields=["order_index"])
        return Response({"status": "reordered"})

    @action(detail=True, methods=["post"], url_path="responses/clear", permission_classes=[permissions.IsAuthenticated, CanEditForm])
    def clear_responses(self, request, pk=None):
        """Delete all submitted responses (and answers) for this form; keep form and questions."""
        form = self.get_object()
        qs = FormResponse.objects.filter(form=form)
        n = qs.count()
        qs.delete()
        form.responses_ai_summary = ""
        form.responses_ai_summary_generated_at = None
        form.save(update_fields=["responses_ai_summary", "responses_ai_summary_generated_at"])
        logger.info(
            "forms_clear_responses user_id=%s form_id=%s deleted_count=%s",
            getattr(request.user, "id", None),
            form.id,
            n,
        )
        return Response({"deleted_count": n}, status=status.HTTP_200_OK)

    @action(detail=True, methods=["get"], permission_classes=[permissions.IsAuthenticated, IsOwnerOrReadOnly])
    def collaborators(self, request, pk=None):
        form = self.get_object()
        rows = FormCollaborator.objects.filter(form=form).select_related("user")
        return Response(CollaboratorSerializer(rows, many=True).data)

    @collaborators.mapping.post
    def add_collaborator(self, request, pk=None):
        form = self.get_object()
        if form.owner_id != request.user.id:
            return Response({"detail": "Only owner can add collaborators."}, status=status.HTTP_403_FORBIDDEN)

        serializer = CollaboratorCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        target = serializer.validated_data["target_user"]
        role = serializer.validated_data["role"]
        row, _ = FormCollaborator.objects.update_or_create(form=form, user=target, defaults={"role": role})
        return Response(CollaboratorSerializer(row).data, status=status.HTTP_201_CREATED)

    @action(detail=True, methods=["get"], permission_classes=[permissions.IsAuthenticated, CanEditForm])
    def collaborator_search(self, request, pk=None):
        form = self.get_object()
        if form.owner_id != request.user.id:
            return Response(
                {"detail": "Only the form owner can search users."},
                status=status.HTTP_403_FORBIDDEN,
            )
        User = get_user_model()
        raw = (request.query_params.get("q") or "").strip()
        if len(raw) < 2:
            return Response({"results": []})
        existing = set(FormCollaborator.objects.filter(form=form).values_list("user_id", flat=True))
        existing.add(form.owner_id)
        qs = (
            User.objects.filter(
                Q(username__icontains=raw)
                | Q(email__icontains=raw)
                | Q(first_name__icontains=raw)
                | Q(last_name__icontains=raw)
            )
            .exclude(id__in=existing)
            .distinct()[:25]
        )
        results = []
        for u in qs:
            results.append(
                {
                    "id": u.id,
                    "username": u.username,
                    "email": u.email or "",
                    "first_name": u.first_name or "",
                    "last_name": u.last_name or "",
                    "display_name": (u.get_full_name() or u.username or "").strip(),
                    "avatar_url": gravatar_url(u.email or ""),
                }
            )
        return Response({"results": results})

    @action(detail=True, methods=["get"], permission_classes=[permissions.IsAuthenticated, CanEditForm])
    def collaborator_candidates(self, request, pk=None):
        """
        List all users who can be added as collaborators (excluding owner and existing collaborators).
        Owner only; capped for performance.
        """
        form = self.get_object()
        if form.owner_id != request.user.id:
            return Response(
                {"detail": "Only the form owner can list users."},
                status=status.HTTP_403_FORBIDDEN,
            )
        User = get_user_model()
        existing = set(FormCollaborator.objects.filter(form=form).values_list("user_id", flat=True))
        existing.add(form.owner_id)
        qs = User.objects.exclude(id__in=existing).order_by("username", "id")[:200]
        results = []
        for u in qs:
            results.append(
                {
                    "id": u.id,
                    "username": u.username,
                    "email": u.email or "",
                    "first_name": u.first_name or "",
                    "last_name": u.last_name or "",
                    "display_name": (u.get_full_name() or u.username or "").strip(),
                    "avatar_url": gravatar_url(u.email or ""),
                }
            )
        return Response({"results": results})

    @action(detail=True, methods=["post"], permission_classes=[permissions.IsAuthenticated, CanEditForm])
    def invite(self, request, pk=None):
        form = self.get_object()
        if form.status != Form.Status.PUBLISHED:
            return Response(
                {"detail": "Publish the form before sending email invitations."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        serializer = InviteEmailsSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        emails = serializer.validated_data["emails"]
        note = (serializer.validated_data.get("message") or "").strip()

        base = getattr(settings, "FRONTEND_BASE_URL", "http://localhost:5173").rstrip("/")
        fill_url = f"{base}/fill/{form.id}"
        inviter = request.user.get_full_name() or request.user.username
        subject = f'Invitation: "{form.title}"'
        body_parts = [
            f"Hello,",
            "",
            f'{inviter} invited you to complete the form "{form.title}".',
        ]
        if form.description:
            body_parts.extend(["", form.description[:500] + ("..." if len(form.description) > 500 else "")])
        if note:
            body_parts.extend(["", "Message from the organizer:", note])
        body_parts.extend(
            [
                "",
                f"Open the form: {fill_url}",
                "",
                "If the form is private, sign in to your FastForms account before opening the link.",
                "",
                "If you did not expect this message, you can ignore it.",
            ]
        )
        body = "\n".join(body_parts)

        sent = 0
        errors = []
        from_addr = settings.DEFAULT_FROM_EMAIL
        for email in emails:
            try:
                send_mail(subject, body, from_addr, [email], fail_silently=False)
                sent += 1
            except Exception as exc:
                errors.append({"email": email, "error": str(exc)})

        return Response(
            {
                "sent": sent,
                "total": len(emails),
                "failed": len(errors),
                "errors": errors[:10],
            },
            status=status.HTTP_200_OK,
        )


@api_view(["PUT", "DELETE"])
@permission_classes([permissions.IsAuthenticated])
def update_or_delete_question(request, question_id):
    try:
        question = Question.objects.select_related("form").get(id=question_id)
    except Question.DoesNotExist:
        return Response({"detail": "Question not found."}, status=status.HTTP_404_NOT_FOUND)

    form = question.form
    user = request.user
    if user.role not in {"creator", "admin"}:
        return Response({"detail": "Permission denied."}, status=status.HTTP_403_FORBIDDEN)
    is_owner = form.owner_id == user.id
    is_editor = FormCollaborator.objects.filter(form=form, user=user, role="editor").exists()
    if not is_owner and not is_editor:
        return Response({"detail": "Permission denied."}, status=status.HTTP_403_FORBIDDEN)

    if request.method == "DELETE":
        question.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)

    serializer = QuestionSerializer(question, data=request.data, partial=True)
    serializer.is_valid(raise_exception=True)
    serializer.save()
    return Response(serializer.data)


@api_view(["POST"])
@permission_classes([permissions.IsAuthenticated])
def submit_response(request, form_id):
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
        return Response({"detail": "Duplicate response is not allowed for this form."}, status=status.HTTP_409_CONFLICT)

    send_new_response_notification_task.delay(form.owner.email, form.title, form_response.id)

    return Response({"status": "submitted", "response_id": form_response.id}, status=status.HTTP_201_CREATED)


def _parse_submitted_bound(value, *, end_of_day=False):
    """Parse query param as datetime (ISO) or date-only (YYYY-MM-DD)."""
    if not value:
        return None
    dt = parse_datetime(value.strip())
    if dt:
        if timezone.is_naive(dt):
            dt = timezone.make_aware(dt)
        return dt
    from django.utils.dateparse import parse_date
    from datetime import datetime as dt_mod, time as time_mod

    d = parse_date(value.strip())
    if not d:
        return None
    if end_of_day:
        naive = dt_mod.combine(d, time_mod(23, 59, 59, 999999))
    else:
        naive = dt_mod.combine(d, time_mod.min)
    return timezone.make_aware(naive)


@api_view(["GET"])
@permission_classes([permissions.IsAuthenticated])
def list_responses(request, form_id):
    qs = FormResponse.objects.filter(form_id=form_id, form__owner=request.user).prefetch_related(
        "answers", "answers__question"
    )

    rid = request.query_params.get("respondent_id")
    if rid:
        qs = qs.filter(respondent_id=rid)

    sa = _parse_submitted_bound(request.query_params.get("submitted_after"), end_of_day=False)
    if sa:
        qs = qs.filter(submitted_at__gte=sa)

    sb = _parse_submitted_bound(request.query_params.get("submitted_before"), end_of_day=True)
    if sb:
        qs = qs.filter(submitted_at__lte=sb)

    search = (request.query_params.get("search") or "").strip()
    if search:
        qs = qs.filter(answers__value__icontains=search).distinct()

    responses = qs.order_by("-submitted_at")
    return Response(ResponseSerializer(responses, many=True).data)


@api_view(["GET"])
@permission_classes([permissions.IsAuthenticated])
def analytics(request, form_id):
    form = Form.objects.filter(id=form_id, owner=request.user).first()
    if not form:
        return Response({"detail": "Form not found."}, status=status.HTTP_404_NOT_FOUND)

    questions = list(Question.objects.filter(form=form).order_by("order_index", "id"))
    responses = list(
        FormResponse.objects.filter(form=form).prefetch_related("answers", "answers__question").order_by("-submitted_at")
    )
    total_responses = len(responses)

    answer_map = {}
    for response in responses:
        for answer in response.answers.all():
            answer_map.setdefault(answer.question_id, []).append(answer.value)

    question_stats = []
    for q in questions:
        values = answer_map.get(q.id, [])
        entry = {
            "id": q.id,
            "text": q.text,
            "question_type": q.question_type,
            "answer_count": len(values),
            "required": q.required,
        }

        entry["options"] = list(q.options) if q.options else []

        if q.question_type in {"single_choice", "dropdown"}:
            counts = {}
            for v in values:
                key = str(v)
                counts[key] = counts.get(key, 0) + 1
            entry["choice_counts"] = counts
        elif q.question_type == "multi_choice":
            counts = {}
            for v in values:
                if isinstance(v, list):
                    for item in v:
                        key = str(item)
                        counts[key] = counts.get(key, 0) + 1
                else:
                    key = str(v)
                    counts[key] = counts.get(key, 0) + 1
            entry["choice_counts"] = counts
        elif q.question_type == "rating":
            numbers = []
            for v in values:
                try:
                    numbers.append(float(v))
                except (TypeError, ValueError):
                    continue
            entry["average"] = round(sum(numbers) / len(numbers), 2) if numbers else 0

        question_stats.append(entry)

    return Response(
        {
            "form_id": form.id,
            "form_title": form.title,
            "total_responses": total_responses,
            "questions": question_stats,
            "latest_submitted_at": responses[0].submitted_at if responses else None,
            "responses_ai_summary": form.responses_ai_summary or "",
            "responses_ai_summary_generated_at": form.responses_ai_summary_generated_at,
        }
    )


@api_view(["GET"])
@permission_classes([permissions.IsAuthenticated])
def export_responses(request, form_id):
    export_format = request.query_params.get("export_format", request.query_params.get("format", "csv")).lower()
    responses = FormResponse.objects.filter(form_id=form_id, form__owner=request.user).prefetch_related(
        "answers", "answers__question"
    )
    logger.info(
        "export_responses user_id=%s form_id=%s format=%s response_count=%s",
        getattr(request.user, "id", None),
        form_id,
        export_format,
        responses.count(),
    )
    if export_format == "json":
        return Response(ResponseSerializer(responses, many=True).data)

    if export_format != "csv":
        return Response({"detail": "Unsupported format. Use csv or json."}, status=status.HTTP_400_BAD_REQUEST)

    questions = list(Question.objects.filter(form_id=form_id).order_by("order_index", "id"))
    columns = [f"Q{idx + 1}: {q.text}" for idx, q in enumerate(questions)]

    response = HttpResponse(content_type="text/csv")
    response["Content-Disposition"] = f'attachment; filename="form_{form_id}_responses.csv"'
    writer = csv.writer(response)
    writer.writerow(["response_id", "submitted_at", "respondent_id", *columns])

    for item in responses:
        answer_lookup = {}
        for ans in item.answers.all():
            val = ans.value
            if isinstance(val, list):
                val = " | ".join(str(x) for x in val)
            answer_lookup[ans.question_id] = str(val)
        row = [item.id, item.submitted_at.isoformat(), item.respondent_id or ""]
        row.extend(answer_lookup.get(q.id, "") for q in questions)
        writer.writerow(row)

    return response


def _create_form_from_template_payload(user, payload: dict) -> Form:
    valid_types = {c.value for c in Question.Types}
    questions_raw = payload.get("questions") or []
    if not questions_raw:
        raise ValidationError({"questions": "Template must include at least one question."})
    appearance = payload.get("appearance")
    if appearance is not None and not isinstance(appearance, dict):
        appearance = {}
    elif appearance is None:
        appearance = {}
    fill_mode = payload.get("fill_mode") or Form.FillMode.ALL_AT_ONCE
    if fill_mode not in {Form.FillMode.ALL_AT_ONCE, Form.FillMode.WIZARD}:
        fill_mode = Form.FillMode.ALL_AT_ONCE
    with transaction.atomic():
        form = Form.objects.create(
            owner=user,
            title=(payload.get("title") or "Untitled")[:255],
            description=payload.get("description") or "",
            thank_you_message=payload.get("thank_you_message") or "",
            appearance=appearance,
            fill_mode=fill_mode,
            status=Form.Status.DRAFT,
            visibility=Form.Visibility.PUBLIC,
        )
        for idx, q in enumerate(questions_raw):
            qt = q.get("question_type")
            if qt not in valid_types:
                raise ValidationError({"questions": f"Invalid question_type: {qt!r}."})
            Question.objects.create(
                form=form,
                order_index=idx,
                question_type=qt,
                text=(q.get("text") or "Question")[:500],
                required=bool(q.get("required", False)),
                disabled=bool(q.get("disabled", False)),
                options=list(q.get("options") or []),
                validation=dict(q.get("validation") or {}),
            )
    return Form.objects.prefetch_related("questions").get(pk=form.pk)


@api_view(["GET"])
@permission_classes([permissions.AllowAny])
def list_form_templates(request):
    return Response(list_template_summaries())


@api_view(["POST"])
@permission_classes([permissions.IsAuthenticated, IsCreatorOrAdmin])
def create_form_from_template(request):
    tid = (request.data or {}).get("template_id")
    if not tid:
        return Response({"detail": "template_id is required."}, status=status.HTTP_400_BAD_REQUEST)
    try:
        assert_can_create_owned_form(request.user)
    except ValidationError as e:
        return Response(e.detail, status=status.HTTP_400_BAD_REQUEST)
    payload = get_template(str(tid))
    if not payload:
        return Response({"detail": "Unknown template."}, status=status.HTTP_404_NOT_FOUND)
    try:
        form = _create_form_from_template_payload(request.user, payload)
    except ValidationError as e:
        return Response(e.detail, status=status.HTTP_400_BAD_REQUEST)
    return Response(FormSerializer(form, context={"request": request}).data, status=status.HTTP_201_CREATED)


def _form_owned_by_user(user, form_id):
    return Form.objects.filter(id=form_id, owner=user).first()


@api_view(["GET"])
@permission_classes([permissions.IsAuthenticated])
def visualization_matrix(request, form_id):
    """
    Full question metadata and all responses with answers for charts and regression (owner only).
    """
    form = _form_owned_by_user(request.user, form_id)
    if not form:
        return Response({"detail": "Form not found."}, status=status.HTTP_404_NOT_FOUND)
    questions = list(Question.objects.filter(form=form).order_by("order_index", "id"))
    questions_meta = [
        {
            "id": q.id,
            "text": q.text,
            "question_type": q.question_type,
            "options": list(q.options) if q.options else [],
        }
        for q in questions
    ]
    responses = (
        FormResponse.objects.filter(form=form)
        .prefetch_related("answers")
        .order_by("-submitted_at")
    )
    rows = []
    for r in responses:
        rows.append(
            {
                "id": r.id,
                "submitted_at": r.submitted_at.isoformat(),
                "answers": [
                    {"question_id": a.question_id, "value": a.value} for a in r.answers.all()
                ],
            }
        )
    return Response({"questions": questions_meta, "responses": rows})


@api_view(["POST"])
@permission_classes([permissions.IsAuthenticated])
@throttle_classes([AiUserThrottle])
def generate_response_ai_narration(request, form_id, response_id):
    """Generate (or regenerate) an AI narration for one response; requires Ollama."""
    form = _form_owned_by_user(request.user, form_id)
    if not form:
        return Response({"detail": "Form not found."}, status=status.HTTP_404_NOT_FOUND)
    resp = (
        FormResponse.objects.filter(pk=response_id, form=form)
        .prefetch_related("answers", "answers__question")
        .first()
    )
    if not resp:
        return Response({"detail": "Response not found."}, status=status.HTTP_404_NOT_FOUND)
    if not is_llm_configured():
        return Response(
            {
                "detail": "AI is not configured. Set LLM_PROVIDER=ollama and OLLAMA_BASE_URL (see backend .env.example)."
            },
            status=status.HTTP_503_SERVICE_UNAVAILABLE,
        )
    try:
        assert_ai_credits_available(request.user)
    except ValidationError as e:
        return Response(e.detail, status=status.HTTP_400_BAD_REQUEST)
    try:
        text = generate_and_save_response_narration(form, resp)
    except RuntimeError as e:
        logger.warning(
            "generate_response_ai_narration failed form_id=%s response_id=%s: %s",
            form_id,
            response_id,
            e,
        )
        return Response({"detail": str(e)}, status=status.HTTP_502_BAD_GATEWAY)
    consume_ai_credits(request.user)
    return Response(
        ResponseSerializer(resp).data,
        status=status.HTTP_200_OK,
    )


@api_view(["POST"])
@permission_classes([permissions.IsAuthenticated])
@throttle_classes([AiUserThrottle])
def generate_form_ai_responses_summary(request, form_id):
    """Generate (or regenerate) an AI summary across all responses on the form."""
    form = _form_owned_by_user(request.user, form_id)
    if not form:
        return Response({"detail": "Form not found."}, status=status.HTTP_404_NOT_FOUND)
    if not is_llm_configured():
        return Response(
            {
                "detail": "AI is not configured. Set LLM_PROVIDER=ollama and OLLAMA_BASE_URL (see backend .env.example)."
            },
            status=status.HTTP_503_SERVICE_UNAVAILABLE,
        )
    responses = list(
        FormResponse.objects.filter(form=form)
        .prefetch_related("answers", "answers__question")
        .order_by("submitted_at")
    )
    if not responses:
        return Response({"detail": "No responses to summarize."}, status=status.HTTP_400_BAD_REQUEST)
    try:
        assert_ai_credits_available(request.user)
    except ValidationError as e:
        return Response(e.detail, status=status.HTTP_400_BAD_REQUEST)
    try:
        generate_and_save_form_responses_summary(form, responses)
    except RuntimeError as e:
        logger.warning("generate_form_ai_responses_summary failed form_id=%s: %s", form_id, e)
        return Response({"detail": str(e)}, status=status.HTTP_502_BAD_GATEWAY)
    consume_ai_credits(request.user)
    form = Form.objects.get(pk=form.pk)
    return Response(
        {
            "responses_ai_summary": form.responses_ai_summary,
            "responses_ai_summary_generated_at": form.responses_ai_summary_generated_at,
        },
        status=status.HTTP_200_OK,
    )
