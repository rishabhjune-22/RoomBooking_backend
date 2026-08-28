from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("bookings", "0028_remove_attender_count_per_day"),
    ]

    operations = [
        migrations.AddField(
            model_name="booking",
            name="remarks",
            field=models.TextField(blank=True, default=""),
        ),
        migrations.AddField(
            model_name="bookingchargesheet",
            name="remarks",
            field=models.TextField(blank=True, default=""),
        ),
    ]
