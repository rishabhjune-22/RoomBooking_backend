from rest_framework.views import exception_handler

from backend.responses import error_body


def custom_exception_handler(exc, context):
    response = exception_handler(exc, context)

    if response is None:
        return response

    normalized_errors = normalize_errors(response.data)

    response.data = error_body(
        get_first_error_message(normalized_errors),
        errors=normalized_errors,
    )
    return response


def normalize_errors(errors):
    if not isinstance(errors, dict):
        return {"detail": [stringify_error(errors)]}

    normalized = {}

    for key, value in errors.items():
        if isinstance(value, list):
            normalized[key] = [stringify_error(item) for item in value]
        else:
            normalized[key] = [stringify_error(value)]

    return normalized


def get_first_error_message(errors):
    if not isinstance(errors, dict):
        return "Request failed"

    for key, value in errors.items():
        if isinstance(value, list) and value:
            first_message = value[0]

            if first_message:
                return str(first_message)

        if isinstance(value, str) and value:
            return value

    return "Request failed"


def stringify_error(value):
    if isinstance(value, dict):
        if "message" in value and value["message"]:
            return str(value["message"])

        parts = []

        for key, item in value.items():
            if isinstance(item, list):
                joined = ", ".join(str(error) for error in item)
                parts.append(f"{key}: {joined}")
            else:
                parts.append(f"{key}: {item}")

        return " | ".join(parts)

    return str(value)
