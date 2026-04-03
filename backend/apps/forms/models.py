from django.conf import settings
from django.db import models


class Form(models.Model):
    class Status(models.TextChoices):
        DRAFT = "draft", "Draft"
        PUBLISHED = "published", "Published"
        CLOSED = "closed", "Closed"

    class Visibility(models.TextChoices):
        PUBLIC = "public", "Public"
        PRIVATE = "private", "Private"

    class FillMode(models.TextChoices):
        ALL_AT_ONCE = "all_at_once", "All at once"
        WIZARD = "wizard", "Wizard (one question per step)"

    owner = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="forms")
    title = models.CharField(max_length=255)
    description = models.TextField(blank=True)
    thank_you_message = models.TextField(blank=True, default="")
    appearance = models.JSONField(default=dict, blank=True)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.DRAFT)
    visibility = models.CharField(max_length=20, choices=Visibility.choices, default=Visibility.PUBLIC)
    one_response_per_user = models.BooleanField(default=False)
    opens_at = models.DateTimeField(null=True, blank=True)
    closes_at = models.DateTimeField(null=True, blank=True)
    fill_mode = models.CharField(max_length=20, choices=FillMode.choices, default=FillMode.ALL_AT_ONCE)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    responses_ai_summary = models.TextField(blank=True, default="")
    responses_ai_summary_generated_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-updated_at"]


class Question(models.Model):
    class Types(models.TextChoices):
        SHORT_TEXT = "short_text", "Short Text"
        PARAGRAPH = "paragraph", "Paragraph"
        SINGLE_CHOICE = "single_choice", "Single Choice"
        MULTI_CHOICE = "multi_choice", "Multi Choice"
        DROPDOWN = "dropdown", "Dropdown"
        DATE = "date", "Date"
        RATING = "rating", "Rating"
        FILE_UPLOAD = "file_upload", "File Upload"

    form = models.ForeignKey(Form, on_delete=models.CASCADE, related_name="questions")
    order_index = models.PositiveIntegerField(default=0)
    question_type = models.CharField(max_length=30, choices=Types.choices)
    text = models.CharField(max_length=500)
    required = models.BooleanField(default=False)
    disabled = models.BooleanField(default=False)
    options = models.JSONField(default=list, blank=True)
    validation = models.JSONField(default=dict, blank=True)

    class Meta:
        ordering = ["order_index", "id"]


class Response(models.Model):
    form = models.ForeignKey(Form, on_delete=models.CASCADE, related_name="responses")
    respondent = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="responses"
    )
    submitted_at = models.DateTimeField(auto_now_add=True)
    ai_narration = models.TextField(blank=True, default="")
    ai_narration_generated_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["form", "respondent"],
                condition=models.Q(respondent__isnull=False),
                name="unique_form_respondent_when_present",
            )
        ]


class Answer(models.Model):
    response = models.ForeignKey(Response, on_delete=models.CASCADE, related_name="answers")
    question = models.ForeignKey(Question, on_delete=models.CASCADE, related_name="answers")
    value = models.JSONField()


class FormCollaborator(models.Model):
    class Roles(models.TextChoices):
        EDITOR = "editor", "Editor"
        VIEWER = "viewer", "Viewer"

    form = models.ForeignKey(Form, on_delete=models.CASCADE, related_name="collaborators")
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="form_collaborations")
    role = models.CharField(max_length=20, choices=Roles.choices, default=Roles.VIEWER)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["form", "user"], name="unique_form_collaborator"),
        ]
