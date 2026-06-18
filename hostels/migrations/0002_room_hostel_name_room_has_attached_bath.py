from django.db import migrations, models


HOSTEL_NAME_BY_PREFIX = {
    "Delta": "Gaurlata",
    "Gamma": "Mainpat",
    "Beta": "Palma",
}

ROOMS_WITHOUT_ATTACHED_BATH = {
    ("Gamma", "101B"),
    ("Gamma", "102B"),
    ("Beta", "1001B"),
    ("Beta", "1002B"),
    ("Beta", "1003B"),
    ("Beta", "1004B"),
    ("Beta", "1103B"),
    ("Beta", "1104B"),
}


def populate_room_attributes(apps, schema_editor):
    Room = apps.get_model("hostels", "Room")

    for room in Room.objects.all().iterator():
        room.hostel_name = HOSTEL_NAME_BY_PREFIX.get(room.prefix, "")
        room.has_attached_bath = (room.prefix, room.number.upper()) not in (
            ROOMS_WITHOUT_ATTACHED_BATH
        )
        room.save(update_fields=["hostel_name", "has_attached_bath"])


class Migration(migrations.Migration):
    dependencies = [
        ("hostels", "0001_initial"),
    ]

    operations = [
        migrations.AddField(
            model_name="room",
            name="hostel_name",
            field=models.CharField(
                blank=True,
                choices=[
                    ("Gaurlata", "Gaurlata"),
                    ("Mainpat", "Mainpat"),
                    ("Palma", "Palma"),
                ],
                max_length=20,
            ),
        ),
        migrations.AddField(
            model_name="room",
            name="has_attached_bath",
            field=models.BooleanField(default=True),
        ),
        migrations.RunPython(populate_room_attributes, migrations.RunPython.noop),
    ]
