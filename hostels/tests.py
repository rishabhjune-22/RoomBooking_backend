from django.db import IntegrityError, transaction
from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from rest_framework import status
from rest_framework_simplejwt.tokens import RefreshToken

from .models import Room


User = get_user_model()


class RoomModelTests(TestCase):
    def test_prefix_and_number_must_be_unique(self):
        Room.objects.create(prefix="Beta", number="101")

        with self.assertRaises(IntegrityError), transaction.atomic():
            Room.objects.create(prefix="Beta", number="101")


class RoomListApiTests(TestCase):
    def setUp(self):
        Room.objects.all().delete()
        user = User.objects.create_user(
            username="rooms@example.com",
            email="rooms@example.com",
            password="StrongPass123",
        )
        self.client.defaults["HTTP_AUTHORIZATION"] = (
            f"Bearer {RefreshToken.for_user(user).access_token}"
        )
        Room.objects.create(
            prefix="Gamma", number="202", hostel_name="Mainpat", has_attached_bath=True
        )
        Room.objects.create(
            prefix="Beta", number="102", hostel_name="Palma", has_attached_bath=False
        )
        Room.objects.create(
            prefix="Beta", number="101", hostel_name="Palma", has_attached_bath=True
        )

    def test_rooms_are_ordered_and_paginated(self):
        response = self.client.get(reverse("room-list"))

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        results = response.json()["data"]["results"]
        self.assertEqual(
            [room["room_name"] for room in results],
            ["Beta 101", "Beta 102 — bathroom not attached", "Gamma 202"],
        )
        self.assertEqual(results[0]["hostel_name"], "Palma")
        self.assertTrue(results[0]["has_attached_bath"])
        self.assertFalse(results[1]["has_attached_bath"])
        self.assertEqual(results[1]["selection_label"], "102 — bathroom not attached")

    def test_chairman_flat_selection_label(self):
        room = Room.objects.create(
            prefix="Delta",
            number="1103 A",
            hostel_name="Gaurlata",
            room_type=Room.ROOM_TYPE_CHAIRMAN_FLAT,
        )

        self.assertEqual(room.selection_label, "Chairman Flat 1103 A")
        self.assertEqual(str(room), "Delta Chairman Flat 1103 A")

    def test_search_filters_by_prefix_or_number(self):
        response = self.client.get(reverse("room-list"), {"search": "202"})

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        results = response.json()["data"]["results"]
        self.assertEqual([room["room_name"] for room in results], ["Gamma 202"])
