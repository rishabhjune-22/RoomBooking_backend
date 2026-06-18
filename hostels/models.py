from django.db import models


class Room(models.Model):
    PREFIX_CHOICES = [
        ("Delta", "Delta"),
        ("Gamma", "Gamma"),
        ("Beta", "Beta"),
    ]

    HOSTEL_NAME_CHOICES = [
        ("Gaurlata", "Gaurlata"),
        ("Mainpat", "Mainpat"),
        ("Palma", "Palma"),
    ]

    ROOM_TYPE_ROOM = "room"
    ROOM_TYPE_CHAIRMAN_FLAT = "chairman_flat"
    ROOM_TYPE_CHOICES = [
        (ROOM_TYPE_ROOM, "Room"),
        (ROOM_TYPE_CHAIRMAN_FLAT, "Chairman Flat"),
    ]

    prefix = models.CharField(max_length=10, choices=PREFIX_CHOICES)
    number = models.CharField(max_length=10)
    hostel_name = models.CharField(max_length=20, choices=HOSTEL_NAME_CHOICES, blank=True)
    has_attached_bath = models.BooleanField(default=True)
    room_type = models.CharField(
        max_length=20,
        choices=ROOM_TYPE_CHOICES,
        default=ROOM_TYPE_ROOM,
    )
    display_order = models.PositiveSmallIntegerField(default=0)

    @property
    def selection_label(self):
        label = self.number
        if self.room_type == self.ROOM_TYPE_CHAIRMAN_FLAT:
            label = f"Chairman Flat {label}"
        if not self.has_attached_bath:
            label = f"{label} — bathroom not attached"
        return label

    def __str__(self):
        return f"{self.prefix} {self.selection_label}"

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["prefix", "number"], name="unique_room")
        ]
        indexes = [
            models.Index(fields=["prefix", "number"]),
        ]
