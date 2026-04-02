from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("users", "0002_user_profile_and_google"),
    ]

    operations = [
        migrations.AddField(
            model_name="user",
            name="billing_plan",
            field=models.CharField(
                choices=[("free", "Free"), ("pro", "Pro")],
                db_index=True,
                default="free",
                max_length=20,
            ),
        ),
        migrations.AddField(
            model_name="user",
            name="stripe_customer_id",
            field=models.CharField(blank=True, default="", max_length=255),
        ),
        migrations.AddField(
            model_name="user",
            name="stripe_subscription_id",
            field=models.CharField(blank=True, default="", max_length=255),
        ),
        migrations.AddField(
            model_name="user",
            name="billing_current_period_end",
            field=models.DateTimeField(blank=True, null=True),
        ),
    ]
