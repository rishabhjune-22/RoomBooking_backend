from django.db import migrations, models


def delete_cancelled_bookings(apps, schema_editor):
    Booking = apps.get_model("bookings", "Booking")
    Booking.objects.filter(status="cancelled").delete()


class Migration(migrations.Migration):

    dependencies = [
        ("bookings", "0011_cancelledbooking_created_by_name"),
    ]

    operations = [
        migrations.RunPython(
            delete_cancelled_bookings,
            migrations.RunPython.noop,
        ),
        migrations.DeleteModel(
            name="CancelledBooking",
        ),
        migrations.AlterField(
            model_name="booking",
            name="status",
            field=models.CharField(
                choices=[
                    ("active", "Active"),
                    ("expired", "Expired"),
                ],
                db_index=True,
                default="active",
                max_length=20,
            ),
        ),
    ]
