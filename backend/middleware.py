import logging
import time
import uuid

from backend.request_context import reset_request_id, set_request_id


logger = logging.getLogger("backend.requests")


class RequestIdMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        request_id = normalize_request_id(request.headers.get("X-Request-ID"))
        token = set_request_id(request_id)
        request.request_id = request_id
        started_at = time.monotonic()

        try:
            response = self.get_response(request)
        except Exception:
            logger.exception(
                "request_failed",
                extra=request_log_extra(request, status_code=500, started_at=started_at),
            )
            reset_request_id(token)
            raise

        response["X-Request-ID"] = request_id
        logger.info(
            "request_finished",
            extra=request_log_extra(request, status_code=response.status_code, started_at=started_at),
        )
        reset_request_id(token)
        return response


def normalize_request_id(value):
    if not value:
        return uuid.uuid4().hex

    value = value.strip()
    if len(value) > 128:
        return uuid.uuid4().hex

    return value or uuid.uuid4().hex


def request_log_extra(request, status_code, started_at):
    return {
        "method": request.method,
        "path": request.path,
        "status_code": status_code,
        "duration_ms": round((time.monotonic() - started_at) * 1000, 2),
        "remote_addr": request.META.get("REMOTE_ADDR", ""),
    }
