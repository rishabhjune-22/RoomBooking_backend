from django.db import migrations, models


def clear_chargeable_without_morning_shift(apps, schema_editor):
    Booking = apps.get_model("bookings", "Booking")
    BookingRequest = apps.get_model("bookings", "BookingRequest")
    Booking.objects.filter(attender_morning_shift=False).update(attender_morning_chargeable=False)
    BookingRequest.objects.filter(attender_morning_shift=False).update(attender_morning_chargeable=False)


class Migration(migrations.Migration):

    dependencies = [
        ("bookings", "0033_rename_attender_day_shift_to_evening_shift"),
    ]

    operations = [
        migrations.AddField(
            model_name="booking",
            name="attender_morning_chargeable",
            field=models.BooleanField(default=True),
        ),
        migrations.AddField(
            model_name="bookingrequest",
            name="attender_morning_chargeable",
            field=models.BooleanField(default=True),
        ),
        migrations.RunPython(clear_chargeable_without_morning_shift, migrations.RunPython.noop),
    ]
