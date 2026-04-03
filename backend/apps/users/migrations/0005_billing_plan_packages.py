from django.db import migrations, models


def forwards_map_pro_to_plus(apps, schema_editor):
    User = apps.get_model("users", "User")
    User.objects.filter(billing_plan="pro").update(billing_plan="plus")


def backwards_map_plus_to_pro(apps, schema_editor):
    User = apps.get_model("users", "User")
    User.objects.filter(billing_plan="plus").update(billing_plan="pro")


class Migration(migrations.Migration):

    dependencies = [
        ("users", "0004_userapikey"),
    ]

    operations = [
        migrations.RunPython(forwards_map_pro_to_plus, backwards_map_plus_to_pro),
        migrations.AlterField(
            model_name="user",
            name="billing_plan",
            field=models.CharField(
                choices=[
                    ("free", "Free"),
                    ("basic", "Basic"),
                    ("team", "Team"),
                    ("plus", "Plus"),
                    ("premium", "Premium"),
                ],
                db_index=True,
                default="free",
                max_length=20,
            ),
        ),
    ]
