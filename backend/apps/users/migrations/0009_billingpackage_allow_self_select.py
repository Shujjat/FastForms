from django.db import migrations, models


def default_self_select(apps, schema_editor):
    BillingPackage = apps.get_model("users", "BillingPackage")
    BillingPackage.objects.filter(slug="free").update(allow_self_select=True)


def noop(apps, schema_editor):
    pass


class Migration(migrations.Migration):

    dependencies = [
        ("users", "0008_billingpackage_usage_limits"),
    ]

    operations = [
        migrations.AddField(
            model_name="billingpackage",
            name="allow_self_select",
            field=models.BooleanField(
                default=False,
                help_text="If true, creators/admins can pick this package on the Billing page without superuser help.",
            ),
        ),
        migrations.RunPython(default_self_select, noop),
    ]
