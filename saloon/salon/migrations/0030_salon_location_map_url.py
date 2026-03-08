from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("salon", "0029_salonfeatureimage_salonserviceimage"),
    ]

    operations = [
        migrations.AddField(
            model_name="salon",
            name="location_map_url",
            field=models.URLField(blank=True, help_text="Public map link for this salon location."),
        ),
    ]
