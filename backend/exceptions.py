from rest_framework.views import exception_handler


def custom_exception_handler(exc, context):
    response = exception_handler(exc, context)

    if response is None:
        return response

    response.data = {
        "success": False,
        "message": "Request failed",
        "errors": normalize_errors(response.data),
    }

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


def stringify_error(value):
    if isinstance(value, dict):
        if "message" in value and value["message"]:
            return str(value["message"])

        parts = []
        for k, v in value.items():
            if isinstance(v, list):
                joined = ", ".join(str(item) for item in v)
                parts.append(f"{k}: {joined}")
            else:
                parts.append(f"{k}: {v}")
        return " | ".join(parts)

    return str(value)