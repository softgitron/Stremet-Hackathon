from typing import Any

from django.core.exceptions import PermissionDenied
from django.http import Http404
from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import exception_handler as drf_exception_handler


def stremet_exception_handler(exc: Exception, context: dict[str, Any]) -> Response | None:
    """
    Consistent JSON error body for API clients:

        {
          "success": false,
          "error": {
            "code": "<string>",
            "message": "<human-readable>",
            "http_status": <int>,
            "fields": { "<field>": ["..."] } | null
          }
        }
    """
    response = drf_exception_handler(exc, context)

    if response is not None:
        payload = _normalize_error_payload(response.status_code, response.data)
        response.data = {"success": False, "error": payload}
        return response

    if isinstance(exc, Http404):
        return Response(
            {
                "success": False,
                "error": {
                    "code": "not_found",
                    "message": str(exc) or "Not found.",
                    "http_status": status.HTTP_404_NOT_FOUND,
                    "fields": None,
                },
            },
            status=status.HTTP_404_NOT_FOUND,
        )

    if isinstance(exc, PermissionDenied):
        return Response(
            {
                "success": False,
                "error": {
                    "code": "permission_denied",
                    "message": str(exc) or "Permission denied.",
                    "http_status": status.HTTP_403_FORBIDDEN,
                    "fields": None,
                },
            },
            status=status.HTTP_403_FORBIDDEN,
        )

    return None


def _normalize_error_payload(http_status: int, data: Any) -> dict[str, Any]:
    fields: dict[str, list[str]] | None = None
    message = "Request failed."

    if isinstance(data, dict):
        detail = data.get("detail")
        if detail is not None:
            if isinstance(detail, list):
                message = "; ".join(str(x) for x in detail)
            else:
                message = str(detail)
        else:
            fields = {}
            for key, val in data.items():
                if key == "non_field_errors":
                    if isinstance(val, list):
                        message = "; ".join(str(x) for x in val)
                    continue
                if isinstance(val, list):
                    fields[key] = [str(x) for x in val]
                elif isinstance(val, dict):
                    for nk, nv in val.items():
                        composite = f"{key}.{nk}"
                        fields[composite] = [str(x) for x in nv] if isinstance(nv, list) else [str(nv)]
                else:
                    fields[key] = [str(val)]
            if fields == {}:
                fields = None
            if fields and (not message or message == "Request failed."):
                message = "Validation error."
            if detail is None and fields is None and data:
                message = str(data)
    elif isinstance(data, list):
        message = "; ".join(str(x) for x in data)
    else:
        message = str(data)

    code = "error"
    if http_status == 400:
        code = "validation_error" if fields else "bad_request"
    elif http_status == 401:
        code = "not_authenticated"
    elif http_status == 403:
        code = "permission_denied"
    elif http_status == 404:
        code = "not_found"
    elif http_status == 405:
        code = "method_not_allowed"
    elif http_status >= 500:
        code = "server_error"

    return {
        "code": code,
        "message": message,
        "http_status": http_status,
        "fields": fields,
    }
