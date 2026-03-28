import re
from datetime import datetime

from django.utils import timezone
from rest_framework import serializers

from apps.users.models import User

from .models import Answer, Form, FormCollaborator, Question, Response

_ALLOWED_VALIDATION_KEYS = frozenset(
    {"min_length", "max_length", "min", "max", "pattern", "min_date", "max_date"}
)


class QuestionSerializer(serializers.ModelSerializer):
    class Meta:
        model = Question
        fields = ("id", "order_index", "question_type", "text", "required", "options", "validation")

    def validate_validation(self, value):
        if not isinstance(value, dict):
            raise serializers.ValidationError("validation must be an object.")
        extra = set(value.keys()) - _ALLOWED_VALIDATION_KEYS
        if extra:
            raise serializers.ValidationError(f"Unknown validation keys: {', '.join(sorted(extra))}")
        return value


class FormSerializer(serializers.ModelSerializer):
    questions = QuestionSerializer(many=True, read_only=True)

    class Meta:
        model = Form
        fields = (
            "id",
            "title",
            "description",
            "status",
            "visibility",
            "one_response_per_user",
            "opens_at",
            "closes_at",
            "created_at",
            "updated_at",
            "questions",
        )
        read_only_fields = ("created_at", "updated_at")


class FormCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model = Form
        fields = ("id", "title", "description", "visibility", "one_response_per_user", "opens_at", "closes_at")


def _validate_answer_against_rules(question: Question, raw_value):
    """Apply optional Question.validation rules (ExecutionPlan PR3)."""
    rules = question.validation or {}
    if not rules:
        return
    qt = question.question_type
    qid = question.id

    if qt in (Question.Types.SHORT_TEXT, Question.Types.PARAGRAPH):
        s = "" if raw_value is None else str(raw_value)
        if "min_length" in rules and len(s) < int(rules["min_length"]):
            raise serializers.ValidationError(
                f"Question {qid}: answer must be at least {rules['min_length']} characters."
            )
        if "max_length" in rules and len(s) > int(rules["max_length"]):
            raise serializers.ValidationError(
                f"Question {qid}: answer must be at most {rules['max_length']} characters."
            )
        if s and "pattern" in rules:
            pat = rules["pattern"]
            if not re.match(pat, s):
                raise serializers.ValidationError(f"Question {qid}: answer does not match the required pattern.")

    elif qt == Question.Types.RATING:
        try:
            num = float(raw_value)
        except (TypeError, ValueError):
            raise serializers.ValidationError(f"Question {qid}: rating must be a number.")
        if "min" in rules and num < float(rules["min"]):
            raise serializers.ValidationError(f"Question {qid}: rating must be >= {rules['min']}.")
        if "max" in rules and num > float(rules["max"]):
            raise serializers.ValidationError(f"Question {qid}: rating must be <= {rules['max']}.")

    elif qt == Question.Types.DATE and raw_value:
        s = str(raw_value)
        try:
            d = datetime.strptime(s[:10], "%Y-%m-%d").date()
        except ValueError:
            raise serializers.ValidationError(f"Question {qid}: date must be YYYY-MM-DD.")
        if "min_date" in rules:
            lo = datetime.strptime(str(rules["min_date"])[:10], "%Y-%m-%d").date()
            if d < lo:
                raise serializers.ValidationError(f"Question {qid}: date must be on or after {lo}.")
        if "max_date" in rules:
            hi = datetime.strptime(str(rules["max_date"])[:10], "%Y-%m-%d").date()
            if d > hi:
                raise serializers.ValidationError(f"Question {qid}: date must be on or before {hi}.")


class ResponseSubmitSerializer(serializers.Serializer):
    answers = serializers.DictField(child=serializers.JSONField())

    def validate(self, attrs):
        form = self.context["form"]
        now = timezone.now()

        if form.status != Form.Status.PUBLISHED:
            raise serializers.ValidationError("Form is not published.")
        if form.opens_at and now < form.opens_at:
            raise serializers.ValidationError("Form is not open yet.")
        if form.closes_at and now > form.closes_at:
            raise serializers.ValidationError("Form is closed.")

        payload = attrs["answers"]
        questions = list(form.questions.all())
        q_by_id = {str(q.id): q for q in questions}
        required_ids = {str(q.id) for q in questions if q.required}
        submitted = set(payload.keys())
        missing = sorted(required_ids - submitted)
        if missing:
            raise serializers.ValidationError(f"Missing required answers for question IDs: {', '.join(missing)}")

        for qid, value in payload.items():
            q = q_by_id.get(str(qid))
            if not q:
                raise serializers.ValidationError(f"Unknown question id: {qid}")
            _validate_answer_against_rules(q, value)
        return attrs


class AnswerSerializer(serializers.ModelSerializer):
    class Meta:
        model = Answer
        fields = ("question_id", "value")


class ResponseSerializer(serializers.ModelSerializer):
    answers = AnswerSerializer(many=True, read_only=True)

    class Meta:
        model = Response
        fields = ("id", "form_id", "respondent_id", "submitted_at", "answers")


class CollaboratorSerializer(serializers.ModelSerializer):
    username = serializers.CharField(source="user.username", read_only=True)
    email = serializers.EmailField(source="user.email", read_only=True)

    class Meta:
        model = FormCollaborator
        fields = ("id", "user", "username", "email", "role", "created_at")
        read_only_fields = ("id", "created_at")


class CollaboratorCreateSerializer(serializers.Serializer):
    username = serializers.CharField(required=False)
    email = serializers.EmailField(required=False)
    role = serializers.ChoiceField(choices=FormCollaborator.Roles.choices)

    def validate(self, attrs):
        username = attrs.get("username")
        email = attrs.get("email")
        if not username and not email:
            raise serializers.ValidationError("Provide username or email.")

        user = None
        if username:
            user = User.objects.filter(username=username).first()
        if not user and email:
            user = User.objects.filter(email=email).first()
        if not user:
            raise serializers.ValidationError("User not found.")
        attrs["target_user"] = user
        return attrs


MAX_INVITE_EMAILS = 100


class InviteEmailsSerializer(serializers.Serializer):
    """Bulk invite: one request sends the same invitation to many addresses."""

    emails = serializers.ListField(child=serializers.EmailField(), min_length=1)
    message = serializers.CharField(required=False, allow_blank=True, default="", max_length=2000)

    def validate_emails(self, value):
        seen = set()
        unique = []
        for raw in value:
            e = (raw or "").strip().lower()
            if not e or e in seen:
                continue
            seen.add(e)
            unique.append(raw.strip())
        if not unique:
            raise serializers.ValidationError("Provide at least one valid email address.")
        if len(unique) > MAX_INVITE_EMAILS:
            raise serializers.ValidationError(f"At most {MAX_INVITE_EMAILS} emails per request.")
        return unique
