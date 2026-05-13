from django.db import migrations


def remove_demo_lawyers(apps, schema_editor):
    Lawyer = apps.get_model("main", "Lawyer")
    Lawyer.objects.filter(email__endswith='@lexconnect.demo').delete()


class Migration(migrations.Migration):

    dependencies = [
        ("main", "0003_seed_lawyers_and_normalize_categories"),
    ]

    operations = [
        migrations.RunPython(remove_demo_lawyers, migrations.RunPython.noop),
    ]
