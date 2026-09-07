from django.db import migrations


GAMMA_BETA_ACTIVE_ROOMS = [
    ("101A", True, 9),
    ("101B", True, 10),
    ("101C", False, 11),
    ("101D", False, 12),
    ("102A", True, 13),
    ("102B", True, 14),
    ("102C", False, 15),
    ("102D", False, 16),
]


def seed_gamma_beta_room_catalog(apps, schema_editor):
    Room = apps.get_model("hostels", "Room")

    active_numbers = [number for number, _, _ in GAMMA_BETA_ACTIVE_ROOMS]

    for prefix in ("Gamma", "Beta"):
        for number, has_attached_bath, display_order in GAMMA_BETA_ACTIVE_ROOMS:
            Room.objects.update_or_create(
                prefix=prefix,
                number=number,
                defaults={
                    "hostel_name": "Gaurlata",
                    "room_type": "room",
                    "has_attached_bath": has_attached_bath,
                    "display_order": display_order,
                    "is_active": True,
                },
            )

        Room.objects.filter(prefix=prefix).exclude(number__in=active_numbers).update(
            is_active=False
        )


class Migration(migrations.Migration):

    dependencies = [
        ("hostels", "0006_delete_bookings_for_obsolete_delta_rooms"),
    ]

    operations = [
        migrations.RunPython(seed_gamma_beta_room_catalog, migrations.RunPython.noop),
    ]
