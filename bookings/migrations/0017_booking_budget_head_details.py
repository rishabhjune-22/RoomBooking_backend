from django.db import migrations, models


def copy_legacy_budget_head_values(apps, schema_editor):
    Booking = apps.get_model("bookings", "Booking")

    for booking in Booking.objects.exclude(budget_head_value="").iterator():
        value = (booking.budget_head_value or "").strip()
        if not value:
            continue

        if booking.budget_head_type == "institute_head":
            booking.budget_head_department_name = value
        elif booking.budget_head_type == "project_head":
            booking.budget_head_project_code = value
        else:
            booking.budget_head_name = value

        booking.save(
            update_fields=[
                "budget_head_name",
                "budget_head_department_name",
                "budget_head_project_code",
            ]
        )


class Migration(migrations.Migration):

    dependencies = [
        ("bookings", "0016_booking_budget_head"),
    ]

    operations = [
        migrations.AddField(
            model_name="booking",
            name="budget_head_name",
            field=models.CharField(blank=True, default="", max_length=100),
        ),
        migrations.AddField(
            model_name="booking",
            name="budget_head_department_name",
            field=models.CharField(blank=True, default="", max_length=100),
        ),
        migrations.AddField(
            model_name="booking",
            name="budget_head_project_code",
            field=models.CharField(blank=True, default="", max_length=100),
        ),
        migrations.RunPython(copy_legacy_budget_head_values, migrations.RunPython.noop),
    ]
