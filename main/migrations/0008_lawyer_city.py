from django.db import migrations, models


def copy_location_to_city(apps, schema_editor):
    Lawyer = apps.get_model("main", "Lawyer")
    for lawyer in Lawyer.objects.filter(city="").exclude(location=""):
        lawyer.city = lawyer.location
        lawyer.save(update_fields=["city"])


class Migration(migrations.Migration):

    dependencies = [
        ("main", "0007_lawyeravailability_and_more"),
    ]

    operations = [
        migrations.AddField(
            model_name="lawyer",
            name="city",
            field=models.CharField(blank=True, max_length=100),
        ),
        migrations.RunPython(copy_location_to_city, migrations.RunPython.noop),
    ]
