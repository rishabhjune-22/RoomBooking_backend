import calendar
import logging
from datetime import datetime, time, timedelta
from zoneinfo import ZoneInfo
from django.db import transaction
from django.db.models import Count
from django.shortcuts import get_object_or_404
from django.utils import timezone

from rest_framework import status
from rest_framework.generics import CreateAPIView, ListAPIView, RetrieveAPIView, UpdateAPIView
from rest_framework.permissions import AllowAny
from rest_framework.throttling import ScopedRateThrottle
from rest_framework.views import APIView

from backend.responses import api_success, serializer_error_response
from hostels.models import Room

from .constants import COOLING_PERIOD
from .idempotency import begin_idempotent_request, complete_idempotent_request
from .models import Booking, BookingIdempotencyRecord
from .serializers import (
    AvailableRoomsByDateQuerySerializer,
    AvailableRoomsByDateRangeQuerySerializer,
    BookingListQuerySerializer,
    BookingSerializer,
    RoomAvailabilityCalendarQuerySerializer,
    RoomAvailabilityDetailsQuerySerializer,
)


INDIA_TZ = ZoneInfo("Asia/Kolkata")
logger = logging.getLogger(__name__)


def invalid_query_params_response(serializer):
    return serializer_error_response(serializer, "Invalid query parameters.")


def action_response_body(message, booking):
    return {
        "success": True,
        "message": message,
        "data": {
            "booking_id": booking.id,
            "room_id": booking.room.id,
            "room_name": str(booking.room),
            "status": booking.status,
            "budget_head_name": booking.budget_head_name,
            "budget_head_department_name": booking.budget_head_department_name,
            "budget_head_project_code": booking.budget_head_project_code,
        },
    }


def delete_response_body(booking_id):
    return {
        "success": True,
        "message": "Booking deleted successfully",
        "data": {
            "booking_id": booking_id,
        },
    }


def get_local_date_bounds(selected_date):
    start_at = datetime.combine(selected_date, time.min, tzinfo=INDIA_TZ)
    end_at = start_at + timedelta(days=1)
    return start_at, end_at


def get_local_date_range_bounds(start_date, end_date):
    start_at, _ = get_local_date_bounds(start_date)
    _, end_at = get_local_date_bounds(end_date)
    return start_at, end_at


def filter_active_bookings_overlapping_date(queryset, selected_date):
    start_at, end_at = get_local_date_bounds(selected_date)
    return queryset.filter(
        status=Booking.STATUS_ACTIVE,
        arrival_at__lt=end_at,
        departure_at__gte=start_at,
    )


def filter_active_bookings_overlapping_range(queryset, start_date, end_date):
    start_at, end_at = get_local_date_range_bounds(start_date, end_date)
    return queryset.filter(
        status=Booking.STATUS_ACTIVE,
        arrival_at__lt=end_at,
        departure_at__gte=start_at,
    )


def mark_departure_day_availability(
        room_id,
        cooling_end,
        unavailable_room_ids,
        partial_available_rooms=None,
        orange_room_ids=None,
):
    if cooling_end.time() > time(hour=18):
        unavailable_room_ids.add(room_id)
        return

    if partial_available_rooms is not None:
        current_cooling_end = partial_available_rooms.get(room_id)
        if current_cooling_end is None or cooling_end > current_cooling_end:
            partial_available_rooms[room_id] = cooling_end

    if orange_room_ids is not None:
        orange_room_ids.add(room_id)


def get_rooms_for_prefix(prefix):
    return list(
        Room.objects
        .filter(prefix__iexact=prefix)
        .only(
            "id",
            "prefix",
            "number",
            "room_type",
            "has_attached_bath",
            "display_order",
        )
        .order_by("display_order", "number")
    )


def build_room_response(room, availability_status="available", cooling_end=None):
    return {
        "room_id": room.id,
        "room_number": room.number,
        "room_name": f"{room.prefix} {room.number}",
        "selection_label": room.selection_label,
        "prefix": room.prefix,
        "availability_status": availability_status,
        "available_from_date": cooling_end.date() if cooling_end else None,
        "available_from_time": cooling_end.strftime("%I:%M %p") if cooling_end else None,
    }


def apply_booking_availability_for_date(
        booking,
        selected_date,
        unavailable_room_ids,
        partial_available_rooms=None,
        orange_room_ids=None,
):
    local_arrival = booking.arrival_at.astimezone(INDIA_TZ)
    local_departure = booking.departure_at.astimezone(INDIA_TZ)
    cooling_end = local_departure + COOLING_PERIOD

    arrival_date = local_arrival.date()
    departure_date = local_departure.date()

    if arrival_date == departure_date:
        if selected_date == arrival_date:
            mark_departure_day_availability(
                booking.room_id,
                cooling_end,
                unavailable_room_ids,
                partial_available_rooms=partial_available_rooms,
                orange_room_ids=orange_room_ids,
            )
        return

    if arrival_date <= selected_date < departure_date:
        unavailable_room_ids.add(booking.room_id)
    elif selected_date == departure_date:
        mark_departure_day_availability(
            booking.room_id,
            cooling_end,
            unavailable_room_ids,
            partial_available_rooms=partial_available_rooms,
            orange_room_ids=orange_room_ids,
        )


def apply_booking_availability_for_range(
        booking,
        arrival_date,
        departure_date,
        unavailable_room_ids,
        partial_available_rooms=None,
):
    local_arrival = booking.arrival_at.astimezone(INDIA_TZ)
    local_departure = booking.departure_at.astimezone(INDIA_TZ)
    cooling_end = local_departure + COOLING_PERIOD

    booking_arrival_date = local_arrival.date()
    booking_departure_date = local_departure.date()

    if booking_arrival_date == booking_departure_date:
        if arrival_date <= booking_arrival_date <= departure_date:
            mark_departure_day_availability(
                booking.room_id,
                cooling_end,
                unavailable_room_ids,
                partial_available_rooms=partial_available_rooms,
            )
        return

    if booking_arrival_date <= departure_date and arrival_date < booking_departure_date:
        unavailable_room_ids.add(booking.room_id)
    elif arrival_date <= booking_departure_date <= departure_date:
        mark_departure_day_availability(
            booking.room_id,
            cooling_end,
            unavailable_room_ids,
            partial_available_rooms=partial_available_rooms,
        )


def lock_rooms_for_booking_write(*room_ids):
    normalized_ids = set()

    for room_id in room_ids:
        if room_id is None:
            continue

        try:
            normalized_ids.add(int(room_id))
        except (TypeError, ValueError):
            continue

    normalized_ids = sorted(normalized_ids)
    if normalized_ids:
        list(
            Room.objects
            .select_for_update()
            .filter(pk__in=normalized_ids)
            .order_by("pk")
        )


class BookingCreateView(CreateAPIView):
    queryset = Booking.objects.select_related("room").all()
    serializer_class = BookingSerializer
    permission_classes = [AllowAny]
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "booking_mutation"

    @transaction.atomic
    def create(self, request, *args, **kwargs):
        idempotency = begin_idempotent_request(
            request,
            BookingIdempotencyRecord.ACTION_CREATE,
        )
        if idempotency.response is not None:
            return idempotency.response

        lock_rooms_for_booking_write(request.data.get("room"))

        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        booking = serializer.save()
        response_body = action_response_body("Booking created successfully", booking)
        complete_idempotent_request(
            idempotency.record,
            response_body,
            status.HTTP_201_CREATED,
            booking_id=booking.id,
        )
        logger.info(
            "booking_created",
            extra={
                "event": "booking_created",
                "booking_id": booking.id,
                "room_id": booking.room_id,
            },
        )

        return api_success(
            response_body["message"],
            response_body["data"],
            status_code=status.HTTP_201_CREATED,
        )


class BookingListView(ListAPIView):
    serializer_class = BookingSerializer
    permission_classes = [AllowAny]
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "booking_read"

    def list(self, request, *args, **kwargs):
        serializer = BookingListQuerySerializer(data=request.query_params)
        if not serializer.is_valid():
            return invalid_query_params_response(serializer)

        self._validated_query_params = serializer.validated_data
        return super().list(request, *args, **kwargs)

    def get_query_params(self):
        if not hasattr(self, "_validated_query_params"):
            serializer = BookingListQuerySerializer(data=self.request.query_params)
            serializer.is_valid(raise_exception=True)
            self._validated_query_params = serializer.validated_data

        return self._validated_query_params

    def get_queryset(self):
        queryset = (
            Booking.objects
            .select_related("room")
            .all()
            .order_by("-created_at")
        )

        query_params = self.get_query_params()
        prefix = query_params.get("prefix")
        arrival_from = query_params.get("arrival_from")
        departure_to = query_params.get("departure_to")
        status_filter = query_params.get("status")

        if prefix:
            queryset = queryset.filter(room__prefix__iexact=prefix)

        if arrival_from:
            start_at, _ = get_local_date_bounds(arrival_from)
            queryset = queryset.filter(arrival_at__gte=start_at)

        if departure_to:
            _, end_at = get_local_date_bounds(departure_to)
            queryset = queryset.filter(departure_at__lt=end_at)

        if status_filter:
            queryset = queryset.filter(status__iexact=status_filter)

        return queryset


class BookingDetailView(RetrieveAPIView):
    queryset = Booking.objects.select_related("room").all()
    serializer_class = BookingSerializer
    permission_classes = [AllowAny]
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "booking_read"

    def retrieve(self, request, *args, **kwargs):
        booking = self.get_object()
        serializer = self.get_serializer(booking)

        return api_success(
            "Booking fetched successfully",
            serializer.data,
        )


class BookingUpdateView(UpdateAPIView):
    queryset = Booking.objects.select_related("room").all()
    serializer_class = BookingSerializer
    permission_classes = [AllowAny]
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "booking_mutation"

    @transaction.atomic
    def update(self, request, *args, **kwargs):
        partial = kwargs.pop("partial", False)
        instance = get_object_or_404(
            Booking.objects.select_for_update().select_related("room"),
            pk=kwargs.get("pk"),
        )

        lock_rooms_for_booking_write(
            instance.room_id,
            request.data.get("room"),
        )

        serializer = self.get_serializer(instance, data=request.data, partial=partial)
        serializer.is_valid(raise_exception=True)
        booking = serializer.save()
        logger.info(
            "booking_updated",
            extra={
                "event": "booking_updated",
                "booking_id": booking.id,
                "room_id": booking.room_id,
            },
        )

        return api_success(
            "Booking updated successfully",
            action_response_body("Booking updated successfully", booking)["data"],
        )

class BookingDeleteView(APIView):
    permission_classes = [AllowAny]
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "booking_mutation"

    @transaction.atomic
    def _delete_booking(self, request, pk):
        idempotency = begin_idempotent_request(
            request,
            BookingIdempotencyRecord.ACTION_DELETE,
            extra={"pk": pk},
        )
        if idempotency.response is not None:
            return idempotency.response

        booking = get_object_or_404(
            Booking.objects.select_for_update(),
            pk=pk,
        )

        booking_id = booking.id
        logger.info(
            "booking_deleted",
            extra={
                "event": "booking_deleted",
                "booking_id": booking.id,
                "room_id": booking.room_id,
                "visitor_name": booking.visitor_name,
            },
        )
        booking.delete()
        response_body = delete_response_body(booking_id)
        complete_idempotent_request(
            idempotency.record,
            response_body,
            status.HTTP_200_OK,
            booking_id=booking_id,
        )

        return api_success(response_body["message"], response_body["data"])

    def post(self, request, pk):
        return self._delete_booking(request, pk)

    def delete(self, request, pk):
        return self._delete_booking(request, pk)


class RoomAvailabilityCalendarView(APIView):
    permission_classes = [AllowAny]
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "availability"

    def get(self, request):
        today = timezone.localdate()

        query_serializer = RoomAvailabilityCalendarQuerySerializer(
            data=request.query_params
        )
        if not query_serializer.is_valid():
            return invalid_query_params_response(query_serializer)

        query_params = query_serializer.validated_data
        month = query_params.get("month", today.month)
        year = query_params.get("year", today.year)

        _, days_in_month = calendar.monthrange(year, month)
        month_start = datetime(year, month, 1).date()
        month_end = (
            datetime(year + 1, 1, 1).date()
            if month == 12
            else datetime(year, month + 1, 1).date()
        )

        room_counts = list(
            Room.objects
            .values("prefix")
            .annotate(total_rooms=Count("id"))
            .order_by("prefix")
        )

        room_prefix_by_id = dict(Room.objects.values_list("id", "prefix"))
        month_bookings = (
            filter_active_bookings_overlapping_range(
                Booking.objects,
                month_start,
                month_end - timedelta(days=1),
            )
            .only("id", "room_id", "arrival_at", "departure_at")
            .order_by("arrival_at", "id")
        )
        bookings_by_prefix = {}

        for booking in month_bookings:
            booking_prefix = room_prefix_by_id.get(booking.room_id)
            if booking_prefix:
                bookings_by_prefix.setdefault(booking_prefix, []).append(booking)

        groups = []

        for room_count in room_counts:
            prefix = room_count["prefix"]
            total_rooms = room_count["total_rooms"]
            calendar_data = []
            bookings = bookings_by_prefix.get(prefix, [])

            for day in range(1, days_in_month + 1):
                current_date = datetime(year, month, day).date()

                unavailable_room_ids = set()
                orange_room_ids = set()

                for booking in bookings:
                    apply_booking_availability_for_date(
                        booking,
                        current_date,
                        unavailable_room_ids,
                        orange_room_ids=orange_room_ids,
                    )

                unavailable_rooms = len(unavailable_room_ids)
                available_rooms = max(total_rooms - unavailable_rooms, 0)

                calendar_data.append(
                    {
                        "date": current_date,
                        "total_rooms": total_rooms,
                        "booked_rooms": unavailable_rooms,
                        "available_rooms": available_rooms,
                        "has_before_6pm_booking": len(orange_room_ids) > 0,
                    }
                )

            groups.append(
                {
                    "prefix": prefix,
                    "total_rooms": total_rooms,
                    "calendar": calendar_data,
                }
            )

        return api_success(
            "Room availability fetched successfully.",
            {
                "month": month,
                "year": year,
                "groups": groups,
            },
        )

class RoomAvailabilityDetailsView(APIView):
    permission_classes = [AllowAny]
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "availability"

    def get(self, request):
        query_serializer = RoomAvailabilityDetailsQuerySerializer(
            data=request.query_params
        )
        if not query_serializer.is_valid():
            return invalid_query_params_response(query_serializer)

        query_params = query_serializer.validated_data
        selected_date = query_params["date"]
        prefix = query_params.get("prefix")

        if prefix:
            room_ids = list(
                Room.objects
                .filter(prefix__iexact=prefix)
                .values_list("id", flat=True)
            )
            if not room_ids:
                return api_success(
                    "Availability details fetched successfully.",
                    {
                        "date": selected_date,
                        "prefix": prefix,
                        "total_bookings": 0,
                        "bookings": [],
                    },
                )
        else:
            room_ids = None

        bookings_query = filter_active_bookings_overlapping_date(
            Booking.objects.select_related("room"),
            selected_date,
        ).only(
            "id",
            "room_id",
            "visitor_name",
            "visitor_gender",
            "requestor_name",
            "arrival_at",
            "departure_at",
            "status",
            "room__id",
            "room__prefix",
            "room__number",
            "room__room_type",
            "room__has_attached_bath",
        )

        if room_ids is not None:
            bookings_query = bookings_query.filter(room_id__in=room_ids)

        booking_details = []

        for booking in bookings_query:
            local_arrival = booking.arrival_at.astimezone(INDIA_TZ)
            local_departure = booking.departure_at.astimezone(INDIA_TZ)

            arrival_date = local_arrival.date()
            departure_date = local_departure.date()

            if arrival_date <= selected_date <= departure_date:
                booking_details.append(
                    {
                        "booking_id": booking.id,
                        "room_id": booking.room.id,
                        "room_name": str(booking.room),
                        "selection_label": booking.room.selection_label,

                        "guest_name": booking.visitor_name,
                        "guest_gender": booking.visitor_gender,

                        "requestor_name": booking.requestor_name,

                        "arrival_at": booking.arrival_at,
                        "departure_at": booking.departure_at,

                        "status": booking.status,
                    }
                )

        return api_success(
            "Availability details fetched successfully.",
            {
                "date": selected_date,
                "prefix": prefix,
                "total_bookings": len(booking_details),
                "bookings": booking_details,
            },
        )

class AvailableRoomsByDateView(APIView):
    permission_classes = [AllowAny]
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "availability"

    def get(self, request):
        query_serializer = AvailableRoomsByDateQuerySerializer(
            data=request.query_params
        )
        if not query_serializer.is_valid():
            return invalid_query_params_response(query_serializer)

        query_params = query_serializer.validated_data
        selected_date = query_params["date"]
        prefix = query_params["prefix"]

        rooms = get_rooms_for_prefix(prefix)
        room_ids = [room.id for room in rooms]

        active_bookings = (
            filter_active_bookings_overlapping_date(
                Booking.objects,
                selected_date,
            )
            .filter(room_id__in=room_ids)
            .only("id", "room_id", "arrival_at", "departure_at")
        )

        unavailable_room_ids = set()

        # room_id -> cooling_end datetime
        partial_available_rooms = {}

        for booking in active_bookings:
            apply_booking_availability_for_date(
                booking,
                selected_date,
                unavailable_room_ids,
                partial_available_rooms=partial_available_rooms,
            )

        room_data = []

        for room in rooms:
            # unavailable wins over partial
            if room.id in unavailable_room_ids:
                continue

            if room.id in partial_available_rooms:
                room_data.append(build_room_response(
                    room,
                    availability_status="partial",
                    cooling_end=partial_available_rooms[room.id],
                ))
            else:
                room_data.append(build_room_response(room))

        return api_success(
            "Available rooms fetched successfully.",
            {
                "date": selected_date,
                "prefix": prefix,
                "total_available_rooms": len(room_data),
                "rooms": room_data,
            },
        )




class AvailableRoomsByDateRangeView(APIView):
    permission_classes = [AllowAny]
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "availability"

    def get(self, request):
        query_serializer = AvailableRoomsByDateRangeQuerySerializer(
            data=request.query_params
        )
        if not query_serializer.is_valid():
            return invalid_query_params_response(query_serializer)

        query_params = query_serializer.validated_data
        arrival_date = query_params["arrival_date"]
        departure_date = query_params["departure_date"]
        prefix = query_params["prefix"]

        rooms = get_rooms_for_prefix(prefix)
        room_ids = [room.id for room in rooms]

        active_bookings = (
            filter_active_bookings_overlapping_range(
                Booking.objects,
                arrival_date,
                departure_date,
            )
            .filter(room_id__in=room_ids)
            .only("id", "room_id", "arrival_at", "departure_at")
        )

        unavailable_room_ids = set()

        # room_id -> available_from time
        partial_available_rooms = {}

        for booking in active_bookings:
            apply_booking_availability_for_range(
                booking,
                arrival_date,
                departure_date,
                unavailable_room_ids,
                partial_available_rooms=partial_available_rooms,
            )

        room_data = []

        for room in rooms:
            # Fully unavailable rooms should not appear
            if room.id in unavailable_room_ids:
                continue

            if room.id in partial_available_rooms:
                room_data.append(build_room_response(
                    room,
                    availability_status="partial",
                    cooling_end=partial_available_rooms[room.id],
                ))

            else:
                room_data.append(build_room_response(room))

        return api_success(
            "Available rooms fetched successfully.",
            {
                "arrival_date": arrival_date,
                "departure_date": departure_date,
                "prefix": prefix,
                "total_available_rooms": len(room_data),
                "rooms": room_data,
            },
        )
