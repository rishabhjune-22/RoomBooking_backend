from datetime import datetime, timedelta, time
from zoneinfo import ZoneInfo

from django.db.models import DecimalField, ExpressionWrapper, F, Q
from django.shortcuts import get_object_or_404
from django.utils import timezone
from django.views.generic import TemplateView

from bookings.constants import COOLING_PERIOD
from bookings.models import Booking, BookingChargeSheet, BookingShare
from hostels.models import Room


INDIA_TZ = ZoneInfo("Asia/Kolkata")
BUILDING_ORDER = {"Delta": 0, "Gamma": 1, "Beta": 2}


class RoomBookingWebAppView(TemplateView):
    template_name = "webapp/index.html"


def parse_share_date(value):
    if not value:
        return None
    try:
        return datetime.strptime(value, "%Y-%m-%d").date()
    except (TypeError, ValueError):
        return None


def current_month_share_range():
    today = timezone.localtime(timezone.now(), INDIA_TZ).date()
    start_date = today.replace(day=1)
    if today.month == 12:
        next_month = today.replace(year=today.year + 1, month=1, day=1)
    else:
        next_month = today.replace(month=today.month + 1, day=1)
    return start_date, next_month - timedelta(days=1)


def active_share_queryset():
    return BookingShare.objects.filter(
        Q(expires_at__isnull=True) | Q(expires_at__gt=timezone.now()),
        is_active=True,
    )


def booking_charge_sheet_defaults(booking):
    return {
        "requestor_name": booking.requestor_name or "",
        "guest_name": booking.visitor_name or "",
        "purpose_event": booking.purpose_of_visit or "",
        "room_charges_amount": booking.room_charges_amount or 0,
        "attender_charges_amount": booking.attender_charges_amount or 0,
        "budget_head_name": (
            booking.budget_head_name
            or booking.budget_head_department_name
            or booking.budget_head_project_code
            or booking.budget_head_value
            or ""
        ),
    }


def ensure_booking_charge_sheet_rows():
    missing_bookings = (
        Booking.objects
        .filter(charge_sheet__isnull=True)
        .only(
            "id",
            "requestor_name",
            "visitor_name",
            "purpose_of_visit",
            "room_charges_amount",
            "attender_charges_amount",
            "budget_head_name",
            "budget_head_department_name",
            "budget_head_project_code",
            "budget_head_value",
        )
    )
    BookingChargeSheet.objects.bulk_create(
        [
            BookingChargeSheet(
                booking=booking,
                **booking_charge_sheet_defaults(booking),
            )
            for booking in missing_bookings
        ],
        ignore_conflicts=True,
    )


def share_date_range(start_date, end_date):
    if start_date > end_date:
        start_date, end_date = end_date, start_date

    dates = []
    cursor = start_date
    while cursor <= end_date:
        dates.append(cursor)
        cursor += timedelta(days=1)
    return dates


def local_date_bounds(selected_date):
    start_at = datetime.combine(selected_date, time.min, tzinfo=INDIA_TZ)
    return start_at, start_at + timedelta(days=1)


def booking_cell_text(booking):
    visitor_name = (booking.visitor_name or "").strip()
    organisation = (booking.visitor_organisation or "").strip()
    if organisation:
        return f"{visitor_name} ({organisation})" if visitor_name else organisation
    return visitor_name or "Booked"


def booking_availability_on_date(booking, selected_date):
    local_arrival = timezone.localtime(booking.arrival_at, INDIA_TZ)
    local_departure = timezone.localtime(booking.departure_at, INDIA_TZ)
    cooling_end = local_departure + COOLING_PERIOD
    arrival_date = local_arrival.date()
    departure_date = local_departure.date()
    cooling_end_date = cooling_end.date()
    cooling_ends_after_day = cooling_end_date != selected_date or (
        cooling_end.hour > 18 or (cooling_end.hour == 18 and cooling_end.minute > 0)
    )

    if arrival_date == departure_date and selected_date == arrival_date:
        return ("full", None) if cooling_ends_after_day else ("partial", cooling_end)

    if arrival_date <= selected_date < departure_date:
        return "full", None

    if selected_date == departure_date:
        return ("full", None) if cooling_ends_after_day else ("partial", cooling_end)

    return None, None


def room_sort_key(room):
    return (
        BUILDING_ORDER.get(room.prefix, 99),
        room.display_order,
        room.number,
    )


def charge_sheet_ordering(ordering):
    ordering_value = ordering or "-created_at"
    descending = ordering_value.startswith("-")
    ordering_field = ordering_value[1:] if descending else ordering_value
    ordering_map = {
        "serial_no": "id",
        "check_in": "booking__arrival_at",
        "check_out": "booking__departure_at",
        "booking_reference_id": "booking_id",
        "requestor_name": "requestor_name",
        "guest_name": "guest_name",
        "purpose_event": "purpose_event",
        "delta": "booking__room__number",
        "gamma": "booking__room__number",
        "beta": "booking__room__number",
        "room_charges_amount": "room_charges_amount",
        "attender_charges_amount": "attender_charges_amount",
        "payment_received_date": "payment_received_date",
        "budget_head_name": "budget_head_name",
        "created_at": "created_at",
    }
    if ordering_field == "total_charges":
        return "-total_charges_value" if descending else "total_charges_value"
    order_by = ordering_map.get(ordering_field, "created_at")
    return f"-{order_by}" if descending else order_by


def shared_booking_sheet_context(share):
    filters = share.filters or {}
    default_start, default_end = current_month_share_range()
    start_date = parse_share_date(filters.get("arrival_from")) or default_start
    end_date = parse_share_date(filters.get("departure_to")) or default_end
    dates = share_date_range(start_date, end_date)
    range_start_at, _ = local_date_bounds(dates[0])
    _, range_end_at = local_date_bounds(dates[-1])

    rooms = Room.objects.filter(is_active=True)
    bookings = (
        Booking.objects
        .select_related("room")
        .filter(arrival_at__lt=range_end_at, departure_at__gte=range_start_at)
        .order_by("arrival_at", "id")
    )

    prefix = filters.get("prefix")
    status = filters.get("status")
    if prefix:
        rooms = rooms.filter(prefix__iexact=prefix)
        bookings = bookings.filter(room__prefix__iexact=prefix)
    if status:
        bookings = bookings.filter(status__iexact=status)

    cells = {}
    visible_booking_ids = set()
    for booking in bookings:
        for selected_date in dates:
            availability_status, available_from = booking_availability_on_date(booking, selected_date)
            if not availability_status:
                continue
            key = (selected_date.isoformat(), booking.room_id)
            cells.setdefault(key, []).append({
                "text": booking_cell_text(booking),
                "status": booking.status,
                "status_label": booking.get_status_display(),
                "availability_status": availability_status,
                "available_from": (
                    timezone.localtime(available_from, INDIA_TZ).strftime("%d %b %Y, %I:%M %p")
                    if available_from else ""
                ),
            })
            visible_booking_ids.add(booking.id)

    room_rows = sorted(list(rooms), key=room_sort_key)
    table_rows = []
    for selected_date in dates:
        table_rows.append({
            "date": selected_date,
            "cells": [
                {"entries": cells.get((selected_date.isoformat(), room.id), [])}
                for room in room_rows
            ],
        })

    return {
        "share": share,
        "rooms": room_rows,
        "table_rows": table_rows,
        "visible_booking_count": len(visible_booking_ids),
        "start_date": start_date,
        "end_date": end_date,
        "filters": filters,
    }


def shared_charge_sheet_context(share):
    filters = share.filters or {}
    ensure_booking_charge_sheet_rows()
    queryset = BookingChargeSheet.objects.select_related("booking", "booking__room").all()

    prefix = filters.get("prefix")
    payment = filters.get("payment")
    checkout_from = parse_share_date(filters.get("checkout_from"))
    checkout_to = parse_share_date(filters.get("checkout_to"))
    search = (filters.get("search") or "").strip()

    if prefix:
        queryset = queryset.filter(booking__room__prefix__iexact=prefix)

    if payment == "received":
        queryset = queryset.filter(payment_received_date__isnull=False)
    elif payment == "pending":
        queryset = queryset.filter(payment_received_date__isnull=True)

    if checkout_from:
        start_at, _ = local_date_bounds(checkout_from)
        queryset = queryset.filter(booking__departure_at__gte=start_at)

    if checkout_to:
        _, end_at = local_date_bounds(checkout_to)
        queryset = queryset.filter(booking__departure_at__lt=end_at)

    if search:
        search_filter = (
            Q(requestor_name__icontains=search)
            | Q(guest_name__icontains=search)
            | Q(purpose_event__icontains=search)
            | Q(budget_head_name__icontains=search)
            | Q(booking__requestor_name__icontains=search)
            | Q(booking__visitor_name__icontains=search)
            | Q(booking__purpose_of_visit__icontains=search)
            | Q(booking__room__prefix__icontains=search)
            | Q(booking__room__number__icontains=search)
        )
        normalized_reference = search.lstrip("0")
        if normalized_reference.isdigit():
            search_filter |= Q(booking_id=int(normalized_reference))
        queryset = queryset.filter(search_filter)

    ordering = filters.get("ordering", "-created_at")
    if ordering.lstrip("-") == "total_charges":
        queryset = queryset.annotate(
            total_charges_value=ExpressionWrapper(
                F("room_charges_amount") + F("attender_charges_amount"),
                output_field=DecimalField(max_digits=10, decimal_places=2),
            )
        )
    queryset = queryset.order_by(charge_sheet_ordering(ordering), "id")

    return {
        "share": share,
        "rows": list(queryset),
        "filters": filters,
    }


class SharedBookingSheetView(TemplateView):
    template_name = "webapp/shared_bookings.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        share = get_object_or_404(
            active_share_queryset(),
            token=kwargs["token"],
            share_type=BookingShare.SHARE_TYPE_BOOKING_SHEET,
        )
        context.update(shared_booking_sheet_context(share))
        return context


class SharedChargeSheetView(TemplateView):
    template_name = "webapp/shared_charges.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        share = get_object_or_404(
            active_share_queryset(),
            token=kwargs["token"],
            share_type=BookingShare.SHARE_TYPE_CHARGE_SHEET,
        )
        context.update(shared_charge_sheet_context(share))
        return context
