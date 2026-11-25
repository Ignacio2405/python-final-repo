"""Autenticación del servicio compartida con Node.js."""

import hmac

from django.conf import settings
from rest_framework.permissions import BasePermission
from rest_framework.request import Request
from rest_framework.views import APIView

from core.exceptions import NoAutorizadoError


class RequiereApiKey(BasePermission):
    """Exigí X-API-Key salvo en desarrollo con token vacío."""

    def has_permission(self, request: Request, _view: APIView) -> bool:
        if settings.DEBUG and not settings.API_TOKEN:
            return True

        token = request.headers.get("X-API-Key")
        if token is None or not hmac.compare_digest(
            token.encode("utf-8"),
            settings.API_TOKEN.encode("utf-8"),
        ):
            raise NoAutorizadoError()
        return True
