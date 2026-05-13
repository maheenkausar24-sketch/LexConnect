from django.db import migrations, models


def normalize_category_name(name):
    return " ".join(word.capitalize() for word in name.split())


def seed_foundation(apps, schema_editor):
    LawCategory = apps.get_model("main", "LawCategory")
    Lawyer = apps.get_model("main", "Lawyer")

    canonical_categories = {}

    for category in LawCategory.objects.order_by("id"):
        normalized_name = normalize_category_name(category.name)
        canonical = canonical_categories.get(normalized_name)

        if canonical is None:
            category.name = normalized_name
            category.save(update_fields=["name"])
            canonical_categories[normalized_name] = category
            continue

        Lawyer.objects.filter(category=category).update(category=canonical)
        category.delete()


class Migration(migrations.Migration):

    dependencies = [
        ("main", "0002_alter_lawyer_user"),
    ]

    operations = [
        migrations.AlterField(
            model_name="lawyer",
            name="certification",
            field=models.CharField(blank=True, max_length=200),
        ),
        migrations.AlterField(
            model_name="lawyer",
            name="certificate_file",
            field=models.FileField(blank=True, null=True, upload_to="certificates/"),
        ),
        migrations.RunPython(seed_foundation, migrations.RunPython.noop),
    ]
