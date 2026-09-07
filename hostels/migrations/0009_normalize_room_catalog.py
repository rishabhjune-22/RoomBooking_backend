from django.db import migrations


DELTA_ROOMS = [
    ("101A", True),
    ("101B", True),
    ("101C", False),
    ("101D", False),
    ("102A", True),
    ("102B", True),
    ("102C", False),
    ("102D", False),
]

GAMMA_ROOMS = [
    ("101A", True),
    ("101B", True),
    ("101C", False),
    ("101D", False),
    ("102A", True),
    ("102B", True),
]

BETA_ROOMS = [
    ("101A", True),
    ("101B", True),
    ("101C", False),
    ("101D", False),
    ("102A", True),
    ("102B", True),
    ("102C", False),
    ("102D", False),
    ("103A", True),
    ("103B", True),
    ("103C", False),
    ("103D", False),
]


def normalize_room_catalog(apps, schema_editor):
    Room = apps.get_model("hostels", "Room")

    plans = [
        ("Delta", DELTA_ROOMS, 1),
        ("Gamma", GAMMA_ROOMS, 9),
        ("Beta", BETA_ROOMS, 15),
    ]

    for prefix, rooms, start_order in plans:
        catalog_numbers = []
        for offset, (number, has_attached_bath) in enumerate(rooms):
            Room.objects.update_or_create(
                prefix=prefix,
                number=number,
                defaults={
                    "hostel_name": "Gaurlata",
                    "room_type": "room",
                    "has_attached_bath": has_attached_bath,
                    "display_order": start_order + offset,
                    "is_active": True,
                },
            )
            catalog_numbers.append(number)

        Room.objects.filter(prefix=prefix).exclude(number__in=catalog_numbers).update(
            is_active=False
        )


class Migration(migrations.Migration):
    dependencies = [
        ("hostels", "0008_gamma_beta_room_counts"),
    ]

    operations = [
        migrations.RunPython(normalize_room_catalog, migrations.RunPython.noop),
    ]
