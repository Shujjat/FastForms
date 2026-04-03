from django.db import migrations, models
import django.db.models.deletion


def seed_billing_packages(apps, schema_editor):
    BillingPackage = apps.get_model("users", "BillingPackage")
    rows = [
        ("free", "Free", "", 0, True, True),
        ("basic", "Basic", "", 10, True, False),
        ("team", "Team", "", 20, True, False),
        ("plus", "Plus", "", 30, True, False),
        ("premium", "Premium", "", 40, True, False),
    ]
    for slug, name, desc, order, active, free in rows:
        BillingPackage.objects.update_or_create(
            slug=slug,
            defaults={
                "name": name,
                "description": desc,
                "sort_order": order,
                "is_active": active,
                "is_free_tier": free,
            },
        )


def attach_users_to_packages(apps, schema_editor):
    User = apps.get_model("users", "User")
    BillingPackage = apps.get_model("users", "BillingPackage")
    by_slug = {p.slug: p.pk for p in BillingPackage.objects.all()}
    fallback = by_slug.get("free")
    for u in User.objects.all():
        slug = getattr(u, "billing_plan", None) or "free"
        uid = by_slug.get(slug, fallback)
        if uid:
            User.objects.filter(pk=u.pk).update(billing_package_id=uid)


def noop_reverse(apps, schema_editor):
    pass


class Migration(migrations.Migration):

    dependencies = [
        ("users", "0006_rename_userapikey_hash_idx_users_usera_key_has_a2c5c2_idx_and_more"),
    ]

    operations = [
        migrations.CreateModel(
            name="BillingPackage",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("slug", models.SlugField(max_length=32, unique=True)),
                ("name", models.CharField(max_length=64)),
                ("description", models.TextField(blank=True, default="")),
                ("sort_order", models.PositiveSmallIntegerField(default=0)),
                ("is_active", models.BooleanField(default=True, help_text="If false, hidden from default pickers but superusers can still assign.")),
                ("is_free_tier", models.BooleanField(default=False, help_text="Exactly one package should be the free tier (form limits, branding).")),
            ],
            options={
                "ordering": ["sort_order", "id"],
            },
        ),
        migrations.RunPython(seed_billing_packages, noop_reverse),
        migrations.AddField(
            model_name="user",
            name="billing_package",
            field=models.ForeignKey(
                null=True,
                blank=True,
                on_delete=django.db.models.deletion.PROTECT,
                related_name="users",
                to="users.billingpackage",
            ),
        ),
        migrations.RunPython(attach_users_to_packages, noop_reverse),
        migrations.RemoveField(
            model_name="user",
            name="billing_plan",
        ),
        migrations.AlterField(
            model_name="user",
            name="billing_package",
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.PROTECT,
                related_name="users",
                to="users.billingpackage",
            ),
        ),
    ]
