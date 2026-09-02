from rest_framework.views import exception_handler


def api_exception_handler(exc, context):
    response = exception_handler(exc, context)
    if response is None:
        return None

    if isinstance(response.data, dict) and "code" in response.data:
        return response

    detail = response.data
    if isinstance(detail, dict) and set(detail) == {"detail"}:
        message = detail["detail"]
    else:
        message = "The request could not be processed."

    response.data = {
        "code": getattr(exc, "default_code", "request_error"),
        "detail": message,
        "errors": detail if detail != message else None,
    }
    return response
