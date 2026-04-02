import re
from datetime import datetime

from django.utils import timezone
from rest_framework import serializers

from apps.users.avatar import gravatar_url
from apps.users.models import User

from .models import Answer, Form, FormCollaborator, Question, Response
from .validation_formats import validate_text_format

_ALLOWED_VALIDATION_KEYS = frozenset(
    {"min_length", "max_length", "min", "max", "pattern", "min_date", "max_date", "format"}
)

_ALLOWED_FORMATS = frozenset({"email", "phone", "url", "zip_us", "integer", "alphanumeric"})


class QuestionSerializer(serializers.ModelSerializer):
    class Meta:
        model = Question
        fields = ("id", "order_index", "question_type", "text", "required", "disabled", "options", "validation")

    def validate_validation(self, value):
        if not isinstance(value, dict):
            raise serializers.ValidationError("validation must be an object.")
        extra = set(value.keys()) - _ALLOWED_VALIDATION_KEYS
        if extra:
            raise serializers.ValidationError(f"Unknown validation keys: {', '.join(sorted(extra))}")
        fmt = value.get("format")
        if fmt is not None and str(fmt).strip() != "" and fmt not in _ALLOWED_FORMATS:
            raise serializers.ValidationError(
                f"Invalid format {fmt!r}. Allowed: {', '.join(sorted(_ALLOWED_FORMATS))}."
            )
        return value


class FormSerializer(serializers.ModelSerializer):
    questions = QuestionSerializer(many=True, read_only=True)
    my_role = serializers.SerializerMethodField()
    show_platform_branding = serializers.SerializerMethodField()

    class Meta:
        model = Form
        fields = (
            "id",
            "title",
            "description",
            "thank_you_message",
            "appearance",
            "fill_mode",
            "status",
            "visibility",
            "one_response_per_user",
            "opens_at",
            "closes_at",
            "created_at",
            "updated_at",
            "questions",
            "my_role",
            "show_platform_branding",
        )
        read_only_fields = ("created_at", "updated_at", "my_role", "show_platform_branding")

    def get_my_role(self, obj):
        """How the current user relates to this form: owner | editor | viewer | respondent."""
        request = self.context.get("request")
        if not request or not request.user.is_authenticated:
            return None
        user = request.user
        if obj.owner_id == user.id:
            return "owner"
        collabs = getattr(obj, "_my_collaborations", None) or []
        if collabs:
            return collabs[0].role
        return "respondent"

    def get_show_platform_branding(self, obj):
        owner = getattr(obj, "owner", None)
        if not owner:
            return True
        return getattr(owner, "billing_plan", User.BillingPlan.FREE) == User.BillingPlan.FREE


class FormCreateSerializer(serializers.ModelSerializer):
    my_role = serializers.SerializerMethodField()

    class Meta:
        model = Form
        fields = (
            "id",
            "title",
            "description",
            "thank_you_message",
            "appearance",
            "fill_mode",
            "visibility",
            "one_response_per_user",
            "opens_at",
            "closes_at",
            "my_role",
        )
        read_only_fields = ("my_role",)

    def get_my_role(self, obj):
        return "owner"

    def update(self, instance, validated_data):
        request = self.context.get("request")
        if (
            request
            and request.user.is_authenticated
            and "visibility" in validated_data
            and instance.owner_id != request.user.id
        ):
            raise serializers.ValidationError(
                {"visibility": "Only the form owner can change visibility."}
            )
        return super().update(instance, validated_data)


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
        fmt = (rules.get("format") or "").strip()
        if s and fmt:
            try:
                validate_text_format(s, fmt)
            except ValueError as e:
                raise serializers.ValidationError(f"Question {qid}: {e.args[0]}") from e
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
        active_questions = [q for q in questions if not q.disabled]
        active_ids = {str(q.id) for q in active_questions}
        required_ids = {str(q.id) for q in active_questions if q.required}
        submitted = set(payload.keys())
        unknown = submitted - active_ids
        if unknown:
            raise serializers.ValidationError(
                f"Invalid or disabled question id(s) in answers: {', '.join(sorted(unknown))}"
            )
        missing = sorted(required_ids - submitted)
        if missing:
            raise serializers.ValidationError(f"Missing required answers for question IDs: {', '.join(missing)}")

        for qid, value in payload.items():
            q = q_by_id.get(str(qid))
            if not q or q.disabled:
                continue
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
    display_name = serializers.SerializerMethodField()
    avatar_url = serializers.SerializerMethodField()

    class Meta:
        model = FormCollaborator
        fields = ("id", "user", "username", "email", "display_name", "avatar_url", "role", "created_at")
        read_only_fields = ("id", "created_at")

    def get_display_name(self, obj):
        u = obj.user
        return (u.get_full_name() or u.username or "").strip()

    def get_avatar_url(self, obj):
        return gravatar_url(obj.user.email or "")


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
