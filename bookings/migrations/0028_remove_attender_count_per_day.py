from django.db import migrations


class Migration(migrations.Migration):
    dependencies = [
        ("bookings", "0027_bookingrequest_budget_head_department_name_and_more"),
    ]

    operations = [
        migrations.RemoveField(
            model_name="booking",
            name="attender_count_per_day",
        ),
        migrations.RemoveField(
            model_name="bookingrequest",
            name="attender_count_per_day",
        ),
    ]
