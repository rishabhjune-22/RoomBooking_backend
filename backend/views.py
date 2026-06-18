from django.db import connection
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes, throttle_classes
from rest_framework.permissions import AllowAny

from backend.responses import api_error, api_success


@api_view(["GET"])
@permission_classes([AllowAny])
@throttle_classes([])
def health_check(request):
    try:
        connection.ensure_connection()
    except Exception:
        return api_error(
            "Service unavailable.",
            errors={"database": ["unavailable"]},
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
        )

    return api_success("OK", {"database": "ok"})
