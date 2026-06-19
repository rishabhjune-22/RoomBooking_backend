from datetime import time
import re

from django.utils import timezone
from rest_framework import serializers

from .constants import COOLING_PERIOD
from .models import Booking

from zoneinfo import ZoneInfo


PHONE_ALLOWED_RE = re.compile(r"^\+?[0-9][0-9\s().-]*$")
PHONE_DIGIT_RE = re.compile(r"\d")

class BookingSerializer(serializers.ModelSerializer):
    room_name = serializers.SerializerMethodField()

    class Meta:
        model = Booking
        fields = [
            "id", "room", "room_name", "arrival_at", "departure_at",

            "visitor_name",
            "visitor_designation",
            "visitor_organisation",
            "visitor_gender",
            "visitor_address",
            "visitor_mobile",
            "visitor_email",
            "purpose_of_visit",
            "visitor_category",
            "budget_head_type",
            "budget_head_value",
            "budget_head_name",
            "budget_head_department_name",
            "budget_head_project_code",
"attender_required",
"attender_count_per_day",
"attender_general_shift",
"attender_morning_shift",
"attender_day_shift",
            "room_charges_status",
            "attender_charges_status",
            "room_charges_amount",
            "attender_charges_amount",
            "requestor_name",
            "requestor_designation",
            "requestor_department",
            "requestor_mobile",
            "created_by_name",

            "logistics_name",
            "logistics_designation",
            "logistics_mobile",

            "status", "created_at",
        ]

        read_only_fields = [
            "id", "room_name", "status", "created_at",
        ]

        extra_kwargs = {
 "visitor_name": {
        "required": True,
        "allow_blank": False,
        "trim_whitespace": True,
        "error_messages": {
            "blank": "Visitor name is required.",
            "required": "Visitor name is required.",
            "null": "Visitor name is required.",
        },
    },

    "created_by_name": {
        "required": False,
        "allow_blank": True
    },


"visitor_gender": {
    "required": False,
    "allow_blank": True
},

               "created_by_name": {
        "required": False,
        "allow_blank": True
    },
"visitor_category": {"required": False, "allow_blank": True},
            "budget_head_type": {"required": False, "allow_blank": True},
            "budget_head_value": {"required": False, "allow_blank": True},
            "budget_head_name": {"required": False, "allow_blank": True},
            "budget_head_department_name": {"required": False, "allow_blank": True},
            "budget_head_project_code": {"required": False, "allow_blank": True},
            "room_charges_status": {"required": False},
            "attender_charges_status": {"required": False},
            "room_charges_amount": {"required": False},
            "attender_charges_amount": {"required": False},

            "visitor_designation": {"required": False, "allow_blank": True},
            "visitor_organisation": {"required": False, "allow_blank": True},
            "visitor_address": {"required": False, "allow_blank": True},
            "visitor_mobile": {"required": False, "allow_blank": True},
            "visitor_email": {"required": False, "allow_blank": True},
            "purpose_of_visit": {"required": False, "allow_blank": True},
            "requestor_name": {"required": False, "allow_blank": True},
            "requestor_designation": {"required": False, "allow_blank": True},
            "requestor_department": {"required": False, "allow_blank": True},
            "requestor_mobile": {"required": False, "allow_blank": True},
            "logistics_name": {"required": False, "allow_blank": True},
            "logistics_designation": {"required": False, "allow_blank": True},
            "logistics_mobile": {"required": False, "allow_blank": True},
        }

    def get_room_name(self, obj):
        return str(obj.room)

    def validate_visitor_name(self, value):
        if not value or not value.strip():
            raise serializers.ValidationError("Visitor name is required.")
        return value.strip()

    def validate_visitor_gender(self, value):
        if value is None:
            return ""
        return value.strip()

    def validate_visitor_mobile(self, value):
        return self.validate_optional_mobile(value, "Visitor mobile")

    def validate_requestor_mobile(self, value):
        return self.validate_optional_mobile(value, "Requestor mobile")

    def validate_logistics_mobile(self, value):
        return self.validate_optional_mobile(value, "Logistics mobile")

    def validate_optional_mobile(self, value, label):
        if value is None:
            return ""

        mobile = value.strip()
        if not mobile:
            return ""

        digits = PHONE_DIGIT_RE.findall(mobile)
        if not PHONE_ALLOWED_RE.fullmatch(mobile) or not 7 <= len(digits) <= 15:
            raise serializers.ValidationError(
                f"{label} must contain 7 to 15 digits and may only include +, spaces, hyphens, dots or parentheses."
            )

        return mobile

    def validate(self, attrs):
        instance = self.instance
        room = attrs.get("room", getattr(instance, "room", None))
        arrival_at = attrs.get("arrival_at", getattr(instance, "arrival_at", None))
        departure_at = attrs.get("departure_at", getattr(instance, "departure_at", None))

        if not all([room, arrival_at, departure_at]):
            raise serializers.ValidationError(
                "Room, arrival datetime and departure datetime are required."
            )

        if departure_at <= arrival_at:
            raise serializers.ValidationError(
                {"departure_at": ["Departure datetime must be after arrival datetime."]}
            )

        self.set_default_optional_fields(attrs)
        self.validate_attender_fields(attrs)
        self.validate_charge_fields(attrs)
        self.validate_room_conflict(room, arrival_at, departure_at, instance)
        self.validate_same_day_full_block(room, arrival_at, instance)
        self.validate_cooling_period(room, arrival_at, instance)
        self.validate_next_booking_cooling_period(room, departure_at, instance)

        return attrs
    def validate_charge_fields(self, attrs):
        instance = self.instance

        charge_fields = [
            ("room_charges_status", "room_charges_amount", "Room charges amount"),
            ("attender_charges_status", "attender_charges_amount", "Attender charges amount"),
        ]

        for status_field, amount_field, label in charge_fields:
            charge_status = attrs.get(
                status_field,
                getattr(instance, status_field, Booking.CHARGE_STATUS_NO),
            )
            amount = attrs.get(amount_field, getattr(instance, amount_field, 0))

            if charge_status == Booking.CHARGE_STATUS_YES and amount <= 0:
                raise serializers.ValidationError({
                    amount_field: [f"{label} is required when charges are received."]
                })

            if charge_status != Booking.CHARGE_STATUS_YES:
                attrs[amount_field] = 0

    def validate_attender_fields(self, attrs):
        instance = self.instance

        attender_required = attrs.get(
            "attender_required",
            getattr(instance, "attender_required", False)
        )

        attender_count = attrs.get(
            "attender_count_per_day",
            getattr(instance, "attender_count_per_day", 0)
        )

        general_shift = attrs.get(
            "attender_general_shift",
            getattr(instance, "attender_general_shift", False)
        )

        morning_shift = attrs.get(
            "attender_morning_shift",
            getattr(instance, "attender_morning_shift", False)
        )

        day_shift = attrs.get(
            "attender_day_shift",
            getattr(instance, "attender_day_shift", False)
        )

        if attender_required and attender_count <= 0:
            raise serializers.ValidationError({
                "attender_count_per_day": [
                    "Enter number of attenders required per day."
                ]
            })

        if attender_required and not any([
            general_shift,
            morning_shift,
            day_shift,
        ]):
            raise serializers.ValidationError({
                "attender_shift": [
                    "Please select at least one attender shift."
                ]
            })

        if not attender_required:
            attrs["attender_count_per_day"] = 0
            attrs["attender_general_shift"] = False
            attrs["attender_morning_shift"] = False
            attrs["attender_day_shift"] = False

    def set_default_optional_fields(self, attrs):
        optional_fields = [
                "created_by_name",

            "visitor_designation",
            "visitor_organisation",
            "visitor_address",
            "visitor_mobile",
            "visitor_email",
            "purpose_of_visit",
            "budget_head_type",
            "budget_head_value",
            "budget_head_name",
            "budget_head_department_name",
            "budget_head_project_code",
            "requestor_name",
            "requestor_designation",
            "requestor_department",
            "requestor_mobile",
            "logistics_name",
            "logistics_designation",
            "logistics_mobile",
        ]

        for field in optional_fields:
            attrs.setdefault(field, "")

    def validate_room_conflict(self, room, arrival_at, departure_at, instance=None):
        conflicting_bookings = Booking.objects.filter(
            room=room,
            status=Booking.STATUS_ACTIVE,
            arrival_at__lt=departure_at,
            departure_at__gt=arrival_at,
        )

        if instance:
            conflicting_bookings = conflicting_bookings.exclude(pk=instance.pk)

        conflict = conflicting_bookings.only("id", "arrival_at", "departure_at").first()

        if conflict:
            raise serializers.ValidationError(
                {
                    "room": [
                        f"{room} is already booked from "
                        f"{conflict.arrival_at} to {conflict.departure_at}."
                    ]
                }
            )

    def validate_same_day_full_block(self, room, arrival_at, instance=None):
        india_tz = ZoneInfo("Asia/Kolkata")

        local_arrival = arrival_at.astimezone(india_tz)
        arrival_date = local_arrival.date()

        bookings = Booking.objects.filter(
            room=room,
            status=Booking.STATUS_ACTIVE,
        )

        if instance:
            bookings = bookings.exclude(pk=instance.pk)

        for booking in bookings:
            local_departure = booking.departure_at.astimezone(india_tz)
            cooling_end = local_departure + COOLING_PERIOD

            if (
                local_departure.date() == arrival_date
                and local_departure <= local_arrival
                and cooling_end.time() > time(hour=18)
            ):
                raise serializers.ValidationError(
                    {
                        "room": [
                            f"{room} is unavailable for {arrival_date}. "
                            f"Previous checkout was {local_departure.strftime('%d %b %Y, %I:%M %p')}. "
                            f"Cooling ends at {cooling_end.strftime('%d %b %Y, %I:%M %p')}."
                        ]
                    }
                )
    def validate_cooling_period(self, room, arrival_at, instance=None):
        cooling_period_booking = Booking.objects.filter(
            room=room,
            status__in=[
                Booking.STATUS_ACTIVE,
                Booking.STATUS_EXPIRED,
            ],
            departure_at__lte=arrival_at,
            departure_at__gt=arrival_at - COOLING_PERIOD,
        )

        if instance:
            cooling_period_booking = cooling_period_booking.exclude(pk=instance.pk)

        cooling_period_booking = (
            cooling_period_booking
            .only("id", "departure_at", "status")
            .order_by("-departure_at")
            .first()
        )

        if cooling_period_booking:
            available_after = cooling_period_booking.departure_at + COOLING_PERIOD

            raise serializers.ValidationError(
                {
                    "room": [
                        f"{room} is in cooling period after previous booking. "
                        f"It can be booked after {available_after}."
                    ]
                }
            )

    def validate_next_booking_cooling_period(self, room, departure_at, instance=None):
        cooling_end = departure_at + COOLING_PERIOD

        next_booking = Booking.objects.filter(
            room=room,
            status=Booking.STATUS_ACTIVE,
            arrival_at__gte=departure_at,
            arrival_at__lt=cooling_end,
        )

        if instance:
            next_booking = next_booking.exclude(pk=instance.pk)

        next_booking = (
            next_booking
            .only("id", "arrival_at", "status")
            .order_by("arrival_at")
            .first()
        )

        if next_booking:
            raise serializers.ValidationError(
                {
                    "departure_at": [
                        f"{room} needs a 1-hour gap before the next booking. "
                        f"Next booking starts at {next_booking.arrival_at}. "
                        f"Departure must be at or before {next_booking.arrival_at - COOLING_PERIOD}."
                    ]
                }
            )


class RoomAvailabilityDaySerializer(serializers.Serializer):
    date = serializers.DateField()
    total_rooms = serializers.IntegerField()
    booked_rooms = serializers.IntegerField()
    available_rooms = serializers.IntegerField()


class RoomAvailabilityGroupSerializer(serializers.Serializer):
    prefix = serializers.CharField()
    total_rooms = serializers.IntegerField()
    calendar = RoomAvailabilityDaySerializer(many=True)


class RoomAvailabilityResponseSerializer(serializers.Serializer):
    month = serializers.IntegerField()
    year = serializers.IntegerField()
    groups = RoomAvailabilityGroupSerializer(many=True)


class BookingListQuerySerializer(serializers.Serializer):
    prefix = serializers.CharField(required=False, allow_blank=False)
    arrival_from = serializers.DateField(required=False)
    departure_to = serializers.DateField(required=False)
    status = serializers.CharField(required=False, allow_blank=False)

    def validate_status(self, value):
        status_value = value.lower()
        valid_statuses = {choice[0] for choice in Booking.STATUS_CHOICES}

        if status_value not in valid_statuses:
            raise serializers.ValidationError("Invalid booking status.")

        return status_value


class RoomAvailabilityCalendarQuerySerializer(serializers.Serializer):
    month = serializers.IntegerField(required=False, min_value=1, max_value=12)
    year = serializers.IntegerField(required=False, min_value=1)


class RoomAvailabilityDetailsQuerySerializer(serializers.Serializer):
    date = serializers.DateField(required=True)
    prefix = serializers.CharField(required=False, allow_blank=False)


class AvailableRoomsByDateQuerySerializer(serializers.Serializer):
    date = serializers.DateField(required=True)
    prefix = serializers.CharField(required=True, allow_blank=False)


class AvailableRoomsByDateRangeQuerySerializer(serializers.Serializer):
    arrival_date = serializers.DateField(required=True)
    departure_date = serializers.DateField(required=True)
    prefix = serializers.CharField(required=True, allow_blank=False)

    def validate(self, attrs):
        if attrs["arrival_date"] > attrs["departure_date"]:
            attrs["arrival_date"], attrs["departure_date"] = (
                attrs["departure_date"],
                attrs["arrival_date"],
            )

        return attrs
