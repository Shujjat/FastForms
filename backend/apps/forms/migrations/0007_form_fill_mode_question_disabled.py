from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("forms_app", "0006_form_appearance"),
    ]

    operations = [
        migrations.AddField(
            model_name="form",
            name="fill_mode",
            field=models.CharField(
                choices=[("all_at_once", "All at once"), ("wizard", "Wizard (one question per step)")],
                default="all_at_once",
                max_length=20,
            ),
        ),
        migrations.AddField(
            model_name="question",
            name="disabled",
            field=models.BooleanField(default=False),
        ),
    ]
