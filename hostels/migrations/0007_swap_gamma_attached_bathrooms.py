from django.db import migrations


FORWARD_FLAGS = {
    "101B": True,
    "101C": False,
    "102B": True,
    "102C": False,
}

REVERSE_FLAGS = {
    "101B": False,
    "101C": True,
    "102B": False,
    "102C": True,
}


def set_gamma_bathroom_flags(apps, flags):
    Room = apps.get_model("hostels", "Room")

    for number, has_attached_bath in flags.items():
        Room.objects.filter(prefix="Gamma", number__iexact=number).update(
            has_attached_bath=has_attached_bath
        )


def apply_swap(apps, schema_editor):
    set_gamma_bathroom_flags(apps, FORWARD_FLAGS)


def reverse_swap(apps, schema_editor):
    set_gamma_bathroom_flags(apps, REVERSE_FLAGS)


class Migration(migrations.Migration):
    dependencies = [
        ("hostels", "0006_delete_bookings_for_obsolete_delta_rooms"),
    ]

    operations = [
        migrations.RunPython(apply_swap, reverse_swap),
    ]
