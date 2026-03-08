from django.db import migrations


def backfill_visit_services(apps, schema_editor):
    SalonVisit = apps.get_model("salon", "SalonVisit")
    through_model = SalonVisit.services.through
    records = []
    for visit in SalonVisit.objects.exclude(service_id__isnull=True).iterator():
        records.append(through_model(salonvisit_id=visit.id, salonservice_id=visit.service_id))
    if records:
        through_model.objects.bulk_create(records, ignore_conflicts=True)


class Migration(migrations.Migration):
    dependencies = [
        ("salon", "0013_salonvisit_services"),
    ]

    operations = [
        migrations.RunPython(backfill_visit_services, migrations.RunPython.noop),
    ]
