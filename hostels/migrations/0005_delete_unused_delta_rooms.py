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


def delete_unused_delta_rooms(apps, schema_editor):
    Room = apps.get_model("hostels", "Room")
    Booking = apps.get_model("bookings", "Booking")

    old_delta_rooms = Room.objects.filter(prefix="Delta").exclude(
        number__in=DELTA_REQUIRED_ROOMS
    )
    protected_room_ids = set(
        Booking.objects.filter(room__in=old_delta_rooms).values_list("room_id", flat=True)
    )

    old_delta_rooms.exclude(id__in=protected_room_ids).delete()
    if protected_room_ids:
        old_delta_rooms.filter(id__in=protected_room_ids).update(is_active=False)


class Migration(migrations.Migration):

    dependencies = [
        ("hostels", "0004_room_is_active"),
        ("bookings", "0023_remove_booking_visitor_address_and_more"),
    ]

    operations = [
        migrations.RunPython(delete_unused_delta_rooms, migrations.RunPython.noop),
    ]
