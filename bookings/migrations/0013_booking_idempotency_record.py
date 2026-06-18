from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("bookings", "0012_remove_cancelled_bookings"),
    ]

    operations = [
        migrations.CreateModel(
            name="BookingIdempotencyRecord",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("action", models.CharField(choices=[("booking_create", "Booking create"), ("booking_delete", "Booking delete")], max_length=50)),
                ("key", models.CharField(max_length=128)),
                ("request_hash", models.CharField(max_length=64)),
                ("booking_id", models.PositiveIntegerField(blank=True, null=True)),
                ("response_status", models.PositiveSmallIntegerField(blank=True, null=True)),
                ("response_body", models.JSONField(blank=True, null=True)),
                ("created_at", models.DateTimeField(auto_now_add=True, db_index=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
            ],
        ),
        migrations.AddConstraint(
            model_name="bookingidempotencyrecord",
            constraint=models.UniqueConstraint(fields=("action", "key"), name="unique_booking_idempotency_key"),
        ),
        migrations.AddIndex(
            model_name="bookingidempotencyrecord",
            index=models.Index(fields=["action", "created_at"], name="bookings_bo_action_40c9e4_idx"),
        ),
    ]
