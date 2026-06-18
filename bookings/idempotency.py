import hashlib
import json

from django.db import IntegrityError
from rest_framework import status
from rest_framework.response import Response

from backend.responses import api_error

from .models import BookingIdempotencyRecord


MAX_IDEMPOTENCY_KEY_LENGTH = 128


class IdempotencyResult:
    def __init__(self, record=None, response=None):
        self.record = record
        self.response = response


def begin_idempotent_request(request, action, extra=None):
    key = get_idempotency_key(request)
    if not key:
        return IdempotencyResult()

    if len(key) > MAX_IDEMPOTENCY_KEY_LENGTH:
        return IdempotencyResult(
            response=api_error(
                "Idempotency-Key is too long.",
                errors={"idempotency_key": ["Maximum length is 128 characters."]},
                status_code=status.HTTP_400_BAD_REQUEST,
            )
        )

    request_hash = build_request_hash(request, extra=extra)

    try:
        record, created = (
            BookingIdempotencyRecord.objects
            .select_for_update()
            .get_or_create(
                action=action,
                key=key,
                defaults={"request_hash": request_hash},
            )
        )
    except IntegrityError:
        record = (
            BookingIdempotencyRecord.objects
            .select_for_update()
            .get(action=action, key=key)
        )
        created = False

    if not created and record.request_hash != request_hash:
        return IdempotencyResult(
            response=api_error(
                "Idempotency-Key was already used with different request data.",
                errors={"idempotency_key": ["Reuse the key only for an identical request."]},
                status_code=status.HTTP_409_CONFLICT,
            )
        )

    if record.response_body is not None:
        return IdempotencyResult(
            response=Response(record.response_body, status=record.response_status)
        )

    if not created:
        return IdempotencyResult(
            response=api_error(
                "Idempotent request is already being processed.",
                errors={"idempotency_key": ["Please retry shortly."]},
                status_code=status.HTTP_409_CONFLICT,
            )
        )

    return IdempotencyResult(record=record)


def complete_idempotent_request(record, response_body, response_status, booking_id=None):
    if record is None:
        return

    record.response_body = response_body
    record.response_status = response_status
    record.booking_id = booking_id
    record.save(update_fields=[
        "response_body",
        "response_status",
        "booking_id",
        "updated_at",
    ])


def get_idempotency_key(request):
    value = request.headers.get("Idempotency-Key", "")
    return value.strip()


def build_request_hash(request, extra=None):
    payload = {
        "method": request.method,
        "path": request.path,
        "data": request.data,
        "extra": extra,
    }
    serialized = json.dumps(payload, sort_keys=True, default=str, separators=(",", ":"))
    return hashlib.sha256(serialized.encode("utf-8")).hexdigest()
