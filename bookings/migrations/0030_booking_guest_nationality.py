from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("bookings", "0029_booking_remarks_bookingsheet_remarks"),
    ]

    operations = [
        migrations.AddField(
            model_name="booking",
            name="visitor_nationality",
            field=models.CharField(
                choices=[("indian", "Indian"), ("foreigner", "Foreigner")],
                default="indian",
                max_length=20,
            ),
        ),
        migrations.AddField(
            model_name="bookingrequest",
            name="visitor_nationality",
            field=models.CharField(
                choices=[("indian", "Indian"), ("foreigner", "Foreigner")],
                default="indian",
                max_length=20,
            ),
        ),
    ]
