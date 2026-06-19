import os
import logging
from datetime import datetime, timedelta
from django.core.exceptions import ImproperlyConfigured
from django.utils import timezone
from google.oauth2.service_account import Credentials
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

from bookings.models import Booking
from hostels.models import Room


SCOPES = ["https://www.googleapis.com/auth/spreadsheets"]
logger = logging.getLogger(__name__)

SHEET_NAME = "Visitor Room"
OCCUPANCY_SHEET_NAME = "Visitor Room"

ROOM_HEADER_ROW = 4
DATE_COLUMN = "A"
DATA_START_ROW = 5


def get_google_sheet_settings():
    service_account_file = os.getenv("GOOGLE_SERVICE_ACCOUNT_FILE")
    spreadsheet_id = os.getenv("GOOGLE_SHEET_ID")
    missing_settings = [
        name
        for name, value in [
            ("GOOGLE_SERVICE_ACCOUNT_FILE", service_account_file),
            ("GOOGLE_SHEET_ID", spreadsheet_id),
        ]
        if not value
    ]

    if missing_settings:
        raise ImproperlyConfigured(
            "Google Sheet sync requires environment variable(s): "
            + ", ".join(missing_settings)
        )

    return service_account_file, spreadsheet_id


def get_spreadsheet_id():
    _, spreadsheet_id = get_google_sheet_settings()
    return spreadsheet_id


def quote_sheet_name(name):
    return "'" + name.replace("'", "''") + "'"


def sheet_range(sheet_name, cell_range):
    return f"{quote_sheet_name(sheet_name)}!{cell_range}"


def get_sheet_service():
    service_account_file, _ = get_google_sheet_settings()
    creds = Credentials.from_service_account_file(
        service_account_file,
        scopes=SCOPES,
    )
    return build("sheets", "v4", credentials=creds)


def list_sheet_names():
    service = get_sheet_service()
    result = service.spreadsheets().get(spreadsheetId=get_spreadsheet_id()).execute()

    for sheet in result["sheets"]:
        logger.info("Google Sheet tab: %s", sheet["properties"]["title"])


def format_datetime(value):
    return timezone.localtime(value).strftime("%Y-%m-%d %H:%M:%S") if value else ""


def parse_datetime(value):
    if not value:
        return None

    value = str(value).strip()

    try:
        serial = float(value)
        base_date = datetime(1899, 12, 30)
        dt = base_date + timedelta(days=serial)
        return timezone.make_aware(dt)
    except ValueError:
        pass

    formats = [
        "%Y-%m-%d %H:%M:%S",
        "%d/%m/%Y %H:%M:%S",
        "%d-%m-%Y %H:%M:%S",
        "%d-%b-%Y",
        "%d-%B-%Y",
        "%d-%b-%y",
        "%d-%B-%y",
        "%Y-%m-%dT%H:%M:%S%z",
        "%Y-%m-%dT%H:%M:%S.%f%z",
    ]

    for fmt in formats:
        try:
            dt = datetime.strptime(value, fmt)
            if timezone.is_naive(dt):
                return timezone.make_aware(dt)
            return dt
        except ValueError:
            pass

    raise ValueError(f"Invalid datetime format: {value}")


def get_booking_instance(booking_or_id):
    if isinstance(booking_or_id, Booking):
        return booking_or_id

    return Booking.objects.select_related("room").get(pk=booking_or_id)


def write_sync_result(service, row_number, error_message="", status_message=""):
    service.spreadsheets().values().update(
        spreadsheetId=get_spreadsheet_id(),
        range=sheet_range(SHEET_NAME, f"V{row_number}:W{row_number}"),
        valueInputOption="USER_ENTERED",
        body={"values": [[error_message, status_message]]},
    ).execute()


def append_booking_to_sheet(booking):
    try:
        return sync_booking_calendar_cells(booking)

    except HttpError:
        logger.exception("Google Sheet API error while appending booking")
        return False

    except Exception:
        logger.exception("Google Sheet append failed")
        return False


def update_booking_in_sheet(booking):
    try:
        return sync_booking_calendar_cells(booking)

    except Exception:
        logger.exception("Google Sheet update failed")
        return False


def booking_to_row(booking):
    return [
        booking.id,
        str(booking.room),
        format_datetime(booking.arrival_at),
        format_datetime(booking.departure_at),
        booking.visitor_name,
        booking.visitor_designation,
        booking.visitor_organisation,
        booking.visitor_gender,
        booking.visitor_address,
        booking.visitor_mobile,
        booking.visitor_email,
        booking.purpose_of_visit,
        booking.budget_head_type,
        booking.budget_head_value,
        booking.budget_head_name,
        booking.budget_head_department_name,
        booking.budget_head_project_code,
        booking.requestor_name,
        booking.requestor_designation,
        booking.requestor_department,
        booking.requestor_mobile,
        booking.logistics_name,
        booking.logistics_designation,
        booking.logistics_mobile,
        booking.status,
        format_datetime(booking.created_at),
    ]


def get_room_from_name(room_name):
    room_name = str(room_name).strip()
    parts = room_name.split(maxsplit=1)

    if len(parts) != 2:
        raise ValueError(f"Invalid room format: {room_name}")

    prefix, number = parts[0], parts[1]
    return Room.objects.get(prefix=prefix, number=number)


def serializer_errors_to_text(errors):
    return "; ".join(
        f"{field}: {', '.join(map(str, messages))}"
        for field, messages in errors.items()
    )


def sync_sheet_to_database():
    raise NotImplementedError(
        "Sheet-to-database sync is disabled for the Visitor Room calendar layout."
    )


def normalize_room(value):
    value = str(value).lower()

    value = (
        value
        .replace("\n", "")
        .replace("-", "")
        .replace(" ", "")
        .replace("(", "")
        .replace(")", "")
    )

    value = (
        value
        .replace("chairmanflat", "")
        .replace("withoutattachedbath", "")
        .replace("bathroomnotattached", "")
        .replace("bathromnotattached", "")
    )

    return value.strip()


def column_number_to_letter(n):
    result = ""

    while n:
        n, remainder = divmod(n - 1, 26)
        result = chr(65 + remainder) + result

    return result


def detect_building_from_text(text):
    text = str(text).lower()

    if "delta" in text or "gaurlata" in text:
        return "Delta"

    if "gamma" in text or "mainpat" in text:
        return "Gamma"

    if "beta" in text or "palma" in text:
        return "Beta"

    return None


def debug_sheet_headers():
    service = get_sheet_service()

    result = service.spreadsheets().values().get(
        spreadsheetId=get_spreadsheet_id(),
        range=sheet_range(OCCUPANCY_SHEET_NAME, "A1:ZZ4"),
    ).execute()

    rows = result.get("values", [])

    logger.debug("Google Sheet header debug")

    for row_index, row in enumerate(rows, start=1):
        for col_index, value in enumerate(row, start=1):
            if value:
                logger.debug(
                    "row=%s column=%s value=%s",
                    row_index,
                    column_number_to_letter(col_index),
                    value,
                )


def build_room_column_map(service):
    header_result = service.spreadsheets().values().get(
        spreadsheetId=get_spreadsheet_id(),
        range=sheet_range(OCCUPANCY_SHEET_NAME, f"A1:ZZ{ROOM_HEADER_ROW}"),
    ).execute()

    header_rows = header_result.get("values", [])

    while len(header_rows) < ROOM_HEADER_ROW:
        header_rows.append([])

    max_cols = max(len(row) for row in header_rows)

    for row in header_rows:
        row += [""] * (max_cols - len(row))

    room_row = header_rows[ROOM_HEADER_ROW - 1]
    room_column_map = {}
    current_building = None

    for index in range(max_cols):
        column_text = " ".join(
            str(header_rows[row_index][index])
            for row_index in range(ROOM_HEADER_ROW)
            if header_rows[row_index][index]
        )

        detected_building = detect_building_from_text(column_text)

        if detected_building:
            current_building = detected_building

        room_header = room_row[index]

        if not room_header:
            continue

        if str(room_header).strip().lower() == "dates":
            continue

        if "chairman" in str(room_header).lower():
            current_building = "Delta"

        if not current_building:
            continue

        key = f"{current_building}:{normalize_room(room_header)}"
        room_column_map[key] = index + 1

    return room_column_map


def build_date_row_map(service):
    date_result = service.spreadsheets().values().get(
        spreadsheetId=get_spreadsheet_id(),
        range=sheet_range(OCCUPANCY_SHEET_NAME, f"{DATE_COLUMN}{DATA_START_ROW}:{DATE_COLUMN}"),
        valueRenderOption="FORMATTED_VALUE",
    ).execute()

    date_rows = date_result.get("values", [])
    date_row_map = {}

    for index, row in enumerate(date_rows, start=DATA_START_ROW):
        if not row:
            continue

        sheet_date = parse_datetime(row[0]).date()
        date_row_map[sheet_date] = index

    return date_row_map


def get_calendar_display_name(booking):
    name = str(booking.visitor_name or "").strip()
    organisation = str(booking.visitor_organisation or "").strip()

    if organisation:
        return f"{name} ({organisation})"

    return name


def append_name_to_existing_value(existing_value, display_name):
    display_name = str(display_name or "").strip()

    if not display_name:
        return existing_value

    if not existing_value:
        return display_name

    existing_names = [name.strip() for name in existing_value.split(",") if name.strip()]

    if display_name in existing_names:
        return existing_value

    return existing_value + ", " + display_name

def build_booking_cell_values(room_column_map, date_row_map):
    cell_bookings = {}

    bookings = (
        Booking.objects
        .filter(status=Booking.STATUS_ACTIVE)
        .select_related("room")
        .order_by("arrival_at", "id")
    )

    for booking in bookings:
        room_key = f"{booking.room.prefix}:{normalize_room(booking.room.number)}"

        if room_key not in room_column_map:
            logger.warning("Room not found in visitor calendar: %s", room_key)
            continue

        col_number = room_column_map[room_key]
        col_letter = column_number_to_letter(col_number)

        current_date = timezone.localtime(booking.arrival_at).date()
        end_date = timezone.localtime(booking.departure_at).date()

        while current_date <= end_date:
            if current_date in date_row_map:
                row_number = date_row_map[current_date]
                cell_range = sheet_range(
                    OCCUPANCY_SHEET_NAME,
                    f"{col_letter}{row_number}",
                )

                if cell_range not in cell_bookings:
                    cell_bookings[cell_range] = {}

                # Booking ID is the identity.
                # Same booking edit replaces this value.
                # Different booking appends separately.
                cell_bookings[cell_range][booking.id] = get_calendar_display_name(booking)

            current_date += timedelta(days=1)

    cell_values = {}

    for cell_range, booking_map in cell_bookings.items():
        names = [
            name
            for booking_id, name in sorted(booking_map.items())
            if name
        ]
        cell_values[cell_range] = ", ".join(names)

    return cell_values

CALENDAR_CLEAR_RANGE = "B5:ZZ400"


def clear_calendar_room_cells(service, room_column_map=None, date_row_map=None):
    service.spreadsheets().values().batchClear(
        spreadsheetId=get_spreadsheet_id(),
        body={
            "ranges": [
                sheet_range(OCCUPANCY_SHEET_NAME, CALENDAR_CLEAR_RANGE)
            ]
        },
    ).execute()


def fill_visitor_names_in_calendar():
    service = get_sheet_service()

    logger.info("Building Google Sheet room column map")
    room_column_map = build_room_column_map(service)
    logger.debug("Google Sheet room column map: %s", room_column_map)

    logger.info("Building Google Sheet date row map")
    date_row_map = build_date_row_map(service)
    logger.debug("Google Sheet date row map sample: %s", list(date_row_map.items())[:10])

    cell_values = build_booking_cell_values(room_column_map, date_row_map)
    logger.debug("Google Sheet cells to write: %s", cell_values)

    logger.info("Clearing Google Sheet calendar cells")
    clear_calendar_room_cells(service, room_column_map, date_row_map)

    updates = [
        {
            "range": cell_range,
            "values": [[value]],
        }
        for cell_range, value in cell_values.items()
    ]

    if updates:
        logger.info("Writing Google Sheet calendar cells: %s", len(updates))
        service.spreadsheets().values().batchUpdate(
            spreadsheetId=get_spreadsheet_id(),
            body={
                "valueInputOption": "USER_ENTERED",
                "data": updates,
            },
        ).execute()
    else:
        logger.info("No Google Sheet calendar cells to write")

    logger.info("Calendar visitor names updated: %s", len(updates))
    return {"updated_cells": len(updates)}


def sync_booking_calendar_cells(booking_or_id):
    request_calendar_sync()
    return True


def request_calendar_sync():
    try:
        from bookings.tasks import sync_google_sheet_calendar

        sync_google_sheet_calendar.delay()
        logger.info("Queued Google Sheet calendar sync task")
        return True

    except Exception:
        logger.exception("Failed to queue Google Sheet calendar sync task")
        return False
