from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("salon", "0011_worker_user_and_login_access"),
    ]

    operations = [
        migrations.AlterField(
            model_name="salon",
            name="is_active",
            field=models.BooleanField(default=False),
        ),
    ]
