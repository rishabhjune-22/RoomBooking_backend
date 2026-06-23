from datetime import datetime, timezone as datetime_timezone
from unittest.mock import patch
from zoneinfo import ZoneInfo

from django.core.cache import cache
from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from rest_framework import status
from rest_framework.throttling import ScopedRateThrottle
from rest_framework_simplejwt.tokens import RefreshToken

from accounts.roles import APPROVAL_PENDING, ROLE_ADMIN, ROLE_REQUESTER, set_user_role
from hostels.models import Room

from .models import Booking, BookingEditHistory, BookingRequest
from .services.expiry_service import expire_due_bookings


INDIA_TZ = ZoneInfo("Asia/Kolkata")
User = get_user_model()


def create_user(email="rishabh@example.com", name="Rishabh Kumar"):
    user = User.objects.create_user(
        username=email,
        email=email,
        password="StrongPass123",
        first_name=name,
    )
    set_user_role(user, ROLE_ADMIN)
    return user


def create_requester(email="requester@example.com", name="Requester One"):
    user = User.objects.create_user(
        username=email,
        email=email,
        password="StrongPass123",
        first_name=name,
    )
    set_user_role(user, ROLE_REQUESTER)
    return user


def bearer_token(user):
    return f"Bearer {RefreshToken.for_user(user).access_token}"


class BookingApiBusinessRuleTests(TestCase):
    def setUp(self):
        self.signal_sync = patch("bookings.signals.request_calendar_sync", return_value=True)
        self.signal_sync.start()
        self.addCleanup(self.signal_sync.stop)

        self.room = Room.objects.create(prefix="Beta", number="101", hostel_name="Palma")
        self.other_room = Room.objects.create(prefix="Beta", number="102", hostel_name="Palma")
        self.user = create_user()
        self.client.defaults["HTTP_AUTHORIZATION"] = bearer_token(self.user)

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

    def test_create_accepts_requestor_fields(self):
        response = self.client.post(
            reverse("booking-create"),
            data=self.valid_payload(
                room=self.room,
                arrival_at=utc_dt(2026, 7, 1, 10, 0),
                departure_at=utc_dt(2026, 7, 1, 12, 0),
                requestor_name="Requestor One",
                requestor_designation="Assistant Registrar",
                requestor_department="Administration",
                requestor_mobile="9876543211",
            ),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        booking = Booking.objects.get(pk=response.json()["data"]["booking_id"])
        self.assertEqual(booking.requestor_name, "Requestor One")
        self.assertEqual(booking.requestor_designation, "Assistant Registrar")
        self.assertEqual(booking.requestor_department, "Administration")
        self.assertEqual(booking.requestor_mobile, "9876543211")

        detail = self.client.get(reverse("booking-detail", kwargs={"pk": booking.pk}))
        self.assertEqual(detail.status_code, status.HTTP_200_OK)
        self.assertEqual(detail.json()["data"]["requestor_name"], "Requestor One")

    def test_create_rejects_invalid_mobile_numbers(self):
        invalid_cases = {
            "visitor_mobile": "123",
            "requestor_mobile": "abc1234567",
            "logistics_mobile": "1" * 16,
        }

        for field, value in invalid_cases.items():
            with self.subTest(field=field):
                response = self.client.post(
                    reverse("booking-create"),
                    data=self.valid_payload(
                        room=self.room,
                        arrival_at=utc_dt(2026, 7, 1, 10, 0),
                        departure_at=utc_dt(2026, 7, 1, 12, 0),
                        **{field: value},
                    ),
                    content_type="application/json",
                )

                self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
                self.assertFalse(response.json()["success"])
                self.assertIn(field, response.json()["errors"])

    def test_create_accepts_budget_head_fields(self):
        response = self.client.post(
            reverse("booking-create"),
            data=self.valid_payload(
                room=self.room,
                arrival_at=utc_dt(2026, 7, 1, 10, 0),
                departure_at=utc_dt(2026, 7, 1, 12, 0),
                budget_head_type=Booking.BUDGET_HEAD_PROJECT,
                budget_head_value="PRJ-2026-001",
                budget_head_name="Project Travel",
                budget_head_department_name="Computer Science",
                budget_head_project_code="PRJ-2026-001",
            ),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        booking = Booking.objects.get(pk=response.json()["data"]["booking_id"])
        self.assertEqual(booking.budget_head_type, Booking.BUDGET_HEAD_PROJECT)
        self.assertEqual(booking.budget_head_value, "PRJ-2026-001")
        self.assertEqual(booking.budget_head_name, "Project Travel")
        self.assertEqual(booking.budget_head_department_name, "Computer Science")
        self.assertEqual(booking.budget_head_project_code, "PRJ-2026-001")

        detail = self.client.get(reverse("booking-detail", kwargs={"pk": booking.pk}))
        self.assertEqual(detail.status_code, status.HTTP_200_OK)
        self.assertEqual(detail.json()["data"]["budget_head_type"], Booking.BUDGET_HEAD_PROJECT)
        self.assertEqual(detail.json()["data"]["budget_head_value"], "PRJ-2026-001")
        self.assertEqual(detail.json()["data"]["budget_head_name"], "Project Travel")
        self.assertEqual(
            detail.json()["data"]["budget_head_department_name"],
            "Computer Science",
        )
        self.assertEqual(detail.json()["data"]["budget_head_project_code"], "PRJ-2026-001")

    def test_create_booking_uses_logged_in_user_as_created_by(self):
        response = self.client.post(
            reverse("booking-create"),
            data=self.valid_payload(
                room=self.room,
                arrival_at=utc_dt(2026, 7, 1, 10, 0),
                departure_at=utc_dt(2026, 7, 1, 12, 0),
            ),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        booking = Booking.objects.get(pk=response.json()["data"]["booking_id"])
        self.assertEqual(booking.created_by, self.user)
        self.assertEqual(booking.created_by_name, "Rishabh Kumar")

    def test_old_created_by_name_from_request_is_ignored(self):
        response = self.client.post(
            reverse("booking-create"),
            data=self.valid_payload(
                room=self.room,
                arrival_at=utc_dt(2026, 7, 1, 10, 0),
                departure_at=utc_dt(2026, 7, 1, 12, 0),
                created_by_name="Legacy Client Name",
            ),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        booking = Booking.objects.get(pk=response.json()["data"]["booking_id"])
        self.assertEqual(booking.created_by_name, "Rishabh Kumar")

    def test_booking_detail_includes_created_by_name_and_empty_edit_history(self):
        booking = self.create_booking(
            self.room,
            utc_dt(2026, 7, 1, 10, 0),
            utc_dt(2026, 7, 1, 12, 0),
            created_by=self.user,
            created_by_name="Stored Name",
        )

        response = self.client.get(reverse("booking-detail", kwargs={"pk": booking.pk}))

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.json()["data"]
        self.assertEqual(data["created_by_name"], "Rishabh Kumar")
        self.assertIn("created_at", data)
        self.assertEqual(data["edit_history"], [])

    def test_booking_list_does_not_include_edit_history(self):
        booking = self.create_booking(
            self.room,
            utc_dt(2026, 7, 1, 10, 0),
            utc_dt(2026, 7, 1, 12, 0),
            created_by=self.user,
        )
        BookingEditHistory.objects.create(
            booking=booking,
            edited_by=self.user,
            edited_by_name="Rishabh Kumar",
            edited_by_email=self.user.email,
            field_name="purpose_of_visit",
            field_label="Purpose of Visit",
            old_value="Old",
            new_value="New",
        )

        response = self.client.get(reverse("booking-list"))

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        result = response.json()["data"]["results"][0]
        self.assertNotIn("edit_history", result)

    def test_unauthenticated_edit_is_rejected(self):
        booking = self.create_booking(
            self.room,
            utc_dt(2026, 7, 1, 10, 0),
            utc_dt(2026, 7, 1, 12, 0),
        )
        self.client.defaults.pop("HTTP_AUTHORIZATION", None)

        response = self.client.patch(
            reverse("booking-edit", kwargs={"pk": booking.pk}),
            data={"purpose_of_visit": "Updated purpose"},
            content_type="application/json",
        )

        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
        self.assertEqual(BookingEditHistory.objects.count(), 0)

    def test_authenticated_edit_creates_one_history_row_for_one_field(self):
        booking = self.create_booking(
            self.room,
            utc_dt(2026, 7, 1, 10, 0),
            utc_dt(2026, 7, 1, 12, 0),
            purpose_of_visit="Old purpose",
            created_by=self.user,
        )

        response = self.client.patch(
            reverse("booking-edit", kwargs={"pk": booking.pk}),
            data={"purpose_of_visit": "New purpose"},
            content_type="application/json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        history = BookingEditHistory.objects.get(booking=booking)
        self.assertEqual(history.edited_by, self.user)
        self.assertEqual(history.edited_by_name, "Rishabh Kumar")
        self.assertEqual(history.edited_by_email, self.user.email)
        self.assertEqual(history.field_name, "purpose_of_visit")
        self.assertEqual(history.field_label, "Purpose of Visit")
        self.assertEqual(history.old_value, "Old purpose")
        self.assertEqual(history.new_value, "New purpose")

    def test_editing_multiple_fields_creates_multiple_history_rows(self):
        booking = self.create_booking(
            self.room,
            utc_dt(2026, 7, 1, 10, 0),
            utc_dt(2026, 7, 1, 12, 0),
            requestor_name="Old Requestor",
            budget_head_project_code="OLD-001",
        )

        response = self.client.patch(
            reverse("booking-edit", kwargs={"pk": booking.pk}),
            data={
                "requestor_name": "New Requestor",
                "budget_head_project_code": "NEW-002",
                "departure_at": iso(utc_dt(2026, 7, 1, 13, 0)),
            },
            content_type="application/json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        history_by_field = {
            item.field_name: item
            for item in BookingEditHistory.objects.filter(booking=booking)
        }
        self.assertEqual(
            set(history_by_field),
            {"requestor_name", "budget_head_project_code", "departure_at"},
        )
        self.assertEqual(history_by_field["requestor_name"].old_value, "Old Requestor")
        self.assertEqual(history_by_field["requestor_name"].new_value, "New Requestor")
        self.assertEqual(
            history_by_field["budget_head_project_code"].old_value,
            "OLD-001",
        )
        self.assertEqual(
            history_by_field["budget_head_project_code"].new_value,
            "NEW-002",
        )
        self.assertIn("2026-07-01T18:30:00", history_by_field["departure_at"].new_value)

    def test_unchanged_submitted_value_does_not_create_history_row(self):
        booking = self.create_booking(
            self.room,
            utc_dt(2026, 7, 1, 10, 0),
            utc_dt(2026, 7, 1, 12, 0),
            purpose_of_visit="Same purpose",
        )

        response = self.client.patch(
            reverse("booking-edit", kwargs={"pk": booking.pk}),
            data={"purpose_of_visit": "Same purpose"},
            content_type="application/json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(BookingEditHistory.objects.filter(booking=booking).count(), 0)

    def test_created_by_and_edited_by_from_client_are_ignored_on_edit(self):
        other_user = create_user("other@example.com", "Other User")
        booking = self.create_booking(
            self.room,
            utc_dt(2026, 7, 1, 10, 0),
            utc_dt(2026, 7, 1, 12, 0),
            purpose_of_visit="Old purpose",
            created_by=self.user,
            created_by_name="Rishabh Kumar",
        )

        response = self.client.patch(
            reverse("booking-edit", kwargs={"pk": booking.pk}),
            data={
                "purpose_of_visit": "Updated purpose",
                "created_by_name": "Client Supplied Creator",
                "edited_by": other_user.id,
                "edited_by_name": "Client Supplied Editor",
            },
            content_type="application/json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        booking.refresh_from_db()
        self.assertEqual(booking.created_by_name, "Rishabh Kumar")

        history = BookingEditHistory.objects.get(booking=booking)
        self.assertEqual(history.edited_by, self.user)
        self.assertEqual(history.edited_by_name, "Rishabh Kumar")
        self.assertEqual(history.edited_by_email, self.user.email)

    def test_booking_detail_includes_edit_history_after_edit(self):
        booking = self.create_booking(
            self.room,
            utc_dt(2026, 7, 1, 10, 0),
            utc_dt(2026, 7, 1, 12, 0),
            purpose_of_visit="Old purpose",
        )
        self.client.patch(
            reverse("booking-edit", kwargs={"pk": booking.pk}),
            data={"purpose_of_visit": "New purpose"},
            content_type="application/json",
        )

        response = self.client.get(reverse("booking-detail", kwargs={"pk": booking.pk}))

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        history = response.json()["data"]["edit_history"]
        self.assertEqual(len(history), 1)
        self.assertEqual(history[0]["edited_by_name"], "Rishabh Kumar")
        self.assertEqual(history[0]["field_label"], "Purpose of Visit")
        self.assertEqual(history[0]["old_value"], "Old purpose")
        self.assertEqual(history[0]["new_value"], "New purpose")
        self.assertIn("edited_at", history[0])

    def test_bookings_endpoint_requires_authentication(self):
        self.client.defaults.pop("HTTP_AUTHORIZATION", None)

        response = self.client.get(reverse("booking-list"))

        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_bookings_endpoint_accepts_authenticated_request(self):
        response = self.client.get(reverse("booking-list"))

        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_availability_endpoint_requires_authentication(self):
        self.client.defaults.pop("HTTP_AUTHORIZATION", None)

        response = self.client.get(reverse("room-availability"))

        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_create_accepts_updated_attender_shifts_without_night_shift(self):
        response = self.client.post(
            reverse("booking-create"),
            data=self.valid_payload(
                room=self.room,
                arrival_at=utc_dt(2026, 7, 1, 10, 0),
                departure_at=utc_dt(2026, 7, 1, 12, 0),
                attender_required=True,
                attender_count_per_day=1,
                attender_day_shift=True,
            ),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        booking = Booking.objects.get(pk=response.json()["data"]["booking_id"])
        self.assertTrue(booking.attender_day_shift)

        detail = self.client.get(reverse("booking-detail", kwargs={"pk": booking.pk}))
        self.assertEqual(detail.status_code, status.HTTP_200_OK)
        self.assertTrue(detail.json()["data"]["attender_day_shift"])
        self.assertNotIn("attender_night_shift", detail.json()["data"])

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


class BookingRequestWorkflowTests(TestCase):
    def setUp(self):
        self.signal_sync = patch("bookings.signals.request_calendar_sync", return_value=True)
        self.signal_sync.start()
        self.addCleanup(self.signal_sync.stop)

        self.room = Room.objects.create(prefix="Delta", number="101", hostel_name="Main")
        self.other_room = Room.objects.create(prefix="Delta", number="102", hostel_name="Main")
        self.admin = create_user(email="admin@example.com", name="Admin One")
        self.requester = create_requester()
        self.other_requester = create_requester(
            email="other-requester@example.com",
            name="Requester Two",
        )

    def test_requester_cannot_access_admin_booking_apis(self):
        self.client.defaults["HTTP_AUTHORIZATION"] = bearer_token(self.requester)

        list_response = self.client.get(reverse("booking-list"))
        create_response = self.client.post(
            reverse("booking-create"),
            data=self.booking_payload(self.room),
            content_type="application/json",
        )

        self.assertEqual(list_response.status_code, status.HTTP_403_FORBIDDEN)
        self.assertEqual(create_response.status_code, status.HTTP_403_FORBIDDEN)

    def test_requester_can_access_safe_availability(self):
        self.client.defaults["HTTP_AUTHORIZATION"] = bearer_token(self.requester)

        response = self.client.get(
            reverse("requester-availability"),
            {"month": 7, "year": 2026},
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        day = response.json()["data"]["groups"][0]["calendar"][0]
        self.assertIn("available_rooms", day)
        self.assertNotIn("guest_name", day)
        self.assertNotIn("requestor_name", day)

    def test_unauthenticated_requester_availability_rejected(self):
        response = self.client.get(reverse("requester-availability"))
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_requester_can_access_safe_available_rooms_range(self):
        Booking.objects.create(
            room=self.room,
            arrival_at=local_dt(2026, 7, 3, 10, 0),
            departure_at=local_dt(2026, 7, 3, 12, 0),
            visitor_name="Private Visitor",
            requestor_name="Private Requestor",
            purpose_of_visit="Private Purpose",
            created_by=self.admin,
            created_by_name="Private Admin",
        )
        self.client.defaults["HTTP_AUTHORIZATION"] = bearer_token(self.requester)

        response = self.client.get(
            reverse("requester-available-rooms-range"),
            {
                "arrival_date": "2026-07-03",
                "departure_date": "2026-07-03",
                "prefix": "Delta",
            },
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.json()["data"]
        rooms = data["rooms"]
        by_id = {room["room_id"]: room for room in rooms}
        self.assertEqual(by_id[self.room.id]["availability_status"], "partial")
        self.assertIn("available_from_date", by_id[self.room.id])
        self.assertIn("available_from_time", by_id[self.room.id])
        self.assertEqual(by_id[self.other_room.id]["availability_status"], "available")
        private_payload = str(data)
        self.assertNotIn("Private Visitor", private_payload)
        self.assertNotIn("Private Requestor", private_payload)
        self.assertNotIn("Private Purpose", private_payload)
        self.assertNotIn("created_by", private_payload)
        self.assertNotIn("edit_history", private_payload)

    def test_requester_available_rooms_range_rejects_unauthenticated_and_pending(self):
        unauthenticated = self.client.get(
            reverse("requester-available-rooms-range"),
            {
                "arrival_date": "2026-07-03",
                "departure_date": "2026-07-03",
                "prefix": "Delta",
            },
        )
        self.assertEqual(unauthenticated.status_code, status.HTTP_401_UNAUTHORIZED)

        pending = create_requester(
            email="pending-requester@example.com",
            name="Pending Requester",
        )
        set_user_role(pending, ROLE_REQUESTER, approval_status=APPROVAL_PENDING)
        self.client.defaults["HTTP_AUTHORIZATION"] = bearer_token(pending)

        pending_response = self.client.get(
            reverse("requester-available-rooms-range"),
            {
                "arrival_date": "2026-07-03",
                "departure_date": "2026-07-03",
                "prefix": "Delta",
            },
        )

        self.assertEqual(pending_response.status_code, status.HTTP_403_FORBIDDEN)

    def test_requester_submits_request(self):
        self.client.defaults["HTTP_AUTHORIZATION"] = bearer_token(self.requester)

        response = self.client.post(
            reverse("requester-booking-request-list"),
            data=self.request_payload(),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(BookingRequest.objects.count(), 1)
        booking_request = BookingRequest.objects.get()
        self.assertEqual(booking_request.requester, self.requester)
        self.assertEqual(booking_request.status, BookingRequest.STATUS_PENDING)

    def test_requester_sees_only_own_requests(self):
        own_request = BookingRequest.objects.create(
            requester=self.requester,
            **self.request_model_kwargs(visitor_name="Own Visitor"),
        )
        BookingRequest.objects.create(
            requester=self.other_requester,
            **self.request_model_kwargs(visitor_name="Other Visitor"),
        )
        self.client.defaults["HTTP_AUTHORIZATION"] = bearer_token(self.requester)

        response = self.client.get(reverse("requester-booking-request-list"))

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        ids = [item["id"] for item in response.json()["data"]]
        self.assertEqual(ids, [own_request.id])

    def test_requester_can_soft_delete_own_request_for_all_statuses(self):
        statuses = [
            BookingRequest.STATUS_PENDING,
            BookingRequest.STATUS_CORRECTION_REQUIRED,
            BookingRequest.STATUS_APPROVED,
            BookingRequest.STATUS_REJECTED,
        ]
        self.client.defaults["HTTP_AUTHORIZATION"] = bearer_token(self.requester)

        for request_status in statuses:
            with self.subTest(request_status=request_status):
                booking_request = BookingRequest.objects.create(
                    requester=self.requester,
                    status=request_status,
                    **self.request_model_kwargs(visitor_name=f"Visitor {request_status}"),
                )

                response = self.client.delete(
                    reverse("requester-booking-request-delete", kwargs={"pk": booking_request.pk}),
                    data={"remarks": "No longer needed"},
                    content_type="application/json",
                )

                self.assertEqual(response.status_code, status.HTTP_200_OK)
                self.assertTrue(response.json()["success"])
                booking_request.refresh_from_db()
                self.assertTrue(booking_request.is_deleted)
                self.assertIsNotNone(booking_request.deleted_at)
                self.assertEqual(booking_request.deleted_by, self.requester)
                self.assertEqual(booking_request.deleted_by_name, "Requester One")
                self.assertEqual(booking_request.delete_reason, "No longer needed")

    def test_requester_cannot_delete_another_requesters_request(self):
        booking_request = BookingRequest.objects.create(
            requester=self.other_requester,
            **self.request_model_kwargs(),
        )
        self.client.defaults["HTTP_AUTHORIZATION"] = bearer_token(self.requester)

        response = self.client.delete(
            reverse("requester-booking-request-delete", kwargs={"pk": booking_request.pk})
        )

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
        self.assertTrue(BookingRequest.objects.filter(pk=booking_request.pk).exists())

    def test_requester_delete_hides_request_from_my_requests(self):
        booking_request = BookingRequest.objects.create(
            requester=self.requester,
            **self.request_model_kwargs(),
        )
        self.client.defaults["HTTP_AUTHORIZATION"] = bearer_token(self.requester)

        delete_response = self.client.delete(
            reverse("requester-booking-request-delete", kwargs={"pk": booking_request.pk})
        )
        list_response = self.client.get(reverse("requester-booking-request-list"))

        self.assertEqual(delete_response.status_code, status.HTTP_200_OK)
        self.assertEqual(list_response.status_code, status.HTTP_200_OK)
        self.assertEqual(list_response.json()["data"], [])

    def test_requester_delete_approved_request_keeps_real_booking(self):
        booking = Booking.objects.create(
            room=self.room,
            arrival_at=utc_dt(2026, 7, 1, 10, 0),
            departure_at=utc_dt(2026, 7, 1, 12, 0),
            visitor_name="Requester Approved Visitor",
        )
        booking_request = BookingRequest.objects.create(
            requester=self.requester,
            status=BookingRequest.STATUS_APPROVED,
            approved_booking=booking,
            **self.request_model_kwargs(visitor_name="Requester Approved Visitor"),
        )
        self.client.defaults["HTTP_AUTHORIZATION"] = bearer_token(self.requester)

        response = self.client.delete(
            reverse("requester-booking-request-delete", kwargs={"pk": booking_request.pk})
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        booking_request.refresh_from_db()
        self.assertTrue(booking_request.is_deleted)
        self.assertTrue(Booking.objects.filter(pk=booking.pk).exists())

    def test_requester_cannot_delete_already_deleted_request(self):
        booking_request = BookingRequest.objects.create(
            requester=self.requester,
            is_deleted=True,
            deleted_by=self.requester,
            deleted_at=utc_dt(2026, 7, 1, 13, 0),
            **self.request_model_kwargs(),
        )
        self.client.defaults["HTTP_AUTHORIZATION"] = bearer_token(self.requester)

        response = self.client.delete(
            reverse("requester-booking-request-delete", kwargs={"pk": booking_request.pk})
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("already deleted", response.json()["message"])

    def test_admin_cannot_use_requester_delete_endpoint(self):
        booking_request = BookingRequest.objects.create(
            requester=self.requester,
            **self.request_model_kwargs(),
        )
        self.client.defaults["HTTP_AUTHORIZATION"] = bearer_token(self.admin)

        response = self.client.delete(
            reverse("requester-booking-request-delete", kwargs={"pk": booking_request.pk})
        )

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        self.assertTrue(BookingRequest.objects.filter(pk=booking_request.pk).exists())

    def test_admin_can_soft_delete_request_for_all_statuses(self):
        statuses = [
            BookingRequest.STATUS_PENDING,
            BookingRequest.STATUS_CORRECTION_REQUIRED,
            BookingRequest.STATUS_APPROVED,
            BookingRequest.STATUS_REJECTED,
        ]
        self.client.defaults["HTTP_AUTHORIZATION"] = bearer_token(self.admin)

        for request_status in statuses:
            with self.subTest(request_status=request_status):
                booking_request = BookingRequest.objects.create(
                    requester=self.requester,
                    status=request_status,
                    **self.request_model_kwargs(visitor_name=f"Admin Delete {request_status}"),
                )

                response = self.client.delete(
                    reverse("admin-booking-request-delete", kwargs={"pk": booking_request.pk}),
                    data={"remarks": "Duplicate request"},
                    content_type="application/json",
                )

                self.assertEqual(response.status_code, status.HTTP_200_OK)
                booking_request.refresh_from_db()
                self.assertTrue(booking_request.is_deleted)
                self.assertIsNotNone(booking_request.deleted_at)
                self.assertEqual(booking_request.deleted_by, self.admin)
                self.assertEqual(booking_request.deleted_by_name, "Admin One")
                self.assertEqual(booking_request.deleted_by_role, ROLE_ADMIN)
                self.assertEqual(booking_request.delete_reason, "Duplicate request")
                self.assertTrue(response.json()["data"]["is_deleted"])
                self.assertEqual(response.json()["data"]["remarks"], "Duplicate request")

    def test_admin_delete_hides_request_from_normal_list(self):
        booking_request = BookingRequest.objects.create(
            requester=self.requester,
            **self.request_model_kwargs(),
        )
        self.client.defaults["HTTP_AUTHORIZATION"] = bearer_token(self.admin)

        delete_response = self.client.delete(
            reverse("admin-booking-request-delete", kwargs={"pk": booking_request.pk})
        )
        normal_list = self.client.get(reverse("admin-booking-request-list"))
        deleted_list = self.client.get(
            reverse("admin-booking-request-list"),
            {"deleted": "true"},
        )

        self.assertEqual(delete_response.status_code, status.HTTP_200_OK)
        self.assertEqual(normal_list.status_code, status.HTTP_200_OK)
        self.assertEqual(deleted_list.status_code, status.HTTP_200_OK)
        self.assertEqual(normal_list.json()["data"], [])
        self.assertEqual(deleted_list.json()["data"][0]["id"], booking_request.id)

    def test_admin_delete_approved_request_keeps_real_booking(self):
        booking = Booking.objects.create(
            room=self.room,
            arrival_at=utc_dt(2026, 7, 1, 10, 0),
            departure_at=utc_dt(2026, 7, 1, 12, 0),
            visitor_name="Approved Visitor",
        )
        booking_request = BookingRequest.objects.create(
            requester=self.requester,
            status=BookingRequest.STATUS_APPROVED,
            approved_booking=booking,
            **self.request_model_kwargs(visitor_name="Approved Visitor"),
        )
        self.client.defaults["HTTP_AUTHORIZATION"] = bearer_token(self.admin)

        response = self.client.delete(
            reverse("admin-booking-request-delete", kwargs={"pk": booking_request.pk})
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        booking_request.refresh_from_db()
        self.assertTrue(booking_request.is_deleted)
        self.assertTrue(Booking.objects.filter(pk=booking.pk).exists())

    def test_admin_delete_endpoint_rejects_requester_and_unauthenticated(self):
        booking_request = BookingRequest.objects.create(
            requester=self.requester,
            **self.request_model_kwargs(),
        )

        unauthenticated = self.client.delete(
            reverse("admin-booking-request-delete", kwargs={"pk": booking_request.pk})
        )

        self.client.defaults["HTTP_AUTHORIZATION"] = bearer_token(self.requester)
        requester_response = self.client.delete(
            reverse("admin-booking-request-delete", kwargs={"pk": booking_request.pk})
        )

        self.assertEqual(unauthenticated.status_code, status.HTTP_401_UNAUTHORIZED)
        self.assertEqual(requester_response.status_code, status.HTTP_403_FORBIDDEN)

    def test_admin_cannot_delete_already_deleted_request(self):
        booking_request = BookingRequest.objects.create(
            requester=self.requester,
            is_deleted=True,
            deleted_by=self.admin,
            deleted_at=utc_dt(2026, 7, 1, 13, 0),
            **self.request_model_kwargs(),
        )
        self.client.defaults["HTTP_AUTHORIZATION"] = bearer_token(self.admin)

        response = self.client.delete(
            reverse("admin-booking-request-delete", kwargs={"pk": booking_request.pk})
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("already deleted", response.json()["message"])

    def test_requester_can_edit_own_pending_request(self):
        booking_request = BookingRequest.objects.create(
            requester=self.requester,
            **self.request_model_kwargs(visitor_name="Original Visitor"),
        )
        self.client.defaults["HTTP_AUTHORIZATION"] = bearer_token(self.requester)

        response = self.client.patch(
            reverse("requester-booking-request-detail", kwargs={"pk": booking_request.pk}),
            data={
                "visitor_name": "Edited Visitor",
                "purpose_of_visit": "Edited purpose",
                "requestor_department": "Edited Department",
            },
            content_type="application/json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        booking_request.refresh_from_db()
        self.assertEqual(booking_request.visitor_name, "Edited Visitor")
        self.assertEqual(booking_request.purpose_of_visit, "Edited purpose")
        self.assertEqual(booking_request.requestor_department, "Edited Department")

    def test_requester_cannot_edit_another_requesters_request(self):
        booking_request = BookingRequest.objects.create(
            requester=self.other_requester,
            **self.request_model_kwargs(),
        )
        self.client.defaults["HTTP_AUTHORIZATION"] = bearer_token(self.requester)

        response = self.client.patch(
            reverse("requester-booking-request-detail", kwargs={"pk": booking_request.pk}),
            data={"visitor_name": "Edited Visitor"},
            content_type="application/json",
        )

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_requester_cannot_edit_reviewed_request(self):
        booking_request = BookingRequest.objects.create(
            requester=self.requester,
            status=BookingRequest.STATUS_APPROVED,
            reviewed_by=self.admin,
            reviewed_at=utc_dt(2026, 7, 1, 13, 0),
            **self.request_model_kwargs(),
        )
        self.client.defaults["HTTP_AUTHORIZATION"] = bearer_token(self.requester)

        response = self.client.patch(
            reverse("requester-booking-request-detail", kwargs={"pk": booking_request.pk}),
            data={"visitor_name": "Edited Visitor"},
            content_type="application/json",
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("Only pending", response.json()["message"])

    def test_admin_cannot_use_requester_edit_endpoint(self):
        booking_request = BookingRequest.objects.create(
            requester=self.requester,
            **self.request_model_kwargs(),
        )
        self.client.defaults["HTTP_AUTHORIZATION"] = bearer_token(self.admin)

        response = self.client.patch(
            reverse("requester-booking-request-detail", kwargs={"pk": booking_request.pk}),
            data={"visitor_name": "Edited Visitor"},
            content_type="application/json",
        )

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_admin_can_list_pending_requests(self):
        booking_request = BookingRequest.objects.create(
            requester=self.requester,
            **self.request_model_kwargs(),
        )
        self.client.defaults["HTTP_AUTHORIZATION"] = bearer_token(self.admin)

        response = self.client.get(
            reverse("admin-booking-request-list"),
            {"status": BookingRequest.STATUS_PENDING},
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.json()["data"][0]["id"], booking_request.id)

    def test_admin_approve_creates_booking(self):
        booking_request = BookingRequest.objects.create(
            requester=self.requester,
            **self.request_model_kwargs(),
        )
        self.client.defaults["HTTP_AUTHORIZATION"] = bearer_token(self.admin)

        response = self.client.post(
            reverse("admin-booking-request-approve", kwargs={"pk": booking_request.pk}),
            data={"room": self.room.id, "remarks": "Approved."},
            content_type="application/json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        booking_request.refresh_from_db()
        self.assertEqual(booking_request.status, BookingRequest.STATUS_APPROVED)
        self.assertEqual(booking_request.reviewed_by, self.admin)
        self.assertIsNotNone(booking_request.approved_booking)
        self.assertEqual(booking_request.approved_booking.room, self.room)
        self.assertEqual(booking_request.approved_booking.created_by, self.admin)

    def test_admin_approve_can_use_create_booking_form_overrides(self):
        booking_request = BookingRequest.objects.create(
            requester=self.requester,
            **self.request_model_kwargs(
                visitor_name="Original Visitor",
                purpose_of_visit="Original purpose",
                requestor_name="Original Requestor",
            ),
        )
        self.client.defaults["HTTP_AUTHORIZATION"] = bearer_token(self.admin)

        response = self.client.post(
            reverse("admin-booking-request-approve", kwargs={"pk": booking_request.pk}),
            data={
                "room": self.room.id,
                "remarks": "Approved from form.",
                "visitor_name": "Edited Visitor",
                "purpose_of_visit": "Edited purpose",
                "requestor_name": "Edited Requestor",
                "requestor_department": "Edited Department",
                "room_charges_status": Booking.CHARGE_STATUS_YES,
                "room_charges_amount": "1200",
            },
            content_type="application/json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        booking_request.refresh_from_db()
        booking = booking_request.approved_booking
        self.assertIsNotNone(booking)
        self.assertEqual(booking.visitor_name, "Edited Visitor")
        self.assertEqual(booking.purpose_of_visit, "Edited purpose")
        self.assertEqual(booking.requestor_name, "Edited Requestor")
        self.assertEqual(booking.requestor_department, "Edited Department")
        self.assertEqual(booking.room_charges_status, Booking.CHARGE_STATUS_YES)
        self.assertEqual(str(booking.room_charges_amount), "1200.00")

    def test_admin_reject_does_not_create_booking(self):
        booking_request = BookingRequest.objects.create(
            requester=self.requester,
            **self.request_model_kwargs(),
        )
        self.client.defaults["HTTP_AUTHORIZATION"] = bearer_token(self.admin)

        response = self.client.post(
            reverse("admin-booking-request-reject", kwargs={"pk": booking_request.pk}),
            data={"remarks": "Room not available."},
            content_type="application/json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        booking_request.refresh_from_db()
        self.assertEqual(booking_request.status, BookingRequest.STATUS_REJECTED)
        self.assertIsNone(booking_request.approved_booking)
        self.assertEqual(Booking.objects.count(), 0)

    def test_admin_can_send_back_pending_request_for_correction(self):
        booking_request = BookingRequest.objects.create(
            requester=self.requester,
            **self.request_model_kwargs(),
        )
        self.client.defaults["HTTP_AUTHORIZATION"] = bearer_token(self.admin)

        response = self.client.post(
            reverse("admin-booking-request-send-back", kwargs={"pk": booking_request.pk}),
            data={"remarks": "Correction required. Please update visitor mobile."},
            content_type="application/json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        booking_request.refresh_from_db()
        self.assertEqual(booking_request.status, BookingRequest.STATUS_CORRECTION_REQUIRED)
        self.assertEqual(booking_request.reviewed_by, self.admin)
        self.assertIsNotNone(booking_request.reviewed_at)
        self.assertEqual(
            booking_request.admin_remarks,
            "Correction required. Please update visitor mobile.",
        )
        self.assertIsNone(booking_request.approved_booking)
        self.assertEqual(response.json()["data"]["status"], BookingRequest.STATUS_CORRECTION_REQUIRED)

    def test_send_back_requires_remarks(self):
        booking_request = BookingRequest.objects.create(
            requester=self.requester,
            **self.request_model_kwargs(),
        )
        self.client.defaults["HTTP_AUTHORIZATION"] = bearer_token(self.admin)

        response = self.client.post(
            reverse("admin-booking-request-send-back", kwargs={"pk": booking_request.pk}),
            data={"remarks": ""},
            content_type="application/json",
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        booking_request.refresh_from_db()
        self.assertEqual(booking_request.status, BookingRequest.STATUS_PENDING)

    def test_requester_cannot_send_back_request(self):
        booking_request = BookingRequest.objects.create(
            requester=self.requester,
            **self.request_model_kwargs(),
        )
        self.client.defaults["HTTP_AUTHORIZATION"] = bearer_token(self.requester)

        response = self.client.post(
            reverse("admin-booking-request-send-back", kwargs={"pk": booking_request.pk}),
            data={"remarks": "Needs correction."},
            content_type="application/json",
        )

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_unauthenticated_user_cannot_send_back_request(self):
        booking_request = BookingRequest.objects.create(
            requester=self.requester,
            **self.request_model_kwargs(),
        )

        response = self.client.post(
            reverse("admin-booking-request-send-back", kwargs={"pk": booking_request.pk}),
            data={"remarks": "Needs correction."},
            content_type="application/json",
        )

        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_admin_cannot_send_back_reviewed_request(self):
        approved_request = BookingRequest.objects.create(
            requester=self.requester,
            status=BookingRequest.STATUS_APPROVED,
            reviewed_by=self.admin,
            reviewed_at=utc_dt(2026, 7, 1, 13, 0),
            **self.request_model_kwargs(),
        )
        rejected_request = BookingRequest.objects.create(
            requester=self.requester,
            status=BookingRequest.STATUS_REJECTED,
            reviewed_by=self.admin,
            reviewed_at=utc_dt(2026, 7, 1, 13, 0),
            **self.request_model_kwargs(visitor_name="Rejected Visitor"),
        )
        self.client.defaults["HTTP_AUTHORIZATION"] = bearer_token(self.admin)

        approved_response = self.client.post(
            reverse("admin-booking-request-send-back", kwargs={"pk": approved_request.pk}),
            data={"remarks": "Needs correction."},
            content_type="application/json",
        )
        rejected_response = self.client.post(
            reverse("admin-booking-request-send-back", kwargs={"pk": rejected_request.pk}),
            data={"remarks": "Needs correction."},
            content_type="application/json",
        )

        self.assertEqual(approved_response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(rejected_response.status_code, status.HTTP_400_BAD_REQUEST)
        approved_request.refresh_from_db()
        rejected_request.refresh_from_db()
        self.assertEqual(approved_request.status, BookingRequest.STATUS_APPROVED)
        self.assertEqual(rejected_request.status, BookingRequest.STATUS_REJECTED)

    def test_requester_can_resubmit_correction_required_request(self):
        booking_request = BookingRequest.objects.create(
            requester=self.requester,
            status=BookingRequest.STATUS_CORRECTION_REQUIRED,
            reviewed_by=self.admin,
            reviewed_at=utc_dt(2026, 7, 1, 13, 0),
            admin_remarks="Update mobile.",
            **self.request_model_kwargs(visitor_mobile="9876543210"),
        )
        self.client.defaults["HTTP_AUTHORIZATION"] = bearer_token(self.requester)

        response = self.client.patch(
            reverse("requester-booking-request-detail", kwargs={"pk": booking_request.pk}),
            data={
                "visitor_mobile": "9123456789",
                "purpose_of_visit": "Corrected purpose",
            },
            content_type="application/json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        booking_request.refresh_from_db()
        self.assertEqual(booking_request.status, BookingRequest.STATUS_PENDING)
        self.assertIsNone(booking_request.reviewed_by)
        self.assertIsNone(booking_request.reviewed_at)
        self.assertEqual(booking_request.visitor_mobile, "9123456789")
        self.assertEqual(booking_request.purpose_of_visit, "Corrected purpose")
        self.assertEqual(booking_request.admin_remarks, "Update mobile.")
        self.assertEqual(response.json()["data"]["status"], BookingRequest.STATUS_PENDING)

    def test_admin_can_approve_after_requester_resubmits(self):
        booking_request = BookingRequest.objects.create(
            requester=self.requester,
            status=BookingRequest.STATUS_CORRECTION_REQUIRED,
            reviewed_by=self.admin,
            reviewed_at=utc_dt(2026, 7, 1, 13, 0),
            admin_remarks="Update purpose.",
            **self.request_model_kwargs(),
        )
        self.client.defaults["HTTP_AUTHORIZATION"] = bearer_token(self.requester)
        resubmit_response = self.client.patch(
            reverse("requester-booking-request-detail", kwargs={"pk": booking_request.pk}),
            data={"purpose_of_visit": "Corrected purpose"},
            content_type="application/json",
        )
        self.assertEqual(resubmit_response.status_code, status.HTTP_200_OK)

        self.client.defaults["HTTP_AUTHORIZATION"] = bearer_token(self.admin)
        approve_response = self.client.post(
            reverse("admin-booking-request-approve", kwargs={"pk": booking_request.pk}),
            data={"room": self.room.id, "remarks": "Approved after correction."},
            content_type="application/json",
        )

        self.assertEqual(approve_response.status_code, status.HTTP_200_OK)
        booking_request.refresh_from_db()
        self.assertEqual(booking_request.status, BookingRequest.STATUS_APPROVED)
        self.assertIsNotNone(booking_request.approved_booking)

    def test_approve_rechecks_availability(self):
        booking_request = BookingRequest.objects.create(
            requester=self.requester,
            **self.request_model_kwargs(),
        )
        Booking.objects.create(
            room=self.room,
            arrival_at=booking_request.arrival_at,
            departure_at=booking_request.departure_at,
            visitor_name="Conflicting Visitor",
        )
        self.client.defaults["HTTP_AUTHORIZATION"] = bearer_token(self.admin)

        response = self.client.post(
            reverse("admin-booking-request-approve", kwargs={"pk": booking_request.pk}),
            data={"room": self.room.id, "remarks": "Approved."},
            content_type="application/json",
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("no longer available", response.json()["message"])
        booking_request.refresh_from_db()
        self.assertEqual(booking_request.status, BookingRequest.STATUS_PENDING)
        self.assertIsNone(booking_request.approved_booking)

    def request_payload(self, **overrides):
        payload = {
            "arrival_at": iso(utc_dt(2026, 7, 1, 10, 0)),
            "departure_at": iso(utc_dt(2026, 7, 1, 12, 0)),
            "preferred_prefix": "Delta",
            "visitor_name": "Requester Visitor",
            "visitor_mobile": "9876543210",
            "visitor_category": Booking.VISITOR_CATEGORY_INSTITUTE,
            "purpose_of_visit": "Official visit",
            "requestor_name": "Requester One",
            "requestor_email": "requester@example.com",
        }
        payload.update(overrides)
        return payload

    def request_model_kwargs(self, **overrides):
        data = {
            "arrival_at": utc_dt(2026, 7, 1, 10, 0),
            "departure_at": utc_dt(2026, 7, 1, 12, 0),
            "preferred_prefix": "Delta",
            "visitor_name": "Requester Visitor",
            "visitor_mobile": "9876543210",
            "visitor_category": Booking.VISITOR_CATEGORY_INSTITUTE,
            "purpose_of_visit": "Official visit",
            "requestor_name": "Requester One",
            "requestor_email": "requester@example.com",
        }
        data.update(overrides)
        return data

    def booking_payload(self, room):
        return {
            "room": room.id,
            "arrival_at": iso(utc_dt(2026, 7, 1, 10, 0)),
            "departure_at": iso(utc_dt(2026, 7, 1, 12, 0)),
            "visitor_name": "Visitor One",
            "visitor_mobile": "9876543210",
            "visitor_category": Booking.VISITOR_CATEGORY_INSTITUTE,
        }


class BackendOperationalTests(TestCase):
    def test_health_check_returns_request_id_header(self):
        response = self.client.get(
            reverse("health-check"),
            HTTP_X_REQUEST_ID="test-request-id",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response["X-Request-ID"], "test-request-id")
        self.assertTrue(response.json()["success"])
        self.assertEqual(response.json()["data"]["database"], "ok")


def utc_dt(year, month, day, hour, minute):
    return datetime(year, month, day, hour, minute, tzinfo=datetime_timezone.utc)


def local_dt(year, month, day, hour, minute):
    return datetime(year, month, day, hour, minute, tzinfo=INDIA_TZ)


def iso(value):
    return value.isoformat()
