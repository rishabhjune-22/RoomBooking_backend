from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("bookings", "0015_remove_attender_night_shift"),
    ]

    operations = [
        migrations.AddField(
            model_name="booking",
            name="budget_head_type",
            field=models.CharField(
                blank=True,
                choices=[
                    ("individual", "Individual"),
                    ("institute_head", "Institute Head"),
                    ("project_head", "Project Head"),
                ],
                default="",
                max_length=30,
            ),
        ),
        migrations.AddField(
            model_name="booking",
            name="budget_head_value",
            field=models.CharField(blank=True, default="", max_length=100),
        ),
    ]
