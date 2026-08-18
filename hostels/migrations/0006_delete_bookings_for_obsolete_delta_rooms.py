from django.db import migrations


DELTA_REQUIRED_ROOMS = {
    "101A",
    "101B",
    "101C",
    "101D",
    "102A",
    "102B",
    "102C",
    "102D",
}


def delete_bookings_and_obsolete_delta_rooms(apps, schema_editor):
    Room = apps.get_model("hostels", "Room")
    Booking = apps.get_model("bookings", "Booking")

    obsolete_delta_rooms = Room.objects.filter(prefix="Delta").exclude(
        number__in=DELTA_REQUIRED_ROOMS
    )
    Booking.objects.filter(room__in=obsolete_delta_rooms).delete()
    obsolete_delta_rooms.delete()


class Migration(migrations.Migration):

    dependencies = [
        ("hostels", "0005_delete_unused_delta_rooms"),
        ("bookings", "0023_remove_booking_visitor_address_and_more"),
    ]

    operations = [
        migrations.RunPython(
            delete_bookings_and_obsolete_delta_rooms,
            migrations.RunPython.noop,
        ),
    ]
