from django.contrib import admin
from django.urls import path, include
from rest_framework import status
from rest_framework.response import Response
from http import HTTPStatus
from typing import Any
from rest_framework.views import exception_handler
from drf_yasg import openapi
from drf_yasg.views import get_schema_view
from rest_framework_swagger.views import get_swagger_view
from rest_framework import permissions


def my_exception_handler(exc: Exception, context: dict[str, Any]) -> Response:

    response = exception_handler(exc, context)

    if response is not None:
        http_code_to_massage = {v.value: v.description for v in HTTPStatus}
        error_payload = {
            "error": {
                "message": "",
                "details": [],
            }
        }

        error = error_payload["error"]
        error["message"] = http_code_to_massage[response.status_code]
        error["details"] = response.data
        response.data = error_payload
    else:
        response = Response(
            {
                "error": {
                    "message": str(exc),
                    "details": {
                        "detail": "An unexpected error occurred."
                    }
                }
            },
            status=HTTPStatus.INTERNAL_SERVER_ERROR)

    return response


schema_view = get_schema_view(
    openapi.Info(
        title="Found Tracker - Sweeger",
        default_version='v1',),
    public=True,
    permission_classes=(permissions.AllowAny,),

)

urlpatterns = [
    path('admin/', admin.site.urls),
    path('authentication/', include('authentication.urls')),
    path('api/', include('api.urls')),

    path('docs/', schema_view.with_ui('swagger',
         cache_timeout=0), name='schema-swagger-ui')
]
