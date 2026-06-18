from datetime import datetime, timezone as datetime_timezone
from unittest.mock import patch
from zoneinfo import ZoneInfo

from django.core.cache import cache
from django.test import TestCase
from django.urls import reverse
from rest_framework import status
from rest_framework.throttling import ScopedRateThrottle

from hostels.models import Room

from .models import Booking
from .services.expiry_service import expire_due_bookings


INDIA_TZ = ZoneInfo("Asia/Kolkata")


class BookingApiBusinessRuleTests(TestCase):
    def setUp(self):
        self.signal_sync = patch("bookings.signals.request_calendar_sync", return_value=True)
        self.signal_sync.start()
        self.addCleanup(self.signal_sync.stop)

        self.room = Room.objects.create(prefix="Beta", number="101", hostel_name="Palma")
        self.other_room = Room.objects.create(prefix="Beta", number="102", hostel_name="Palma")

    def test_create_rejects_overlapping_booking_for_same_room(self):
        self.create_booking(
            self.room,
            utc_dt(2026, 7, 1, 10, 0),
            utc_dt(2026, 7, 1, 12, 0),
        )

        response = self.client.post(
            reverse("booking-create"),
            data=self.valid_payload(
                room=self.room,
                arrival_at=utc_dt(2026, 7, 1, 11, 0),
                departure_at=utc_dt(2026, 7, 1, 13, 0),
            ),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertFalse(response.json()["success"])
        self.assertIn("already booked", response.json()["message"])

    def test_create_rejects_booking_inside_cooling_period(self):
        self.create_booking(
            self.room,
            utc_dt(2026, 7, 1, 8, 0),
            utc_dt(2026, 7, 1, 10, 0),
        )

        response = self.client.post(
            reverse("booking-create"),
            data=self.valid_payload(
                room=self.room,
                arrival_at=utc_dt(2026, 7, 1, 10, 30),
                departure_at=utc_dt(2026, 7, 1, 11, 30),
            ),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertFalse(response.json()["success"])
        self.assertIn("cooling period", response.json()["message"])

    def test_create_rejects_same_day_when_cooling_runs_past_6pm(self):
        self.create_booking(
            self.room,
            local_dt(2026, 7, 1, 10, 0),
            local_dt(2026, 7, 1, 17, 30),
        )

        response = self.client.post(
            reverse("booking-create"),
            data=self.valid_payload(
                room=self.room,
                arrival_at=local_dt(2026, 7, 1, 18, 45),
                departure_at=local_dt(2026, 7, 1, 20, 0),
            ),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertFalse(response.json()["success"])
        self.assertIn("unavailable", response.json()["message"])

    def test_update_moving_booking_to_occupied_room_is_rejected(self):
        booking = self.create_booking(
            self.room,
            utc_dt(2026, 7, 1, 8, 0),
            utc_dt(2026, 7, 1, 9, 0),
        )
        self.create_booking(
            self.other_room,
            utc_dt(2026, 7, 1, 12, 0),
            utc_dt(2026, 7, 1, 13, 0),
        )

        response = self.client.patch(
            reverse("booking-edit", kwargs={"pk": booking.pk}),
            data={
                "room": self.other_room.id,
                "arrival_at": iso(utc_dt(2026, 7, 1, 12, 30)),
                "departure_at": iso(utc_dt(2026, 7, 1, 13, 30)),
            },
            content_type="application/json",
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        booking.refresh_from_db()
        self.assertEqual(booking.room_id, self.room.id)

    def test_delete_removes_booking(self):
        booking = self.create_booking(
            self.room,
            utc_dt(2026, 7, 1, 10, 0),
            utc_dt(2026, 7, 1, 12, 0),
        )

        response = self.client.delete(reverse("booking-delete", kwargs={"pk": booking.pk}))

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTrue(response.json()["success"])
        self.assertFalse(Booking.objects.filter(pk=booking.pk).exists())

    def test_create_is_idempotent_when_key_repeats(self):
        payload = self.valid_payload(
            room=self.room,
            arrival_at=utc_dt(2026, 7, 1, 10, 0),
            departure_at=utc_dt(2026, 7, 1, 12, 0),
        )
        headers = {"HTTP_IDEMPOTENCY_KEY": "create-2026-07-01-beta-101"}

        first = self.client.post(
            reverse("booking-create"),
            data=payload,
            content_type="application/json",
            **headers,
        )
        second = self.client.post(
            reverse("booking-create"),
            data=payload,
            content_type="application/json",
            **headers,
        )

        self.assertEqual(first.status_code, status.HTTP_201_CREATED)
        self.assertEqual(second.status_code, status.HTTP_201_CREATED)
        self.assertEqual(Booking.objects.count(), 1)
        self.assertEqual(
            first.json()["data"]["booking_id"],
            second.json()["data"]["booking_id"],
        )

    def test_delete_is_idempotent_when_key_repeats(self):
        booking = self.create_booking(
            self.room,
            utc_dt(2026, 7, 1, 10, 0),
            utc_dt(2026, 7, 1, 12, 0),
        )
        headers = {"HTTP_IDEMPOTENCY_KEY": "delete-booking-1"}

        first = self.client.delete(reverse("booking-delete", kwargs={"pk": booking.pk}), **headers)
        second = self.client.delete(reverse("booking-delete", kwargs={"pk": booking.pk}), **headers)

        self.assertEqual(first.status_code, status.HTTP_200_OK)
        self.assertEqual(second.status_code, status.HTTP_200_OK)
        self.assertEqual(first.json(), second.json())
        self.assertFalse(Booking.objects.filter(pk=booking.pk).exists())

    def test_booking_list_filters_use_india_local_dates(self):
        booking = self.create_booking(
            self.room,
            utc_dt(2026, 7, 1, 18, 45),
            utc_dt(2026, 7, 1, 20, 0),
        )

        response = self.client.get(
            reverse("booking-list"),
            {"arrival_from": "2026-07-02"},
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        ids = [item["id"] for item in response.json()["data"]["results"]]
        self.assertIn(booking.id, ids)

    def test_available_rooms_range_marks_departure_day_partial(self):
        self.create_booking(
            self.room,
            local_dt(2026, 7, 3, 10, 0),
            local_dt(2026, 7, 3, 12, 0),
        )

        response = self.client.get(
            reverse("room-available-rooms-range"),
            {
                "arrival_date": "2026-07-03",
                "departure_date": "2026-07-03",
                "prefix": "Beta",
            },
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        rooms = response.json()["data"]["rooms"]
        by_id = {room["room_id"]: room for room in rooms}
        self.assertEqual(by_id[self.room.id]["availability_status"], "partial")
        self.assertEqual(by_id[self.other_room.id]["availability_status"], "available")

    def test_booking_mutation_scope_returns_429(self):
        original_rates = ScopedRateThrottle.THROTTLE_RATES
        ScopedRateThrottle.THROTTLE_RATES = {"booking_mutation": "1/min"}
        self.addCleanup(lambda: setattr(ScopedRateThrottle, "THROTTLE_RATES", original_rates))
        cache.clear()
        remote_addr = "203.0.113.10"

        first = self.client.post(
            reverse("booking-create"),
            data=self.valid_payload(
                room=self.room,
                arrival_at=utc_dt(2026, 7, 1, 10, 0),
                departure_at=utc_dt(2026, 7, 1, 12, 0),
            ),
            content_type="application/json",
            REMOTE_ADDR=remote_addr,
        )
        second = self.client.post(
            reverse("booking-create"),
            data=self.valid_payload(
                room=self.other_room,
                arrival_at=utc_dt(2026, 7, 1, 10, 0),
                departure_at=utc_dt(2026, 7, 1, 12, 0),
            ),
            content_type="application/json",
            REMOTE_ADDR=remote_addr,
        )

        self.assertEqual(first.status_code, status.HTTP_201_CREATED)
        self.assertEqual(second.status_code, status.HTTP_429_TOO_MANY_REQUESTS)
        self.assertFalse(second.json()["success"])

    def create_booking(self, room, arrival_at, departure_at, **overrides):
        data = {
            "room": room,
            "arrival_at": arrival_at,
            "departure_at": departure_at,
            "visitor_name": "Visitor One",
        }
        data.update(overrides)
        return Booking.objects.create(**data)

    def valid_payload(self, room, arrival_at, departure_at, **overrides):
        payload = {
            "room": room.id,
            "arrival_at": iso(arrival_at),
            "departure_at": iso(departure_at),
            "visitor_name": "Visitor One",
            "visitor_mobile": "9876543210",
            "visitor_category": Booking.VISITOR_CATEGORY_INSTITUTE,
            "room_charges_status": Booking.CHARGE_STATUS_NO,
            "attender_charges_status": Booking.CHARGE_STATUS_NO,
            "room_charges_amount": "0",
            "attender_charges_amount": "0",
        }
        payload.update(overrides)
        return payload


class BookingExpiryServiceTests(TestCase):
    def setUp(self):
        self.signal_sync = patch("bookings.signals.request_calendar_sync", return_value=True)
        self.signal_sync.start()
        self.addCleanup(self.signal_sync.stop)
        self.room = Room.objects.create(prefix="Gamma", number="201", hostel_name="Mainpat")

    @patch("bookings.services.expiry_service.request_calendar_sync")
    def test_expiring_bookings_schedules_one_sheet_sync(self, sync_mock):
        Booking.objects.create(
            room=self.room,
            arrival_at=utc_dt(2026, 7, 1, 8, 0),
            departure_at=utc_dt(2026, 7, 1, 10, 0),
            visitor_name="Expired Visitor",
        )

        with self.captureOnCommitCallbacks(execute=True):
            expired_count = expire_due_bookings(now=utc_dt(2026, 7, 1, 11, 0))

        self.assertEqual(expired_count, 1)
        self.assertEqual(
            Booking.objects.get(visitor_name="Expired Visitor").status,
            Booking.STATUS_EXPIRED,
        )
        sync_mock.assert_called_once()


def utc_dt(year, month, day, hour, minute):
    return datetime(year, month, day, hour, minute, tzinfo=datetime_timezone.utc)


def local_dt(year, month, day, hour, minute):
    return datetime(year, month, day, hour, minute, tzinfo=INDIA_TZ)


def iso(value):
    return value.isoformat()
