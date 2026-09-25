from datetime import time, timedelta
from decimal import Decimal
import re

from django.utils import timezone
from rest_framework import serializers

from .constants import COOLING_PERIOD
from .models import Booking, BookingChargeSheet, BookingEditHistory, BookingRequest, BookingShare
from hostels.models import Room

from zoneinfo import ZoneInfo


PHONE_ALLOWED_RE = re.compile(r"^\+?[0-9][0-9\s().-]*$")
PHONE_DIGIT_RE = re.compile(r"\d")
ATTENDER_CHARGE_PER_SHIFT = Decimal("850")
INDIA_TZ = ZoneInfo("Asia/Kolkata")
ROOM_CHARGE_RATES = {
    ("Gamma", True): Decimal("1500"),
    ("Gamma", False): Decimal("1300"),
    ("Beta", True): Decimal("1000"),
    ("Beta", False): Decimal("800"),
}
FOREIGN_ROOM_CHARGE_RATES = {
    ("Gamma", True): Decimal("2000"),
    ("Gamma", False): Decimal("1800"),
    ("Beta", True): Decimal("1500"),
    ("Beta", False): Decimal("1300"),
}


class BookingSerializer(serializers.ModelSerializer):
    room = serializers.PrimaryKeyRelatedField(queryset=Room.objects.filter(is_active=True))
    room_name = serializers.SerializerMethodField()
    created_by_name = serializers.SerializerMethodField()
    booking_reference_number = serializers.SerializerMethodField()

    class Meta:
        model = Booking
        fields = [
            "id", "booking_reference_number", "room", "room_name", "arrival_at", "departure_at",

            "visitor_name",
            "visitor_designation",
            "visitor_organisation",
            "visitor_gender",
            "visitor_nationality",
            "visitor_mobile",
            "visitor_email",
            "purpose_of_visit",
            "remarks",
            "visitor_category",
            "budget_head_type",
            "budget_head_value",
            "budget_head_name",
            "budget_head_department_name",
            "budget_head_project_code",
            "attender_required",
            "attender_morning_shift",
            "attender_morning_chargeable",
            "attender_evening_shift",
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
            "id",
            "booking_reference_number",
            "room_name",
            "status",
            "created_at",
            "created_by_name",
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

"visitor_gender": {
    "required": False,
    "allow_blank": True
},

"visitor_nationality": {"required": False, "allow_blank": True},

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
            "visitor_mobile": {"required": False, "allow_blank": True},
            "visitor_email": {"required": False, "allow_blank": True},
            "purpose_of_visit": {"required": False, "allow_blank": True},
            "remarks": {"required": False, "allow_blank": True},
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

    def get_created_by_name(self, obj):
        user = getattr(obj, "created_by", None)
        if user:
            full_name = user.get_full_name().strip()
            return full_name or user.email or user.username

        return obj.created_by_name or ""

    def get_booking_reference_number(self, obj):
        return obj.booking_reference_number

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

        if instance is None or not self.partial:
            self.set_default_optional_fields(attrs)
        self.validate_attender_fields(attrs)
        self.validate_charge_fields(attrs)
        self.validate_room_conflict(room, arrival_at, departure_at, instance)
        self.validate_same_day_full_block(room, arrival_at, instance)
        self.validate_cooling_period(room, arrival_at, instance)
        self.validate_next_booking_cooling_period(room, departure_at, instance)
        attrs["status"] = (
            Booking.STATUS_EXPIRED
            if departure_at <= timezone.now()
            else Booking.STATUS_ACTIVE
        )

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
            if (
                amount_field == "room_charges_amount"
                and charge_status == Booking.CHARGE_STATUS_YES
                and amount <= 0
            ):
                calculated_amount = self.calculate_room_charges_amount(attrs)
                if calculated_amount is not None:
                    attrs[amount_field] = calculated_amount
                    amount = calculated_amount

            if (
                amount_field == "attender_charges_amount"
                and charge_status == Booking.CHARGE_STATUS_YES
                and amount <= 0
            ):
                calculated_amount = self.calculate_attender_charges_amount(attrs)
                attrs[amount_field] = calculated_amount
                amount = calculated_amount

            if charge_status == Booking.CHARGE_STATUS_YES and amount <= 0:
                raise serializers.ValidationError({
                    amount_field: [f"{label} is required when charges are received."]
                })

            if charge_status != Booking.CHARGE_STATUS_YES:
                attrs[amount_field] = 0

    def calculate_room_charges_amount(self, attrs):
        room = attrs.get("room", getattr(self.instance, "room", None))
        if not room:
            return None
        visitor_nationality = attrs.get(
            "visitor_nationality",
            getattr(self.instance, "visitor_nationality", ""),
        )
        rates = (
            FOREIGN_ROOM_CHARGE_RATES
            if visitor_nationality == Booking.VISITOR_NATIONALITY_FOREIGNER
            else ROOM_CHARGE_RATES
        )
        rate = rates.get((room.prefix, room.has_attached_bath))
        if rate is None:
            return None
        return rate * self.booking_stay_days(attrs)

    def calculate_attender_charges_amount(self, attrs):
        instance = self.instance
        attender_required = attrs.get(
            "attender_required",
            getattr(instance, "attender_required", False),
        )
        if not attender_required:
            return Decimal("0")
        morning_shift = attrs.get(
            "attender_morning_shift",
            getattr(instance, "attender_morning_shift", False),
        )
        morning_chargeable = attrs.get(
            "attender_morning_chargeable",
            getattr(instance, "attender_morning_chargeable", True),
        )
        evening_shift = attrs.get(
            "attender_evening_shift",
            getattr(instance, "attender_evening_shift", False),
        )
        chargeable_shift_count = 0
        if morning_shift and morning_chargeable:
            chargeable_shift_count += 1
        if evening_shift:
            chargeable_shift_count += 1
        return ATTENDER_CHARGE_PER_SHIFT * chargeable_shift_count * self.booking_stay_days(attrs)

    def booking_stay_days(self, attrs):
        instance = self.instance
        arrival_at = attrs.get("arrival_at", getattr(instance, "arrival_at", None))
        departure_at = attrs.get("departure_at", getattr(instance, "departure_at", None))
        if not arrival_at or not departure_at:
            return Decimal("1")

        arrival_date = timezone.localtime(arrival_at, INDIA_TZ).date()
        departure_date = timezone.localtime(departure_at, INDIA_TZ).date()
        nights = max((departure_date - arrival_date).days, 0)
        return Decimal(max(nights + 1, 1))

    def validate_attender_fields(self, attrs):
        instance = self.instance

        attender_required = attrs.get(
            "attender_required",
            getattr(instance, "attender_required", False)
        )

        morning_shift = attrs.get(
            "attender_morning_shift",
            getattr(instance, "attender_morning_shift", False)
        )

        evening_shift = attrs.get(
            "attender_evening_shift",
            getattr(instance, "attender_evening_shift", False)
        )

        if attender_required and not any([
            morning_shift,
            evening_shift,
        ]):
            raise serializers.ValidationError({
                "attender_shift": [
                    "Please select at least one attender shift."
                ]
            })

        if not attender_required:
            attrs["attender_morning_shift"] = False
            attrs["attender_morning_chargeable"] = False
            attrs["attender_evening_shift"] = False
        elif not morning_shift:
            attrs["attender_morning_chargeable"] = False

    def set_default_optional_fields(self, attrs):
        optional_fields = [
            "visitor_designation",
            "visitor_organisation",
            "visitor_mobile",
            "visitor_email",
            "purpose_of_visit",
            "remarks",
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
    has_before_6pm_booking = serializers.BooleanField(required=False)
    has_partial_booking = serializers.BooleanField(required=False)


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
    search = serializers.CharField(required=False, allow_blank=True, trim_whitespace=True)
    arrival_from = serializers.DateField(required=False)
    departure_to = serializers.DateField(required=False)
    status = serializers.CharField(required=False, allow_blank=False)

    def validate_status(self, value):
        status_value = value.lower()
        valid_statuses = {choice[0] for choice in Booking.STATUS_CHOICES}

        if status_value not in valid_statuses:
            raise serializers.ValidationError("Invalid booking status.")

        return status_value


class BookingChargeSheetQuerySerializer(serializers.Serializer):
    prefix = serializers.CharField(required=False, allow_blank=False)
    search = serializers.CharField(required=False, allow_blank=True, trim_whitespace=True)
    payment = serializers.CharField(required=False, allow_blank=False)
    checkout_from = serializers.DateField(required=False)
    checkout_to = serializers.DateField(required=False)
    ordering = serializers.CharField(required=False, allow_blank=False)

    VALID_PAYMENT_FILTERS = {"received", "pending"}
    VALID_ORDERING_FIELDS = {
        "serial_no",
        "check_in",
        "check_out",
        "booking_reference_id",
        "requestor_name",
        "guest_name",
        "purpose_event",
        "remarks",
        "delta",
        "gamma",
        "beta",
        "room_charges_amount",
        "attender_charges_amount",
        "total_charges",
        "payment_received_date",
        "budget_head_name",
        "created_at",
    }

    def validate_payment(self, value):
        payment_filter = value.lower()
        if payment_filter not in self.VALID_PAYMENT_FILTERS:
            raise serializers.ValidationError("Invalid payment filter.")
        return payment_filter

    def validate_ordering(self, value):
        ordering = value.strip()
        field_name = ordering[1:] if ordering.startswith("-") else ordering
        if field_name not in self.VALID_ORDERING_FIELDS:
            raise serializers.ValidationError("Invalid ordering field.")
        return ordering


class BookingChargeSheetSerializer(serializers.ModelSerializer):
    serial_no = serializers.IntegerField(source="id", read_only=True)
    check_in = serializers.DateTimeField(source="booking.arrival_at", read_only=True)
    check_out = serializers.DateTimeField(source="booking.departure_at", read_only=True)
    booking_reference_id = serializers.SerializerMethodField()
    delta = serializers.SerializerMethodField()
    gamma = serializers.SerializerMethodField()
    beta = serializers.SerializerMethodField()
    total_charges = serializers.DecimalField(max_digits=10, decimal_places=2, read_only=True)

    class Meta:
        model = BookingChargeSheet
        fields = [
            "id",
            "serial_no",
            "booking",
            "check_in",
            "check_out",
            "booking_reference_id",
            "requestor_name",
            "guest_name",
            "purpose_event",
            "remarks",
            "delta",
            "gamma",
            "beta",
            "room_charges_amount",
            "attender_charges_amount",
            "total_charges",
            "payment_received_date",
            "budget_head_name",
            "created_at",
            "updated_at",
        ]
        read_only_fields = [
            "id",
            "serial_no",
            "booking",
            "check_in",
            "check_out",
            "booking_reference_id",
            "delta",
            "gamma",
            "beta",
            "total_charges",
            "created_at",
            "updated_at",
        ]
        extra_kwargs = {
            "requestor_name": {"required": False, "allow_blank": True},
            "guest_name": {"required": False, "allow_blank": True},
            "purpose_event": {"required": False, "allow_blank": True},
            "remarks": {"required": False, "allow_blank": True},
            "room_charges_amount": {"required": False, "min_value": 0},
            "attender_charges_amount": {"required": False, "min_value": 0},
            "payment_received_date": {"required": False, "allow_null": True},
            "budget_head_name": {"required": False, "allow_blank": True},
        }

    def get_booking_reference_id(self, obj):
        return obj.booking.booking_reference_number

    def get_delta(self, obj):
        return self.get_room_number_for_prefix(obj, "Delta")

    def get_gamma(self, obj):
        return self.get_room_number_for_prefix(obj, "Gamma")

    def get_beta(self, obj):
        return self.get_room_number_for_prefix(obj, "Beta")

    def get_room_number_for_prefix(self, obj, prefix):
        room = getattr(obj.booking, "room", None)
        if not room or room.prefix != prefix:
            return ""
        return str(room)


class BookingShareSerializer(serializers.ModelSerializer):
    url = serializers.SerializerMethodField()
    validity = serializers.ChoiceField(
        choices=[
            ("24h", "24 hours"),
            ("1w", "1 week"),
            ("1m", "1 month"),
        ],
        write_only=True,
        required=False,
        default="1w",
    )

    VALIDITY_DELTAS = {
        "24h": timedelta(hours=24),
        "1w": timedelta(days=7),
        "1m": timedelta(days=30),
    }

    class Meta:
        model = BookingShare
        fields = [
            "id",
            "token",
            "share_type",
            "title",
            "filters",
            "validity",
            "expires_at",
            "url",
            "created_at",
        ]
        read_only_fields = ["id", "token", "expires_at", "url", "created_at"]
        extra_kwargs = {
            "title": {"required": False, "allow_blank": True},
            "filters": {"required": False},
            "share_type": {"required": False},
        }

    def validate_share_type(self, value):
        valid_share_types = {
            BookingShare.SHARE_TYPE_BOOKING_SHEET,
            BookingShare.SHARE_TYPE_CHARGE_SHEET,
        }
        if value not in valid_share_types:
            raise serializers.ValidationError("Invalid share type.")
        return value

    def validate_filters(self, value):
        if value is not None and not isinstance(value, dict):
            raise serializers.ValidationError("Filters must be an object.")
        return value or {}

    def normalize_filters(self, filters, query_serializer_class, allowed_keys):
        normalized = {}

        for key, raw_value in (filters or {}).items():
            if key not in allowed_keys or raw_value in (None, "", "all"):
                continue
            normalized[key] = raw_value

        query_serializer = query_serializer_class(data=normalized)
        query_serializer.is_valid(raise_exception=True)
        normalized_filters = {}
        for key, filter_value in query_serializer.validated_data.items():
            normalized_filters[key] = filter_value.isoformat() if hasattr(filter_value, "isoformat") else filter_value
        return normalized_filters

    def validate(self, attrs):
        share_type = attrs.get("share_type") or BookingShare.SHARE_TYPE_BOOKING_SHEET
        raw_filters = attrs.get("filters") or {}
        if share_type == BookingShare.SHARE_TYPE_CHARGE_SHEET:
            attrs["filters"] = self.normalize_filters(
                raw_filters,
                BookingChargeSheetQuerySerializer,
                {"prefix", "search", "payment", "checkout_from", "checkout_to", "ordering"},
            )
        else:
            attrs["filters"] = self.normalize_filters(
                raw_filters,
                BookingListQuerySerializer,
                {"prefix", "arrival_from", "departure_to", "status"},
            )
        return attrs

    def create(self, validated_data):
        validity = validated_data.pop("validity", "1w")
        share_type = validated_data.get("share_type") or BookingShare.SHARE_TYPE_BOOKING_SHEET
        if not validated_data.get("title"):
            validated_data["title"] = "Charges Sheet" if share_type == BookingShare.SHARE_TYPE_CHARGE_SHEET else "Booking Sheet"
        validated_data["expires_at"] = timezone.now() + self.VALIDITY_DELTAS[validity]
        return super().create(validated_data)

    def get_url(self, obj):
        request = self.context.get("request")
        if not request:
            return ""

        from django.urls import reverse

        route_name = (
            "webapp:shared-charges"
            if obj.share_type == BookingShare.SHARE_TYPE_CHARGE_SHEET
            else "webapp:shared-bookings"
        )
        path = reverse(route_name, kwargs={"token": obj.token})
        return request.build_absolute_uri(path)


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


class BookingEditHistorySerializer(serializers.ModelSerializer):
    class Meta:
        model = BookingEditHistory
        fields = [
            "id",
            "edited_by_name",
            "edited_by_email",
            "field_name",
            "field_label",
            "old_value",
            "new_value",
            "edited_at",
        ]
        read_only_fields = fields


class BookingDetailSerializer(BookingSerializer):
    edit_history = BookingEditHistorySerializer(many=True, read_only=True)

    class Meta(BookingSerializer.Meta):
        fields = BookingSerializer.Meta.fields + ["edit_history"]
        read_only_fields = BookingSerializer.Meta.read_only_fields + ["edit_history"]


class BookingRequestBaseSerializer(serializers.ModelSerializer):
    requester_name = serializers.SerializerMethodField()
    requester_email = serializers.SerializerMethodField()
    preferred_room = serializers.PrimaryKeyRelatedField(
        queryset=Room.objects.filter(is_active=True),
        required=False,
        allow_null=True,
    )
    preferred_room_name = serializers.SerializerMethodField()
    approved_booking_id = serializers.SerializerMethodField()
    assigned_room_name = serializers.SerializerMethodField()
    reviewed_by_name = serializers.SerializerMethodField()
    remarks = serializers.CharField(source="delete_reason", read_only=True)

    class Meta:
        model = BookingRequest
        fields = [
            "id",
            "requester",
            "requester_name",
            "requester_email",
            "status",
            "requested_at",
            "reviewed_at",
            "reviewed_by",
            "reviewed_by_name",
            "admin_remarks",
            "approved_booking_id",
            "assigned_room_name",
            "is_deleted",
            "deleted_at",
            "deleted_by_name",
            "deleted_by_role",
            "remarks",
            "arrival_at",
            "departure_at",
            "preferred_prefix",
            "preferred_room",
            "preferred_room_name",
            "room_preference_note",
            "visitor_name",
            "visitor_designation",
            "visitor_organisation",
            "visitor_gender",
            "visitor_nationality",
            "visitor_mobile",
            "visitor_email",
            "visitor_category",
            "purpose_of_visit",
            "budget_head_type",
            "budget_head_value",
            "budget_head_name",
            "budget_head_department_name",
            "budget_head_project_code",
            "attender_required",
            "attender_morning_shift",
            "attender_morning_chargeable",
            "attender_evening_shift",
            "requestor_name",
            "requestor_designation",
            "requestor_department",
            "requestor_mobile",
            "requestor_email",
        ]
        read_only_fields = [
            "id",
            "requester",
            "requester_name",
            "requester_email",
            "status",
            "requested_at",
            "reviewed_at",
            "reviewed_by",
            "reviewed_by_name",
            "admin_remarks",
            "approved_booking_id",
            "assigned_room_name",
            "is_deleted",
            "deleted_at",
            "deleted_by_name",
            "deleted_by_role",
            "remarks",
            "preferred_room_name",
        ]

    def get_requester_name(self, obj):
        user = getattr(obj, "requester", None)
        if not user:
            return ""
        return user.get_full_name().strip() or user.email or user.username

    def get_requester_email(self, obj):
        user = getattr(obj, "requester", None)
        return user.email if user else ""

    def get_preferred_room_name(self, obj):
        room = getattr(obj, "preferred_room", None)
        return str(room) if room else ""

    def get_approved_booking_id(self, obj):
        booking = getattr(obj, "approved_booking", None)
        return booking.id if booking else None

    def get_assigned_room_name(self, obj):
        booking = getattr(obj, "approved_booking", None)
        return str(booking.room) if booking and booking.room else ""

    def get_reviewed_by_name(self, obj):
        user = getattr(obj, "reviewed_by", None)
        if not user:
            return ""
        return user.get_full_name().strip() or user.email or user.username


class RequesterBookingRequestCreateSerializer(BookingRequestBaseSerializer):
    class Meta(BookingRequestBaseSerializer.Meta):
        read_only_fields = BookingRequestBaseSerializer.Meta.read_only_fields
        extra_kwargs = {
            "visitor_name": {
                "required": True,
                "allow_blank": False,
                "trim_whitespace": True,
                "error_messages": {
                    "blank": "Visitor name is required.",
                    "required": "Visitor name is required.",
                },
            },
            "visitor_designation": {"required": False, "allow_blank": True},
            "visitor_organisation": {"required": False, "allow_blank": True},
            "visitor_gender": {"required": False, "allow_blank": True},
            "visitor_nationality": {"required": False, "allow_blank": True},
            "visitor_mobile": {"required": False, "allow_blank": True},
            "visitor_email": {"required": False, "allow_blank": True},
            "visitor_category": {"required": False, "allow_blank": True},
            "purpose_of_visit": {"required": False, "allow_blank": True},
            "budget_head_type": {"required": False, "allow_blank": True},
            "budget_head_value": {"required": False, "allow_blank": True},
            "budget_head_name": {"required": False, "allow_blank": True},
            "budget_head_department_name": {"required": False, "allow_blank": True},
            "budget_head_project_code": {"required": False, "allow_blank": True},
            "preferred_prefix": {"required": False, "allow_blank": True},
            "room_preference_note": {"required": False, "allow_blank": True},
            "requestor_name": {"required": False, "allow_blank": True},
            "requestor_designation": {"required": False, "allow_blank": True},
            "requestor_department": {"required": False, "allow_blank": True},
            "requestor_mobile": {"required": False, "allow_blank": True},
            "requestor_email": {"required": False, "allow_blank": True},
        }

    def validate_visitor_mobile(self, value):
        return BookingSerializer().validate_optional_mobile(value, "Visitor mobile")

    def validate_requestor_mobile(self, value):
        return BookingSerializer().validate_optional_mobile(value, "Requestor mobile")

    def validate(self, attrs):
        instance = self.instance
        arrival_at = attrs.get("arrival_at", getattr(instance, "arrival_at", None))
        departure_at = attrs.get("departure_at", getattr(instance, "departure_at", None))

        if not arrival_at or not departure_at:
            raise serializers.ValidationError(
                "Arrival datetime and departure datetime are required."
            )

        if departure_at <= arrival_at:
            raise serializers.ValidationError({
                "departure_at": ["Departure datetime must be after arrival datetime."]
            })

        attender_required = attrs.get(
            "attender_required",
            getattr(instance, "attender_required", False),
        )
        has_shift = any([
            attrs.get(
                "attender_morning_shift",
                getattr(instance, "attender_morning_shift", False),
            ),
            attrs.get(
                "attender_evening_shift",
                getattr(instance, "attender_evening_shift", False),
            ),
        ])

        if attender_required and not has_shift:
            raise serializers.ValidationError({
                "attender_shift": ["Please select at least one attender shift."]
            })

        if not attender_required:
            attrs["attender_morning_shift"] = False
            attrs["attender_morning_chargeable"] = False
            attrs["attender_evening_shift"] = False
        elif not attrs.get(
            "attender_morning_shift",
            getattr(instance, "attender_morning_shift", False),
        ):
            attrs["attender_morning_chargeable"] = False

        return attrs


class RequesterBookingRequestListSerializer(BookingRequestBaseSerializer):
    pass


class AdminBookingRequestSerializer(BookingRequestBaseSerializer):
    pass


class BookingRequestApproveSerializer(serializers.Serializer):
    room = serializers.PrimaryKeyRelatedField(queryset=Room.objects.filter(is_active=True))
    remarks = serializers.CharField(required=False, allow_blank=True, trim_whitespace=True)
    booking_remarks = serializers.CharField(required=False, allow_blank=True, trim_whitespace=True)


class BookingRequestRejectSerializer(serializers.Serializer):
    remarks = serializers.CharField(required=True, allow_blank=False, trim_whitespace=True)


class BookingRequestSendBackSerializer(serializers.Serializer):
    remarks = serializers.CharField(required=True, allow_blank=False, trim_whitespace=True)


class BookingRequestDeleteSerializer(serializers.Serializer):
    remarks = serializers.CharField(required=False, allow_blank=True, trim_whitespace=True)
