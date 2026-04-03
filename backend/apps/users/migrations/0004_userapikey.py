from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("users", "0003_user_billing"),
    ]

    operations = [
        migrations.CreateModel(
            name="UserApiKey",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("name", models.CharField(blank=True, default="", max_length=120)),
                ("prefix", models.CharField(db_index=True, max_length=16)),
                ("key_hash", models.CharField(max_length=64, unique=True)),
                ("scopes", models.JSONField(default=list)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("last_used_at", models.DateTimeField(blank=True, null=True)),
                ("is_active", models.BooleanField(default=True)),
                (
                    "user",
                    models.ForeignKey(
                        on_delete=models.CASCADE,
                        related_name="api_keys",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
            options={
                "ordering": ["-created_at"],
                "indexes": [
                    models.Index(fields=["key_hash"], name="userapikey_hash_idx"),
                    models.Index(fields=["user", "is_active"], name="userapikey_user_act_idx"),
                ],
            },
        ),
    ]
