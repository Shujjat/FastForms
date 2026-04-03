from django.db import migrations, models


def seed_package_limits(apps, schema_editor):
    BillingPackage = apps.get_model("users", "BillingPackage")
    for p in BillingPackage.objects.filter(slug="free"):
        p.max_owned_forms = 5
        p.ai_credits_per_period = 100
        p.ai_usage_period_days = 30
        p.save(update_fields=["max_owned_forms", "ai_credits_per_period", "ai_usage_period_days"])


def noop(apps, schema_editor):
    pass


class Migration(migrations.Migration):

    dependencies = [
        ("users", "0007_billingpackage_and_user_fk"),
    ]

    operations = [
        migrations.AddField(
            model_name="billingpackage",
            name="max_owned_forms",
            field=models.PositiveIntegerField(
                blank=True,
                help_text="Max forms this user may own; empty = unlimited.",
                null=True,
            ),
        ),
        migrations.AddField(
            model_name="billingpackage",
            name="ai_credits_per_period",
            field=models.PositiveIntegerField(
                blank=True,
                help_text="AI operations allowed per period for this package; empty = unlimited.",
                null=True,
            ),
        ),
        migrations.AddField(
            model_name="billingpackage",
            name="ai_usage_period_days",
            field=models.PositiveIntegerField(
                default=30,
                help_text="Length of each AI credit period (days).",
            ),
        ),
        migrations.AddField(
            model_name="user",
            name="ai_credits_used",
            field=models.PositiveIntegerField(default=0),
        ),
        migrations.AddField(
            model_name="user",
            name="ai_usage_period_start",
            field=models.DateTimeField(
                blank=True,
                help_text="Start of the current AI credit period (UTC).",
                null=True,
            ),
        ),
        migrations.RunPython(seed_package_limits, noop),
    ]
