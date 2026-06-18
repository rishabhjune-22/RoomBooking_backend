from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("bookings", "0008_booking_charge_statuses"),
    ]

    operations = [
        migrations.AddField(
            model_name="booking",
            name="room_charges_amount",
            field=models.DecimalField(decimal_places=2, default=0, max_digits=10),
        ),
        migrations.AddField(
            model_name="booking",
            name="attender_charges_amount",
            field=models.DecimalField(decimal_places=2, default=0, max_digits=10),
        ),
        migrations.AddField(
            model_name="cancelledbooking",
            name="room_charges_amount",
            field=models.DecimalField(decimal_places=2, default=0, max_digits=10),
        ),
        migrations.AddField(
            model_name="cancelledbooking",
            name="attender_charges_amount",
            field=models.DecimalField(decimal_places=2, default=0, max_digits=10),
        ),
    ]
