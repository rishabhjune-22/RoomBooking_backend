from django.db import models


class Room(models.Model):
    PREFIX_CHOICES = [
        ("Delta", "Delta"),
        ("Gamma", "Gamma"),
        ("Beta", "Beta"),
    ]

    prefix = models.CharField(max_length=10, choices=PREFIX_CHOICES)
    number = models.CharField(max_length=10)

    def __str__(self):
        return f"{self.prefix} {self.number}"

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["prefix", "number"], name="unique_room")
        ]
        indexes = [
            models.Index(fields=["prefix", "number"]),
        ]