from rest_framework import status
from rest_framework.response import Response


def success_body(message, data=None):
    return {
        "success": True,
        "message": message,
        "data": data,
    }


def error_body(message, errors=None):
    return {
        "success": False,
        "message": message,
        "errors": errors or {},
    }


def api_success(message, data=None, status_code=status.HTTP_200_OK):
    return Response(success_body(message, data), status=status_code)


def api_error(message, errors=None, status_code=status.HTTP_400_BAD_REQUEST):
    return Response(error_body(message, errors), status=status_code)


def serializer_error_response(
        serializer,
        message="Invalid request.",
        status_code=status.HTTP_400_BAD_REQUEST,
):
    return api_error(
        message,
        errors=serializer.errors,
        status_code=status_code,
    )
