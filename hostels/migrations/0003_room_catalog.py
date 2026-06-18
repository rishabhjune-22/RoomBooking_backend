from django.db import migrations, models


DELTA_EXISTING_NUMBER_UPDATES = {
    "101A": "101-A",
    "101B": "101-B",
    "101C": "101-C",
    "101D": "101-D",
    "102A": "102-A",
    "102B": "102-B",
    "102C": "102-C",
    "102D": "103-D",
}

DELTA_NEW_ROOMS = [
    ("1103 A", "chairman_flat", True, 1),
    ("1103 B", "chairman_flat", True, 2),
    ("1103 C", "chairman_flat", True, 3),
    ("1001-A", "room", True, 10),
    ("1001-B", "room", True, 11),
    ("1001-C", "room", False, 12),
    ("1001-D", "room", False, 13),
    ("1002-A", "room", True, 20),
    ("1002-B", "room", True, 21),
    ("1002-C", "room", False, 22),
    ("1002-D", "room", False, 23),
    ("1003-A", "room", True, 60),
    ("1003-B", "room", True, 61),
    ("1003-C", "room", False, 62),
    ("1003-D", "room", False, 63),
    ("1004-A", "room", True, 70),
    ("1004-B", "room", True, 71),
    ("1004-C", "room", True, 72),
    ("1004-D", "room", True, 73),
]

DISPLAY_ORDER = {
    "Delta": {
        "101-A": 30, "101-B": 31, "101-C": 32, "101-D": 33,
        "102-A": 40, "102-B": 41, "102-C": 42, "103-D": 43,
    },
    "Gamma": {
        "101A": 1, "101C": 2, "101B": 3,
        "102A": 4, "102C": 5, "102B": 6,
    },
    "Beta": {
        "1103A": 1, "1103B": 2, "1104A": 3, "1104B": 4,
        "1001A": 5, "1001B": 6, "1002A": 7, "1002B": 8,
        "1003A": 9, "1003B": 10, "1004A": 11, "1004B": 12,
    },
}


def populate_room_catalog(apps, schema_editor):
    Room = apps.get_model("hostels", "Room")

    for old_number, new_number in DELTA_EXISTING_NUMBER_UPDATES.items():
        Room.objects.filter(prefix="Delta", number=old_number).update(number=new_number)

    Room.objects.filter(prefix="Delta").update(
        hostel_name="Gaurlata",
        room_type="room",
    )
    Room.objects.filter(prefix="Gamma").update(hostel_name="Mainpat", room_type="room")
    Room.objects.filter(prefix="Beta").update(hostel_name="Palma", room_type="room")

    for number, room_type, has_attached_bath, display_order in DELTA_NEW_ROOMS:
        Room.objects.update_or_create(
            prefix="Delta",
            number=number,
            defaults={
                "hostel_name": "Gaurlata",
                "room_type": room_type,
                "has_attached_bath": has_attached_bath,
                "display_order": display_order,
            },
        )

    for prefix, room_orders in DISPLAY_ORDER.items():
        for number, display_order in room_orders.items():
            Room.objects.filter(prefix=prefix, number=number).update(
                display_order=display_order
            )


class Migration(migrations.Migration):
    dependencies = [
        ("hostels", "0002_room_hostel_name_room_has_attached_bath"),
    ]

    operations = [
        migrations.AddField(
            model_name="room",
            name="display_order",
            field=models.PositiveSmallIntegerField(default=0),
        ),
        migrations.AddField(
            model_name="room",
            name="room_type",
            field=models.CharField(
                choices=[("room", "Room"), ("chairman_flat", "Chairman Flat")],
                default="room",
                max_length=20,
            ),
        ),
        migrations.RunPython(populate_room_catalog, migrations.RunPython.noop),
    ]
