from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("users", "0009_billingpackage_allow_self_select"),
    ]

    operations = [
        migrations.AddField(
            model_name="billingpackage",
            name="price_cents",
            field=models.PositiveIntegerField(
                blank=True,
                help_text="Display amount in smallest currency unit (e.g. USD cents). Informational only.",
                null=True,
            ),
        ),
        migrations.AddField(
            model_name="billingpackage",
            name="price_currency",
            field=models.CharField(
                default="usd",
                help_text="ISO 4217 lowercase currency code for display (e.g. usd, eur).",
                max_length=3,
            ),
        ),
        migrations.AddField(
            model_name="billingpackage",
            name="stripe_price_id",
            field=models.CharField(
                blank=True,
                help_text="Stripe recurring Price ID (price_…). Checkout uses this server-side; webhooks map the paid subscription to this package.",
                max_length=255,
                null=True,
                unique=True,
            ),
        ),
    ]
