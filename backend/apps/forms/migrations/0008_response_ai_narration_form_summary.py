from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("forms_app", "0007_form_fill_mode_question_disabled"),
    ]

    operations = [
        migrations.AddField(
            model_name="response",
            name="ai_narration",
            field=models.TextField(blank=True, default=""),
        ),
        migrations.AddField(
            model_name="response",
            name="ai_narration_generated_at",
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="form",
            name="responses_ai_summary",
            field=models.TextField(blank=True, default=""),
        ),
        migrations.AddField(
            model_name="form",
            name="responses_ai_summary_generated_at",
            field=models.DateTimeField(blank=True, null=True),
        ),
    ]
