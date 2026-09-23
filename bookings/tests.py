from datetime import datetime, timedelta, timezone as datetime_timezone
from unittest.mock import patch
from zoneinfo import ZoneInfo

from django.core import mail
from django.core.cache import cache
from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone
from django.utils.dateparse import parse_datetime
from rest_framework import status
from rest_framework.throttling import ScopedRateThrottle
from rest_framework_simplejwt.tokens import RefreshToken

from accounts.roles import APPROVAL_APPROVED, APPROVAL_PENDING, ROLE_ADMIN, ROLE_REQUESTER, set_user_role
from hostels.models import Room

from .models import Booking, BookingChargeSheet, BookingEditHistory, BookingRequest, BookingShare
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

    def test_create_allows_arrival_at_cooling_boundary(self):
        self.create_booking(
            self.room,
            utc_dt(2026, 7, 1, 8, 0),
            utc_dt(2026, 7, 1, 10, 0),
        )

        response = self.client.post(
            reverse("booking-create"),
            data=self.valid_payload(
                room=self.room,
                arrival_at=utc_dt(2026, 7, 1, 11, 0),
                departure_at=utc_dt(2026, 7, 1, 12, 0),
            ),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertTrue(response.json()["success"])

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

    def test_create_rejects_departure_too_close_before_next_booking(self):
        self.create_booking(
            self.room,
            utc_dt(2026, 7, 1, 12, 0),
            utc_dt(2026, 7, 1, 14, 0),
        )

        response = self.client.post(
            reverse("booking-create"),
            data=self.valid_payload(
                room=self.room,
                arrival_at=utc_dt(2026, 7, 1, 9, 0),
                departure_at=utc_dt(2026, 7, 1, 11, 30),
            ),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertFalse(response.json()["success"])
        self.assertIn("1-hour gap", response.json()["message"])

    def test_create_allows_departure_at_next_booking_cooling_boundary(self):
        self.create_booking(
            self.room,
            utc_dt(2026, 7, 1, 12, 0),
            utc_dt(2026, 7, 1, 14, 0),
        )

        response = self.client.post(
            reverse("booking-create"),
            data=self.valid_payload(
                room=self.room,
                arrival_at=utc_dt(2026, 7, 1, 9, 0),
                departure_at=utc_dt(2026, 7, 1, 11, 0),
            ),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertTrue(response.json()["success"])

    def test_update_moving_booking_to_occupied_room_is_rejected(self):
        booking = self.create_booking(
            self.room,
            utc_dt(2026, 9, 1, 8, 0),
            utc_dt(2026, 9, 1, 9, 0),
        )
        self.create_booking(
            self.other_room,
            utc_dt(2026, 9, 1, 12, 0),
            utc_dt(2026, 9, 1, 13, 0),
        )

        response = self.client.patch(
            reverse("booking-edit", kwargs={"pk": booking.pk}),
            data={
                "room": self.other_room.id,
                "arrival_at": iso(utc_dt(2026, 9, 1, 12, 30)),
                "departure_at": iso(utc_dt(2026, 9, 1, 13, 30)),
            },
            content_type="application/json",
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("already booked", response.json()["message"])
        booking.refresh_from_db()
        self.assertEqual(booking.room_id, self.room.id)

    def test_update_rejects_departure_too_close_before_next_booking(self):
        booking = self.create_booking(
            self.room,
            utc_dt(2026, 9, 1, 9, 0),
            utc_dt(2026, 9, 1, 10, 0),
        )
        self.create_booking(
            self.room,
            utc_dt(2026, 9, 1, 12, 0),
            utc_dt(2026, 9, 1, 14, 0),
        )

        response = self.client.patch(
            reverse("booking-edit", kwargs={"pk": booking.pk}),
            data={"departure_at": iso(utc_dt(2026, 9, 1, 11, 30))},
            content_type="application/json",
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertFalse(response.json()["success"])
        self.assertIn("1-hour gap", response.json()["message"])
        booking.refresh_from_db()
        self.assertEqual(booking.departure_at, utc_dt(2026, 9, 1, 10, 0))

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

    def test_delete_booking_soft_deletes_linked_approved_request(self):
        requester = create_requester(
            email="source-request-delete@example.com",
            name="Source Requester",
        )
        booking = self.create_booking(
            self.room,
            utc_dt(2026, 7, 1, 10, 0),
            utc_dt(2026, 7, 1, 12, 0),
        )
        booking_request = BookingRequest.objects.create(
            requester=requester,
            status=BookingRequest.STATUS_APPROVED,
            arrival_at=booking.arrival_at,
            departure_at=booking.departure_at,
            preferred_prefix=booking.room.prefix,
            preferred_room=booking.room,
            visitor_name="Source Request Visitor",
            requestor_name="Source Requester",
            approved_booking=booking,
        )

        response = self.client.delete(reverse("booking-delete", kwargs={"pk": booking.pk}))

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertFalse(Booking.objects.filter(pk=booking.pk).exists())
        booking_request.refresh_from_db()
        self.assertTrue(booking_request.is_deleted)
        self.assertIsNotNone(booking_request.deleted_at)
        self.assertEqual(booking_request.deleted_by, self.user)
        self.assertEqual(booking_request.deleted_by_name, self.user.get_full_name() or self.user.email)
        self.assertEqual(booking_request.delete_reason, "Linked booking was deleted by admin.")

        normal_list = self.client.get(reverse("admin-booking-request-list"))
        self.assertEqual(normal_list.status_code, status.HTTP_200_OK)
        normal_ids = [item["id"] for item in normal_list.json()["data"]]
        self.assertNotIn(booking_request.id, normal_ids)

        deleted_list = self.client.get(reverse("admin-booking-request-list"), {"deleted": "true"})
        self.assertEqual(deleted_list.status_code, status.HTTP_200_OK)
        deleted_ids = [item["id"] for item in deleted_list.json()["data"]]
        self.assertIn(booking_request.id, deleted_ids)

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
        self.assertEqual(
            first.json()["data"]["booking_reference_number"],
            second.json()["data"]["booking_reference_number"],
        )

    def test_create_generates_six_digit_booking_reference_number(self):
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
        reference_number = response.json()["data"]["booking_reference_number"]
        self.assertRegex(reference_number, r"^\d{6}$")
        self.assertEqual(booking.booking_reference_number, reference_number)

    @override_settings(EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend")
    def test_create_mail_template_creates_booking_without_sending_email(self):
        response = self.client.post(
            reverse("booking-create-mail-template"),
            data=self.valid_payload(
                room=self.room,
                arrival_at=utc_dt(2026, 9, 11, 4, 0),
                departure_at=utc_dt(2026, 9, 12, 5, 0),
                visitor_name="Mr. Amit Chauhan",
            ),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(Booking.objects.count(), 1)
        data = response.json()["data"]
        self.assertIn("mail_template", data)
        self.assertIn("Accommodation details", data["mail_template"]["subject"])
        self.assertIn("Dear CCPS Team", data["mail_template"]["body"])
        self.assertIn("Mr. Amit Chauhan", data["mail_template"]["body"])
        self.assertIn("Rishabh Kumar", data["mail_template"]["body"])
        self.assertIn("Rishabh Kumar", data["mail_template"]["html"])
        self.assertNotIn("Hemant Verma", data["mail_template"]["body"])
        self.assertEqual(len(getattr(mail, "outbox", [])), 0)

    def test_existing_booking_mail_template_returns_template_without_creating_booking(self):
        booking = self.create_booking(
            self.room,
            utc_dt(2026, 9, 11, 4, 0),
            utc_dt(2026, 9, 12, 5, 0),
            visitor_name="Mr. Amit Chauhan",
        )

        response = self.client.get(reverse("booking-mail-template", kwargs={"pk": booking.pk}))

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(Booking.objects.count(), 1)
        data = response.json()["data"]
        self.assertIn("Accommodation details", data["subject"])
        self.assertIn("Rishabh Kumar", data["body"])
        self.assertIn("Rishabh Kumar", data["html"])
        self.assertNotIn("Hemant Verma", data["body"])
        self.assertIn("Dear CCPS Team", data["body"])
        self.assertIn("Mr. Amit Chauhan", data["body"])
        self.assertIn("<table", data["html"])

    def test_bulk_booking_mail_template_returns_combined_template(self):
        first = self.create_booking(
            self.room,
            utc_dt(2026, 9, 11, 4, 0),
            utc_dt(2026, 9, 12, 5, 0),
            visitor_name="Mr. Amit Chauhan",
        )
        second = self.create_booking(
            self.other_room,
            utc_dt(2026, 9, 11, 4, 0),
            utc_dt(2026, 9, 12, 5, 0),
            visitor_name="Ms. Anu Singh",
        )

        response = self.client.post(
            reverse("booking-mail-template-bulk"),
            data={"booking_ids": [first.pk, second.pk]},
            content_type="application/json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.json()["data"]
        self.assertIn("2 bookings", data["subject"])
        self.assertIn("Mr. Amit Chauhan", data["body"])
        self.assertIn("Ms. Anu Singh", data["body"])
        self.assertIn("Mr. Amit Chauhan", data["html"])
        self.assertIn("Ms. Anu Singh", data["html"])
        self.assertIn("Rishabh Kumar", data["body"])
        self.assertIn("Total", data["body"])
        self.assertIn("<table", data["html"])

    def test_bulk_booking_mail_template_rejects_empty_selection(self):
        response = self.client.post(
            reverse("booking-mail-template-bulk"),
            data={"booking_ids": []},
            content_type="application/json",
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertFalse(response.json()["success"])
        self.assertIn("Select at least one booking", response.json()["message"])

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
                remarks="Needs wheelchair access.",
            ),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        booking = Booking.objects.get(pk=response.json()["data"]["booking_id"])
        self.assertEqual(booking.created_by, self.user)
        self.assertEqual(booking.created_by_name, "Rishabh Kumar")
        self.assertEqual(booking.remarks, "Needs wheelchair access.")
        self.assertEqual(response.json()["data"]["remarks"], "Needs wheelchair access.")

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
        self.assertRegex(data["booking_reference_number"], r"^\d{6}$")
        self.assertEqual(data["booking_reference_number"], booking.booking_reference_number)
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
        self.assertEqual(result["booking_reference_number"], booking.booking_reference_number)
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
            utc_dt(2026, 9, 1, 10, 0),
            utc_dt(2026, 9, 1, 12, 0),
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
            utc_dt(2026, 9, 1, 10, 0),
            utc_dt(2026, 9, 1, 12, 0),
            requestor_name="Old Requestor",
            budget_head_project_code="OLD-001",
        )

        response = self.client.patch(
            reverse("booking-edit", kwargs={"pk": booking.pk}),
            data={
                "requestor_name": "New Requestor",
                "budget_head_project_code": "NEW-002",
                "departure_at": iso(utc_dt(2026, 9, 1, 13, 0)),
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
        self.assertIn("2026-09-01T18:30:00", history_by_field["departure_at"].new_value)

    def test_unchanged_submitted_value_does_not_create_history_row(self):
        booking = self.create_booking(
            self.room,
            utc_dt(2026, 9, 1, 10, 0),
            utc_dt(2026, 9, 1, 12, 0),
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
            utc_dt(2026, 9, 1, 10, 0),
            utc_dt(2026, 9, 1, 12, 0),
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
            utc_dt(2026, 9, 1, 10, 0),
            utc_dt(2026, 9, 1, 12, 0),
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

    def test_expired_booking_edit_is_allowed_and_delete_is_allowed(self):
        booking = self.create_booking(
            self.room,
            utc_dt(2026, 7, 1, 10, 0),
            utc_dt(2026, 7, 1, 12, 0),
            purpose_of_visit="Old purpose",
        )

        response = self.client.patch(
            reverse("booking-edit", kwargs={"pk": booking.pk}),
            data={"purpose_of_visit": "New purpose"},
            content_type="application/json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        booking.refresh_from_db()
        self.assertEqual(booking.purpose_of_visit, "New purpose")
        self.assertEqual(
            BookingEditHistory.objects.filter(
                booking=booking,
                field_name="purpose_of_visit",
                old_value="Old purpose",
                new_value="New purpose",
            ).count(),
            1,
        )

        delete_response = self.client.delete(reverse("booking-delete", kwargs={"pk": booking.pk}))

        self.assertEqual(delete_response.status_code, status.HTTP_200_OK)
        self.assertFalse(Booking.objects.filter(pk=booking.pk).exists())

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

    def test_create_accepts_attender_shifts_without_count_or_night_shift(self):
        response = self.client.post(
            reverse("booking-create"),
            data=self.valid_payload(
                room=self.room,
                arrival_at=utc_dt(2026, 7, 1, 10, 0),
                departure_at=utc_dt(2026, 7, 1, 12, 0),
                attender_required=True,
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
        self.assertNotIn("attender_count_per_day", detail.json()["data"])
        self.assertNotIn("attender_night_shift", detail.json()["data"])

    def test_backdated_create_is_expired_and_visible_in_expired_list(self):
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
        self.assertEqual(response.json()["data"]["status"], Booking.STATUS_EXPIRED)
        booking = Booking.objects.get(pk=response.json()["data"]["booking_id"])
        self.assertEqual(booking.status, Booking.STATUS_EXPIRED)

        active_response = self.client.get(reverse("booking-list"), {"status": Booking.STATUS_ACTIVE})
        expired_response = self.client.get(reverse("booking-list"), {"status": Booking.STATUS_EXPIRED})

        self.assertEqual(active_response.status_code, status.HTTP_200_OK)
        self.assertEqual(expired_response.status_code, status.HTTP_200_OK)
        active_ids = [item["id"] for item in active_response.json()["data"]["results"]]
        expired_ids = [item["id"] for item in expired_response.json()["data"]["results"]]
        self.assertNotIn(booking.id, active_ids)
        self.assertIn(booking.id, expired_ids)

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

    def test_available_rooms_by_date_excludes_room_when_cooling_runs_past_6pm(self):
        self.create_booking(
            self.room,
            local_dt(2026, 7, 3, 10, 0),
            local_dt(2026, 7, 3, 12, 0),
        )
        self.create_booking(
            self.other_room,
            local_dt(2026, 7, 3, 15, 0),
            local_dt(2026, 7, 3, 17, 30),
        )

        response = self.client.get(
            reverse("room-available-rooms"),
            {"date": "2026-07-03", "prefix": "Beta"},
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        rooms = response.json()["data"]["rooms"]
        by_id = {room["room_id"]: room for room in rooms}
        self.assertEqual(by_id[self.room.id]["availability_status"], "partial")
        self.assertNotIn(self.other_room.id, by_id)

    def test_available_rooms_range_excludes_room_when_cooling_runs_past_6pm(self):
        self.create_booking(
            self.room,
            local_dt(2026, 7, 3, 15, 0),
            local_dt(2026, 7, 3, 17, 30),
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
        by_id = {room["room_id"]: room for room in response.json()["data"]["rooms"]}
        self.assertNotIn(self.room.id, by_id)
        self.assertEqual(by_id[self.other_room.id]["availability_status"], "available")

    def test_available_rooms_range_marks_multiday_departure_day_partial(self):
        self.create_booking(
            self.room,
            local_dt(2026, 7, 1, 10, 0),
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
        by_id = {room["room_id"]: room for room in response.json()["data"]["rooms"]}
        self.assertEqual(by_id[self.room.id]["availability_status"], "partial")
        self.assertEqual(by_id[self.room.id]["available_from_time"], "01:00 PM")

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


class BookingShareApiTests(TestCase):
    def setUp(self):
        self.admin = create_user("admin-share@example.com", "Admin Share")
        self.requester = create_requester("requester-share@example.com", "Requester Share")
        self.room = Room.objects.create(prefix="Beta", number="201", hostel_name="Main")
        self.booking = Booking.objects.create(
            room=self.room,
            arrival_at=local_dt(2026, 7, 1, 10, 0),
            departure_at=local_dt(2026, 7, 1, 12, 0),
            visitor_name="Shared Visitor",
            visitor_organisation="Shared Organisation",
            requestor_name="Shared Requestor",
            status=Booking.STATUS_ACTIVE,
        )
        BookingChargeSheet.objects.update_or_create(
            booking=self.booking,
            defaults={
                "requestor_name": "Shared Requestor",
                "guest_name": "Shared Visitor",
                "purpose_event": "Shared Event",
                "room_charges_amount": 200,
                "attender_charges_amount": 50,
                "budget_head_name": "Shared Budget",
            },
        )

    def assert_expires_between(self, expires_at_value, minimum_delta, maximum_delta):
        parsed = parse_datetime(expires_at_value)
        self.assertIsNotNone(parsed)
        now = timezone.now()
        self.assertGreater(parsed, now + minimum_delta)
        self.assertLess(parsed, now + maximum_delta)

    def test_admin_can_create_booking_sheet_share_link(self):
        self.client.defaults["HTTP_AUTHORIZATION"] = bearer_token(self.admin)

        response = self.client.post(
            reverse("booking-share-create"),
            data={
                "share_type": BookingShare.SHARE_TYPE_BOOKING_SHEET,
                "filters": {
                    "prefix": "Beta",
                    "status": Booking.STATUS_ACTIVE,
                    "arrival_from": "2026-07-01",
                    "departure_to": "2026-07-31",
                },
            },
            content_type="application/json",
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        data = response.json()["data"]
        self.assertIn("/web/share/bookings/", data["url"])
        share = BookingShare.objects.get(token=data["token"])
        self.assertEqual(share.created_by, self.admin)
        self.assertIsNotNone(share.expires_at)
        self.assertEqual(share.filters["prefix"], "Beta")
        self.assertEqual(share.filters["status"], Booking.STATUS_ACTIVE)
        self.assert_expires_between(data["expires_at"], timedelta(days=6), timedelta(days=8))

    def test_admin_can_create_charge_sheet_share_link_with_one_month_validity(self):
        self.client.defaults["HTTP_AUTHORIZATION"] = bearer_token(self.admin)

        response = self.client.post(
            reverse("booking-share-create"),
            data={
                "share_type": BookingShare.SHARE_TYPE_CHARGE_SHEET,
                "validity": "1m",
                "filters": {
                    "prefix": "Beta",
                    "payment": "pending",
                    "checkout_from": "2026-07-01",
                    "checkout_to": "2026-07-31",
                    "search": "Shared",
                    "ordering": "-created_at",
                },
            },
            content_type="application/json",
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        data = response.json()["data"]
        self.assertIn("/web/share/charges/", data["url"])
        share = BookingShare.objects.get(token=data["token"])
        self.assertEqual(share.share_type, BookingShare.SHARE_TYPE_CHARGE_SHEET)
        self.assertEqual(share.title, "Charges Sheet")
        self.assertEqual(share.filters["payment"], "pending")
        self.assert_expires_between(data["expires_at"], timedelta(days=29), timedelta(days=31))

    def test_admin_can_create_twenty_four_hour_share_link(self):
        self.client.defaults["HTTP_AUTHORIZATION"] = bearer_token(self.admin)

        response = self.client.post(
            reverse("booking-share-create"),
            data={
                "share_type": BookingShare.SHARE_TYPE_BOOKING_SHEET,
                "validity": "24h",
            },
            content_type="application/json",
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assert_expires_between(response.json()["data"]["expires_at"], timedelta(hours=23), timedelta(hours=25))

    def test_booking_share_create_requires_admin_role(self):
        unauthenticated = self.client.post(
            reverse("booking-share-create"),
            data={"share_type": BookingShare.SHARE_TYPE_BOOKING_SHEET},
            content_type="application/json",
        )

        self.client.defaults["HTTP_AUTHORIZATION"] = bearer_token(self.requester)
        requester_response = self.client.post(
            reverse("booking-share-create"),
            data={"share_type": BookingShare.SHARE_TYPE_BOOKING_SHEET},
            content_type="application/json",
        )

        self.assertEqual(unauthenticated.status_code, status.HTTP_401_UNAUTHORIZED)
        self.assertEqual(requester_response.status_code, status.HTTP_403_FORBIDDEN)
        self.assertFalse(BookingShare.objects.exists())

    def test_public_booking_share_page_renders_without_authentication(self):
        share = BookingShare.objects.create(
            share_type=BookingShare.SHARE_TYPE_BOOKING_SHEET,
            expires_at=timezone.now() + timedelta(days=7),
            filters={
                "prefix": "Beta",
                "status": Booking.STATUS_ACTIVE,
                "arrival_from": "2026-07-01",
                "departure_to": "2026-07-31",
            },
            created_by=self.admin,
            created_by_name="Admin Share",
        )

        response = self.client.get(
            reverse("webapp:shared-bookings", kwargs={"token": share.token})
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertContains(response, "Shared Visitor")
        self.assertContains(response, "Shared Organisation")
        self.assertContains(response, "Beta")
        self.assertContains(response, "201")

    def test_public_booking_share_marks_expired_booking_pill(self):
        self.booking.status = Booking.STATUS_EXPIRED
        self.booking.save(update_fields=["status"])
        share = BookingShare.objects.create(
            share_type=BookingShare.SHARE_TYPE_BOOKING_SHEET,
            expires_at=timezone.now() + timedelta(days=7),
            filters={
                "prefix": "Beta",
                "status": Booking.STATUS_EXPIRED,
                "arrival_from": "2026-07-01",
                "departure_to": "2026-07-31",
            },
            created_by=self.admin,
            created_by_name="Admin Share",
        )

        response = self.client.get(
            reverse("webapp:shared-bookings", kwargs={"token": share.token})
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertContains(response, "Shared Visitor")
        self.assertContains(response, 'class="shared-booking-pill expired"')
        self.assertNotContains(response, "Available after")

    def test_public_charge_share_page_renders_without_authentication(self):
        share = BookingShare.objects.create(
            share_type=BookingShare.SHARE_TYPE_CHARGE_SHEET,
            expires_at=timezone.now() + timedelta(days=7),
            filters={
                "prefix": "Beta",
                "payment": "pending",
                "checkout_from": "2026-07-01",
                "checkout_to": "2026-07-31",
                "search": "Shared",
                "ordering": "-created_at",
            },
            created_by=self.admin,
            created_by_name="Admin Share",
        )

        response = self.client.get(
            reverse("webapp:shared-charges", kwargs={"token": share.token})
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertContains(response, "Charges Sheet")
        self.assertContains(response, "Shared Visitor")
        self.assertContains(response, "Shared Event")
        self.assertContains(response, "250")

    def test_public_charge_share_marks_expired_booking_row(self):
        self.booking.status = Booking.STATUS_EXPIRED
        self.booking.save(update_fields=["status"])
        share = BookingShare.objects.create(
            share_type=BookingShare.SHARE_TYPE_CHARGE_SHEET,
            expires_at=timezone.now() + timedelta(days=7),
            filters={
                "prefix": "Beta",
                "payment": "pending",
                "checkout_from": "2026-07-01",
                "checkout_to": "2026-07-31",
                "search": "Shared",
                "ordering": "-created_at",
            },
            created_by=self.admin,
            created_by_name="Admin Share",
        )

        response = self.client.get(
            reverse("webapp:shared-charges", kwargs={"token": share.token})
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertContains(response, "Shared Visitor")
        self.assertContains(response, 'class="expired-row"')

    def test_public_share_rejects_expired_token(self):
        share = BookingShare.objects.create(
            share_type=BookingShare.SHARE_TYPE_BOOKING_SHEET,
            expires_at=timezone.now() - timedelta(seconds=1),
            filters={
                "prefix": "Beta",
                "arrival_from": "2026-07-01",
                "departure_to": "2026-07-31",
            },
            created_by=self.admin,
            created_by_name="Admin Share",
        )

        response = self.client.get(
            reverse("webapp:shared-bookings", kwargs={"token": share.token})
        )

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_public_booking_share_rejects_unknown_token(self):
        response = self.client.get(
            reverse("webapp:shared-bookings", kwargs={"token": "not-a-valid-token"})
        )

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)


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
        self.assertEqual(booking_request.budget_head_name, "Requester Individual")
        self.assertEqual(booking_request.budget_head_department_name, "Requester Institute")
        self.assertEqual(booking_request.budget_head_project_code, "REQ-2026-001")
        data = response.json()["data"]
        self.assertEqual(data["budget_head_name"], "Requester Individual")
        self.assertEqual(data["budget_head_department_name"], "Requester Institute")
        self.assertEqual(data["budget_head_project_code"], "REQ-2026-001")

    def test_requester_submits_attender_request_without_count(self):
        self.client.defaults["HTTP_AUTHORIZATION"] = bearer_token(self.requester)

        response = self.client.post(
            reverse("requester-booking-request-list"),
            data=self.request_payload(
                attender_required=True,
                attender_day_shift=True,
            ),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        booking_request = BookingRequest.objects.get()
        self.assertTrue(booking_request.attender_day_shift)
        self.assertNotIn("attender_count_per_day", response.json()["data"])

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
            reverse("admin-booking-request-delete", kwargs={"pk": booking_request.pk}),
            data={"remarks": "Duplicate request"},
            content_type="application/json",
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
            reverse("admin-booking-request-delete", kwargs={"pk": booking_request.pk}),
            data={"remarks": "Approved request no longer needed"},
            content_type="application/json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        booking_request.refresh_from_db()
        self.assertTrue(booking_request.is_deleted)
        self.assertTrue(Booking.objects.filter(pk=booking.pk).exists())

    def test_admin_delete_requires_remarks(self):
        booking_request = BookingRequest.objects.create(
            requester=self.requester,
            **self.request_model_kwargs(),
        )
        self.client.defaults["HTTP_AUTHORIZATION"] = bearer_token(self.admin)

        response = self.client.delete(
            reverse("admin-booking-request-delete", kwargs={"pk": booking_request.pk}),
            data={"remarks": ""},
            content_type="application/json",
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("remarks", response.json()["errors"])
        booking_request.refresh_from_db()
        self.assertFalse(booking_request.is_deleted)

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
        self.assertEqual(booking_request.approved_booking.budget_head_name, "Requester Individual")
        self.assertEqual(booking_request.approved_booking.budget_head_department_name, "Requester Institute")
        self.assertEqual(booking_request.approved_booking.budget_head_project_code, "REQ-2026-001")

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
                "booking_remarks": "Guest will arrive late.",
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
        self.assertEqual(booking_request.admin_remarks, "Approved from form.")
        self.assertEqual(booking.visitor_name, "Edited Visitor")
        self.assertEqual(booking.purpose_of_visit, "Edited purpose")
        self.assertEqual(booking.remarks, "Guest will arrive late.")
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

    def test_reject_requires_remarks(self):
        booking_request = BookingRequest.objects.create(
            requester=self.requester,
            **self.request_model_kwargs(),
        )
        self.client.defaults["HTTP_AUTHORIZATION"] = bearer_token(self.admin)

        response = self.client.post(
            reverse("admin-booking-request-reject", kwargs={"pk": booking_request.pk}),
            data={"remarks": ""},
            content_type="application/json",
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        booking_request.refresh_from_db()
        self.assertEqual(booking_request.status, BookingRequest.STATUS_PENDING)

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
        self.assertEqual(booking_request.admin_remarks, "")
        self.assertEqual(response.json()["data"]["status"], BookingRequest.STATUS_PENDING)
        self.assertEqual(response.json()["data"]["admin_remarks"], "")

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

    def test_approve_rechecks_cooling_period(self):
        Booking.objects.create(
            room=self.room,
            arrival_at=utc_dt(2026, 7, 1, 8, 0),
            departure_at=utc_dt(2026, 7, 1, 10, 0),
            visitor_name="Existing Visitor",
        )
        booking_request = BookingRequest.objects.create(
            requester=self.requester,
            **self.request_model_kwargs(
                arrival_at=utc_dt(2026, 7, 1, 10, 30),
                departure_at=utc_dt(2026, 7, 1, 11, 30),
            ),
        )
        self.client.defaults["HTTP_AUTHORIZATION"] = bearer_token(self.admin)

        response = self.client.post(
            reverse("admin-booking-request-approve", kwargs={"pk": booking_request.pk}),
            data={"room": self.room.id, "remarks": "Approved."},
            content_type="application/json",
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("no longer available", response.json()["message"])
        self.assertIn("cooling period", str(response.json()["errors"]))
        self.assertEqual(Booking.objects.count(), 1)
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
            "budget_head_name": "Requester Individual",
            "budget_head_department_name": "Requester Institute",
            "budget_head_project_code": "REQ-2026-001",
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
            "budget_head_name": "Requester Individual",
            "budget_head_department_name": "Requester Institute",
            "budget_head_project_code": "REQ-2026-001",
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


@override_settings(ADMIN_SIGNUP_CODE="integration-admin-code")
class BookingApiIntegrationTests(TestCase):
    def setUp(self):
        self.signal_sync = patch("bookings.signals.request_calendar_sync", return_value=True)
        self.signal_sync.start()
        self.addCleanup(self.signal_sync.stop)

        self.room = Room.objects.create(prefix="Delta", number="INT101", hostel_name="Integration")
        self.other_room = Room.objects.create(prefix="Delta", number="INT102", hostel_name="Integration")
        self.superadmin = User.objects.create_superuser(
            username="integration-superadmin@example.com",
            email="integration-superadmin@example.com",
            password="StrongPass123",
            first_name="Integration Superadmin",
        )

    def test_full_account_request_booking_lifecycle_uses_consistent_api_rules(self):
        admin_token = self.signup_approve_and_login_admin()
        requester_token = self.signup_approve_and_login_requester(admin_token)

        self.authenticate(requester_token)
        availability_before = self.client.get(
            reverse("requester-available-rooms-range"),
            {
                "arrival_date": "2026-09-10",
                "departure_date": "2026-09-10",
                "prefix": "Delta",
            },
        )
        self.assertEqual(availability_before.status_code, status.HTTP_200_OK)
        before_by_id = {
            room["room_id"]: room
            for room in availability_before.json()["data"]["rooms"]
        }
        self.assertEqual(before_by_id[self.room.id]["availability_status"], "available")

        create_request = self.client.post(
            reverse("requester-booking-request-list"),
            data=self.booking_request_payload(
                arrival_at=local_dt(2026, 9, 10, 10, 0),
                departure_at=local_dt(2026, 9, 10, 12, 0),
                preferred_room=self.room.id,
            ),
            content_type="application/json",
        )
        self.assertEqual(create_request.status_code, status.HTTP_201_CREATED)
        request_id = create_request.json()["data"]["id"]

        self.authenticate(admin_token)
        request_list = self.client.get(
            reverse("admin-booking-request-list"),
            {"status": BookingRequest.STATUS_PENDING},
        )
        self.assertEqual(request_list.status_code, status.HTTP_200_OK)
        self.assertIn(request_id, [item["id"] for item in request_list.json()["data"]])

        approve = self.client.post(
            reverse("admin-booking-request-approve", kwargs={"pk": request_id}),
            data={"room": self.room.id, "remarks": "Approved by integration test."},
            content_type="application/json",
        )
        self.assertEqual(approve.status_code, status.HTTP_200_OK)
        approved_booking_id = approve.json()["data"]["approved_booking_id"]
        self.assertIsNotNone(approved_booking_id)

        booking = Booking.objects.get(pk=approved_booking_id)
        self.assertEqual(booking.room, self.room)
        self.assertEqual(booking.created_by.email, "integration-admin@example.com")

        availability_after = self.client.get(
            reverse("room-available-rooms-range"),
            {
                "arrival_date": "2026-09-10",
                "departure_date": "2026-09-10",
                "prefix": "Delta",
            },
        )
        self.assertEqual(availability_after.status_code, status.HTTP_200_OK)
        after_by_id = {
            room["room_id"]: room
            for room in availability_after.json()["data"]["rooms"]
        }
        self.assertEqual(after_by_id[self.room.id]["availability_status"], "partial")
        self.assertEqual(after_by_id[self.room.id]["available_from_time"], "01:00 PM")

        conflict = self.client.post(
            reverse("booking-create"),
            data=self.admin_booking_payload(
                room=self.room,
                arrival_at=local_dt(2026, 9, 10, 11, 0),
                departure_at=local_dt(2026, 9, 10, 13, 0),
            ),
            content_type="application/json",
        )
        self.assertEqual(conflict.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("already booked", conflict.json()["message"])

        boundary_create = self.client.post(
            reverse("booking-create"),
            data=self.admin_booking_payload(
                room=self.room,
                arrival_at=local_dt(2026, 9, 10, 13, 0),
                departure_at=local_dt(2026, 9, 10, 14, 0),
                visitor_name="Boundary Visitor",
            ),
            content_type="application/json",
        )
        self.assertEqual(boundary_create.status_code, status.HTTP_201_CREATED)
        boundary_booking_id = boundary_create.json()["data"]["booking_id"]

        edit = self.client.patch(
            reverse("booking-edit", kwargs={"pk": approved_booking_id}),
            data={"purpose_of_visit": "Updated after approval"},
            content_type="application/json",
        )
        self.assertEqual(edit.status_code, status.HTTP_200_OK)
        booking.refresh_from_db()
        self.assertEqual(booking.purpose_of_visit, "Updated after approval")

        self.authenticate(requester_token)
        requester_requests = self.client.get(
            reverse("requester-booking-request-list"),
            {"status": BookingRequest.STATUS_APPROVED},
        )
        self.assertEqual(requester_requests.status_code, status.HTTP_200_OK)
        self.assertIn(request_id, [item["id"] for item in requester_requests.json()["data"]])

        self.authenticate(admin_token)
        delete_approved = self.client.delete(
            reverse("booking-delete", kwargs={"pk": approved_booking_id})
        )
        self.assertEqual(delete_approved.status_code, status.HTTP_200_OK)
        source_request = BookingRequest.objects.get(pk=request_id)
        self.assertTrue(source_request.is_deleted)
        self.assertEqual(source_request.delete_reason, "Linked booking was deleted by admin.")

        delete_boundary = self.client.delete(
            reverse("booking-delete", kwargs={"pk": boundary_booking_id})
        )
        self.assertEqual(delete_boundary.status_code, status.HTTP_200_OK)
        self.assertEqual(Booking.objects.count(), 0)

    def test_request_sendback_resubmit_reject_and_delete_are_stateful(self):
        admin = self.create_approved_user(
            "workflow-admin@example.com",
            "Workflow Admin",
            ROLE_ADMIN,
        )
        requester = self.create_approved_user(
            "workflow-requester@example.com",
            "Workflow Requester",
            ROLE_REQUESTER,
        )
        admin_token = bearer_token(admin)
        requester_token = bearer_token(requester)

        self.authenticate(requester_token)
        create_request = self.client.post(
            reverse("requester-booking-request-list"),
            data=self.booking_request_payload(
                arrival_at=utc_dt(2026, 9, 12, 10, 0),
                departure_at=utc_dt(2026, 9, 12, 12, 0),
                preferred_room=self.other_room.id,
            ),
            content_type="application/json",
        )
        self.assertEqual(create_request.status_code, status.HTTP_201_CREATED)
        request_id = create_request.json()["data"]["id"]

        self.authenticate(admin_token)
        blank_sendback = self.client.post(
            reverse("admin-booking-request-send-back", kwargs={"pk": request_id}),
            data={"remarks": ""},
            content_type="application/json",
        )
        self.assertEqual(blank_sendback.status_code, status.HTTP_400_BAD_REQUEST)

        sendback = self.client.post(
            reverse("admin-booking-request-send-back", kwargs={"pk": request_id}),
            data={"remarks": "Please correct visitor mobile."},
            content_type="application/json",
        )
        self.assertEqual(sendback.status_code, status.HTTP_200_OK)
        self.assertEqual(sendback.json()["data"]["status"], BookingRequest.STATUS_CORRECTION_REQUIRED)

        self.authenticate(requester_token)
        resubmit = self.client.patch(
            reverse("requester-booking-request-detail", kwargs={"pk": request_id}),
            data={"visitor_mobile": "9123456789"},
            content_type="application/json",
        )
        self.assertEqual(resubmit.status_code, status.HTTP_200_OK)
        self.assertEqual(resubmit.json()["data"]["status"], BookingRequest.STATUS_PENDING)
        self.assertEqual(resubmit.json()["data"]["admin_remarks"], "")

        self.authenticate(admin_token)
        blank_reject = self.client.post(
            reverse("admin-booking-request-reject", kwargs={"pk": request_id}),
            data={"remarks": ""},
            content_type="application/json",
        )
        self.assertEqual(blank_reject.status_code, status.HTTP_400_BAD_REQUEST)

        reject = self.client.post(
            reverse("admin-booking-request-reject", kwargs={"pk": request_id}),
            data={"remarks": "No room can be assigned."},
            content_type="application/json",
        )
        self.assertEqual(reject.status_code, status.HTTP_200_OK)
        self.assertEqual(reject.json()["data"]["status"], BookingRequest.STATUS_REJECTED)
        self.assertEqual(Booking.objects.count(), 0)

        blank_delete = self.client.delete(
            reverse("admin-booking-request-delete", kwargs={"pk": request_id}),
            data={"remarks": ""},
            content_type="application/json",
        )
        self.assertEqual(blank_delete.status_code, status.HTTP_400_BAD_REQUEST)

        delete = self.client.delete(
            reverse("admin-booking-request-delete", kwargs={"pk": request_id}),
            data={"remarks": "Archived rejected integration request."},
            content_type="application/json",
        )
        self.assertEqual(delete.status_code, status.HTTP_200_OK)
        booking_request = BookingRequest.objects.get(pk=request_id)
        self.assertTrue(booking_request.is_deleted)
        self.assertEqual(
            booking_request.delete_reason,
            "Archived rejected integration request.",
        )

    def signup_approve_and_login_admin(self):
        signup = self.client.post(
            reverse("auth-admin-signup"),
            data={
                "name": "Integration Admin",
                "email": "integration-admin@example.com",
                "password": "StrongPass123",
                "confirm_password": "StrongPass123",
                "admin_code": "integration-admin-code",
            },
            content_type="application/json",
        )
        self.assertEqual(signup.status_code, status.HTTP_201_CREATED)
        admin_user = User.objects.get(email="integration-admin@example.com")
        self.assertEqual(admin_user.profile.approval_status, APPROVAL_PENDING)

        login_before = self.client.post(
            reverse("auth-admin-login"),
            data={"email": admin_user.email, "password": "StrongPass123"},
            content_type="application/json",
        )
        self.assertEqual(login_before.status_code, status.HTTP_400_BAD_REQUEST)

        self.authenticate(bearer_token(self.superadmin))
        approve = self.client.post(
            reverse("superadmin-account-request-approve", kwargs={"pk": admin_user.profile.pk}),
            data={},
            content_type="application/json",
        )
        self.assertEqual(approve.status_code, status.HTTP_200_OK)

        self.clear_auth()
        login_after = self.client.post(
            reverse("auth-admin-login"),
            data={"email": admin_user.email, "password": "StrongPass123"},
            content_type="application/json",
        )
        self.assertEqual(login_after.status_code, status.HTTP_200_OK)
        return f"Bearer {login_after.json()['data']['access']}"

    def signup_approve_and_login_requester(self, admin_token):
        signup = self.client.post(
            reverse("auth-requester-signup"),
            data={
                "name": "Integration Requester",
                "email": "integration-requester@example.com",
                "password": "StrongPass123",
                "confirm_password": "StrongPass123",
                "department": "CSE",
                "designation": "Student",
                "mobile": "9876543210",
            },
            content_type="application/json",
        )
        self.assertEqual(signup.status_code, status.HTTP_201_CREATED)
        requester_user = User.objects.get(email="integration-requester@example.com")
        self.assertEqual(requester_user.profile.approval_status, APPROVAL_PENDING)

        login_before = self.client.post(
            reverse("auth-requester-login"),
            data={"email": requester_user.email, "password": "StrongPass123"},
            content_type="application/json",
        )
        self.assertEqual(login_before.status_code, status.HTTP_400_BAD_REQUEST)

        self.authenticate(admin_token)
        approve = self.client.post(
            reverse("admin-requester-account-approve", kwargs={"pk": requester_user.profile.pk}),
            data={},
            content_type="application/json",
        )
        self.assertEqual(approve.status_code, status.HTTP_200_OK)

        self.clear_auth()
        login_after = self.client.post(
            reverse("auth-requester-login"),
            data={"email": requester_user.email, "password": "StrongPass123"},
            content_type="application/json",
        )
        self.assertEqual(login_after.status_code, status.HTTP_200_OK)
        return f"Bearer {login_after.json()['data']['access']}"

    def create_approved_user(self, email, name, role):
        user = User.objects.create_user(
            username=email,
            email=email,
            password="StrongPass123",
            first_name=name,
        )
        set_user_role(user, role, approval_status=APPROVAL_APPROVED)
        return user

    def authenticate(self, token):
        self.client.defaults["HTTP_AUTHORIZATION"] = token

    def clear_auth(self):
        self.client.defaults.pop("HTTP_AUTHORIZATION", None)

    def booking_request_payload(self, arrival_at, departure_at, preferred_room=None, **overrides):
        payload = {
            "arrival_at": iso(arrival_at),
            "departure_at": iso(departure_at),
            "preferred_prefix": "Delta",
            "preferred_room": preferred_room,
            "visitor_name": "Integration Visitor",
            "visitor_mobile": "9876543210",
            "visitor_category": Booking.VISITOR_CATEGORY_INSTITUTE,
            "purpose_of_visit": "Integration test visit",
            "requestor_name": "Integration Requester",
            "requestor_email": "integration-requester@example.com",
        }
        payload.update(overrides)
        return payload

    def admin_booking_payload(self, room, arrival_at, departure_at, **overrides):
        payload = {
            "room": room.id,
            "arrival_at": iso(arrival_at),
            "departure_at": iso(departure_at),
            "visitor_name": "Direct Integration Visitor",
            "visitor_mobile": "9876543210",
            "visitor_category": Booking.VISITOR_CATEGORY_INSTITUTE,
            "room_charges_status": Booking.CHARGE_STATUS_NO,
            "attender_charges_status": Booking.CHARGE_STATUS_NO,
            "room_charges_amount": "0",
            "attender_charges_amount": "0",
        }
        payload.update(overrides)
        return payload


class BookingApiVolumeTests(TestCase):
    def setUp(self):
        self.signal_sync = patch("bookings.signals.request_calendar_sync", return_value=True)
        self.signal_sync.start()
        self.addCleanup(self.signal_sync.stop)

        self.admin = create_user("volume-admin@example.com", "Volume Admin")
        self.requester = create_requester("volume-requester@example.com", "Volume Requester")
        self.client.defaults["HTTP_AUTHORIZATION"] = bearer_token(self.admin)

    def test_availability_endpoints_handle_hundreds_of_rooms_and_bookings(self):
        rooms = self.create_rooms("VolAvail", 300)
        bookings = []
        for room in rooms[:120]:
            bookings.append(self.booking_model(room, local_dt(2026, 9, 15, 10, 0), local_dt(2026, 9, 15, 12, 0)))
        for room in rooms[120:200]:
            bookings.append(self.booking_model(room, local_dt(2026, 9, 15, 15, 0), local_dt(2026, 9, 15, 17, 30)))
        for index in range(500):
            room = rooms[index % len(rooms)]
            day = 1 + (index % 20)
            bookings.append(self.booking_model(room, local_dt(2026, 10, day, 8, 0), local_dt(2026, 10, day, 9, 0)))
        Booking.objects.bulk_create(bookings)

        range_response = self.client.get(
            reverse("room-available-rooms-range"),
            {
                "arrival_date": "2026-09-15",
                "departure_date": "2026-09-15",
                "prefix": "VolAvail",
            },
        )
        day_response = self.client.get(
            reverse("room-available-rooms"),
            {"date": "2026-09-15", "prefix": "VolAvail"},
        )

        self.assertEqual(range_response.status_code, status.HTTP_200_OK)
        self.assertEqual(day_response.status_code, status.HTTP_200_OK)
        for response in [range_response, day_response]:
            data = response.json()["data"]
            rooms_payload = data["rooms"]
            self.assertEqual(data["total_available_rooms"], 220)
            self.assertEqual(len(rooms_payload), 220)
            self.assertEqual(
                sum(1 for room in rooms_payload if room["availability_status"] == "partial"),
                120,
            )
            self.assertEqual(
                sum(1 for room in rooms_payload if room["availability_status"] == "available"),
                100,
            )
            returned_ids = {room["room_id"] for room in rooms_payload}
            self.assertTrue(all(room.id not in returned_ids for room in rooms[120:200]))

    def test_paginated_booking_and_charge_sheet_lists_handle_hundreds_of_bookings(self):
        rooms = self.create_rooms("VolList", 80)
        bookings = []
        for index in range(350):
            room = rooms[index % len(rooms)]
            day = 1 + (index % 25)
            bookings.append(
                self.booking_model(
                    room,
                    utc_dt(2026, 9, day, 8, 0),
                    utc_dt(2026, 9, day, 10, 0),
                    visitor_name=f"Volume Guest {index:04d}",
                    requestor_name=f"Volume Requestor {index % 17:02d}",
                )
            )
        Booking.objects.bulk_create(bookings)

        booking_list = self.client.get(
            reverse("booking-list"),
            {"prefix": "VolList", "page_size": 100},
        )
        charge_sheet_list = self.client.get(
            reverse("booking-charge-sheet-list"),
            {"prefix": "VolList", "page_size": 100},
        )
        charge_sheet_search = self.client.get(
            reverse("booking-charge-sheet-list"),
            {"prefix": "VolList", "search": "Volume Guest 0342"},
        )

        self.assertEqual(booking_list.status_code, status.HTTP_200_OK)
        self.assertEqual(booking_list.json()["data"]["count"], 350)
        self.assertEqual(len(booking_list.json()["data"]["results"]), 100)
        self.assertEqual(charge_sheet_list.status_code, status.HTTP_200_OK)
        self.assertEqual(charge_sheet_list.json()["data"]["count"], 350)
        self.assertEqual(len(charge_sheet_list.json()["data"]["results"]), 100)
        self.assertEqual(BookingChargeSheet.objects.filter(booking__room__prefix="VolList").count(), 350)
        self.assertEqual(charge_sheet_search.status_code, status.HTTP_200_OK)
        self.assertEqual(charge_sheet_search.json()["data"]["count"], 1)
        self.assertEqual(
            charge_sheet_search.json()["data"]["results"][0]["guest_name"],
            "Volume Guest 0342",
        )

    def test_pending_request_review_paths_handle_large_request_volume(self):
        room = Room.objects.create(prefix="VolReq", number="VR001", hostel_name="Integration")
        requests = []
        for index in range(600):
            day = 1 + (index % 25)
            requests.append(
                BookingRequest(
                    requester=self.requester,
                    status=BookingRequest.STATUS_PENDING,
                    arrival_at=utc_dt(2026, 11, day, 8, 0),
                    departure_at=utc_dt(2026, 11, day, 10, 0),
                    preferred_prefix="VolReq",
                    visitor_name=f"Volume Request Visitor {index:04d}",
                    visitor_mobile="9876543210",
                    visitor_category=Booking.VISITOR_CATEGORY_INSTITUTE,
                    purpose_of_visit="Volume request test",
                    requestor_name="Volume Requester",
                    requestor_email="volume-requester@example.com",
                )
            )
        BookingRequest.objects.bulk_create(requests)

        pending_list = self.client.get(
            reverse("admin-booking-request-list"),
            {"status": BookingRequest.STATUS_PENDING},
        )
        approve_target = BookingRequest.objects.get(visitor_name="Volume Request Visitor 0300")
        reject_target = BookingRequest.objects.get(visitor_name="Volume Request Visitor 0301")
        delete_target = BookingRequest.objects.get(visitor_name="Volume Request Visitor 0302")

        approve = self.client.post(
            reverse("admin-booking-request-approve", kwargs={"pk": approve_target.pk}),
            data={"room": room.id, "remarks": "Approved in volume test."},
            content_type="application/json",
        )
        reject = self.client.post(
            reverse("admin-booking-request-reject", kwargs={"pk": reject_target.pk}),
            data={"remarks": "Rejected in volume test."},
            content_type="application/json",
        )
        delete = self.client.delete(
            reverse("admin-booking-request-delete", kwargs={"pk": delete_target.pk}),
            data={"remarks": "Deleted in volume test."},
            content_type="application/json",
        )

        self.assertEqual(pending_list.status_code, status.HTTP_200_OK)
        self.assertEqual(len(pending_list.json()["data"]), 600)
        self.assertEqual(approve.status_code, status.HTTP_200_OK)
        self.assertEqual(reject.status_code, status.HTTP_200_OK)
        self.assertEqual(delete.status_code, status.HTTP_200_OK)
        self.assertEqual(Booking.objects.count(), 1)
        approve_target.refresh_from_db()
        reject_target.refresh_from_db()
        delete_target.refresh_from_db()
        self.assertEqual(approve_target.status, BookingRequest.STATUS_APPROVED)
        self.assertEqual(reject_target.status, BookingRequest.STATUS_REJECTED)
        self.assertTrue(delete_target.is_deleted)
        self.assertEqual(
            BookingRequest.objects.filter(
                status=BookingRequest.STATUS_PENDING,
                is_deleted=False,
            ).count(),
            597,
        )

    def create_rooms(self, prefix, count):
        Room.objects.bulk_create([
            Room(
                prefix=prefix,
                number=f"V{index:04d}",
                hostel_name="Integration",
                display_order=index,
            )
            for index in range(count)
        ])
        return list(Room.objects.filter(prefix=prefix).order_by("display_order", "number"))

    def booking_model(self, room, arrival_at, departure_at, **overrides):
        data = {
            "room": room,
            "arrival_at": arrival_at,
            "departure_at": departure_at,
            "visitor_name": "Volume Guest",
            "purpose_of_visit": "Volume test",
            "requestor_name": "Volume Requestor",
        }
        data.update(overrides)
        return Booking(**data)


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


class BookingChargeSheetApiTests(TestCase):
    def setUp(self):
        self.signal_sync = patch("bookings.signals.request_calendar_sync", return_value=True)
        self.signal_sync.start()
        self.addCleanup(self.signal_sync.stop)

        self.admin = create_user("admin-charge-sheet@example.com", "Admin User")
        self.room = Room.objects.get(prefix="Delta", number="101A")
        self.other_room = Room.objects.create(prefix="Gamma", number="CS201", hostel_name="Mainpat")
        self.client.defaults["HTTP_AUTHORIZATION"] = bearer_token(self.admin)

    def test_charge_sheet_list_creates_missing_rows_from_bookings(self):
        booking = self.create_booking(
            self.room,
            visitor_name="Guest One",
            requestor_name="Requestor One",
            purpose_of_visit="Annual event",
            remarks="Needs projector setup.",
            room_charges_amount=1500,
            attender_charges_amount=500,
            budget_head_name="Budget A",
        )
        BookingChargeSheet.objects.filter(booking=booking).delete()

        response = self.client.get(reverse("booking-charge-sheet-list"))

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        rows = response.json()["data"]["results"]
        self.assertEqual(len(rows), 1)
        row = rows[0]
        self.assertEqual(row["booking_reference_id"], booking.booking_reference_number)
        self.assertEqual(row["check_in"], "2026-09-01T10:00:00Z")
        self.assertEqual(row["requestor_name"], "Requestor One")
        self.assertEqual(row["guest_name"], "Guest One")
        self.assertEqual(row["purpose_event"], "Annual event")
        self.assertEqual(row["remarks"], "Needs projector setup.")
        self.assertEqual(row["delta"], "Delta 101A")
        self.assertEqual(row["gamma"], "")
        self.assertEqual(row["beta"], "")
        self.assertEqual(row["total_charges"], "2000.00")

    def test_charge_sheet_update_updates_linked_booking_and_audit_history(self):
        booking = self.create_booking(self.room, visitor_name="Original Guest")
        sheet_row = booking.charge_sheet

        response = self.client.patch(
            reverse("booking-charge-sheet-detail", kwargs={"pk": sheet_row.pk}),
            data={
                "guest_name": "Edited Guest",
                "purpose_event": "Edited event",
                "remarks": "Edited remarks",
                "room_charges_amount": "2500.00",
                "attender_charges_amount": "750.00",
                "payment_received_date": "2026-07-10",
                "budget_head_name": "Edited Budget",
            },
            content_type="application/json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        sheet_row.refresh_from_db()
        booking.refresh_from_db()
        self.assertEqual(sheet_row.guest_name, "Edited Guest")
        self.assertEqual(sheet_row.remarks, "Edited remarks")
        self.assertEqual(sheet_row.total_charges, 3250)
        self.assertEqual(booking.visitor_name, "Edited Guest")
        self.assertEqual(booking.purpose_of_visit, "Edited event")
        self.assertEqual(booking.remarks, "Edited remarks")
        self.assertEqual(booking.room_charges_amount, 2500)
        self.assertEqual(booking.attender_charges_amount, 750)
        self.assertEqual(booking.room_charges_status, Booking.CHARGE_STATUS_YES)
        self.assertEqual(booking.attender_charges_status, Booking.CHARGE_STATUS_YES)
        self.assertEqual(booking.budget_head_name, "Edited Budget")
        self.assertTrue(
            BookingEditHistory.objects.filter(
                booking=booking,
                field_name="visitor_name",
                old_value="Original Guest",
                new_value="Edited Guest",
            ).exists()
        )
        self.assertTrue(
            BookingEditHistory.objects.filter(
                booking=booking,
                field_name="remarks",
                new_value="Edited remarks",
            ).exists()
        )

    def test_charge_sheet_update_allows_expired_booking(self):
        booking = self.create_booking(
            self.room,
            arrival_at=utc_dt(2026, 7, 1, 10, 0),
            departure_at=utc_dt(2026, 7, 1, 12, 0),
            visitor_name="Expired Guest",
        )
        sheet_row = booking.charge_sheet

        response = self.client.patch(
            reverse("booking-charge-sheet-detail", kwargs={"pk": sheet_row.pk}),
            data={"guest_name": "Expired Guest Edited"},
            content_type="application/json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        sheet_row.refresh_from_db()
        booking.refresh_from_db()
        self.assertEqual(sheet_row.guest_name, "Expired Guest Edited")
        self.assertEqual(booking.visitor_name, "Expired Guest Edited")
        self.assertTrue(
            BookingEditHistory.objects.filter(
                booking=booking,
                field_name="visitor_name",
                old_value="Expired Guest",
                new_value="Expired Guest Edited",
            ).exists()
        )

    def test_deleting_booking_removes_charge_sheet_row(self):
        booking = self.create_booking(self.room, visitor_name="Delete Me")
        sheet_row_id = booking.charge_sheet.id

        response = self.client.delete(reverse("booking-delete", kwargs={"pk": booking.pk}))

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertFalse(Booking.objects.filter(pk=booking.pk).exists())
        self.assertFalse(BookingChargeSheet.objects.filter(pk=sheet_row_id).exists())

    def test_charge_sheet_filters_search_and_ordering(self):
        self.create_booking(
            self.room,
            visitor_name="Alpha Guest",
            requestor_name="Alpha Requestor",
            purpose_of_visit="Seminar",
            room_charges_amount=100,
        )
        gamma_booking = self.create_booking(
            self.other_room,
            visitor_name="Beta Guest",
            requestor_name="Finance Office",
            purpose_of_visit="Workshop",
            remarks="Receipt remarks",
            room_charges_amount=900,
            attender_charges_amount=100,
        )
        gamma_booking.charge_sheet.payment_received_date = datetime(2026, 7, 10).date()
        gamma_booking.charge_sheet.save(update_fields=["payment_received_date"])

        response = self.client.get(
            reverse("booking-charge-sheet-list"),
            {"prefix": "Gamma", "payment": "received", "search": "Receipt remarks", "ordering": "-total_charges"},
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        rows = response.json()["data"]["results"]
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["booking_reference_id"], gamma_booking.booking_reference_number)
        self.assertEqual(rows[0]["gamma"], "Gamma CS201")
        self.assertEqual(rows[0]["total_charges"], "1000.00")

        response = self.client.get(reverse("booking-charge-sheet-list"), {"ordering": "-check_in"})

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("check_in", response.json()["data"]["results"][0])

    def test_charge_sheet_defaults_to_recent_created_first(self):
        first_booking = self.create_booking(self.room, visitor_name="First Created")
        second_booking = self.create_booking(self.other_room, visitor_name="Second Created")

        BookingChargeSheet.objects.filter(booking=second_booking).update(
            created_at=timezone.now() + timedelta(minutes=5)
        )

        response = self.client.get(reverse("booking-charge-sheet-list"))

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        rows = response.json()["data"]["results"]
        self.assertGreaterEqual(len(rows), 2)
        self.assertEqual(rows[0]["booking_reference_id"], second_booking.booking_reference_number)
        self.assertEqual(rows[1]["booking_reference_id"], first_booking.booking_reference_number)

    def create_booking(self, room, **overrides):
        data = {
            "room": room,
            "arrival_at": utc_dt(2026, 9, 1, 10, 0),
            "departure_at": utc_dt(2026, 9, 1, 12, 0),
            "visitor_name": "Guest",
            "purpose_of_visit": "Event",
            "requestor_name": "Requestor",
            "room_charges_amount": 0,
            "attender_charges_amount": 0,
        }
        data.update(overrides)
        return Booking.objects.create(**data)


def utc_dt(year, month, day, hour, minute):
    return datetime(year, month, day, hour, minute, tzinfo=datetime_timezone.utc)


def local_dt(year, month, day, hour, minute):
    return datetime(year, month, day, hour, minute, tzinfo=INDIA_TZ)


def iso(value):
    return value.isoformat()
