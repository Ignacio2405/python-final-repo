"""Excepciones y respuestas de error centralizadas."""

import logging
from collections.abc import Mapping, Sequence
from typing import Any

from django.http import HttpRequest, JsonResponse
from rest_framework.exceptions import (
    MethodNotAllowed,
    NotFound,
    ParseError,
    UnsupportedMediaType,
    ValidationError,
)
from rest_framework.response import Response
from rest_framework.views import exception_handler

logger = logging.getLogger(__name__)


class DatosInsuficientesError(Exception):
    """No se pudo calcular ningún indicador con los datos recibidos."""


class NoAutorizadoError(Exception):
    """Falta una clave de API válida."""


def _respuesta_error(status_code: int, detail: str | dict[str, list[str]]) -> Response:
    return Response(
        {"ok": False, "error": True, "detail": detail},
        status=status_code,
    )


def _aplanar_errores(
    detalle: object,
    prefijo: str = "",
) -> dict[str, list[str]]:
    errores: dict[str, list[str]] = {}
    if isinstance(detalle, Mapping):
        for campo, valor in detalle.items():
            if campo == "detail" and not prefijo:
                return _aplanar_errores(valor)
            nombre = str(campo)
            ruta = f"{prefijo}.{nombre}" if prefijo else nombre
            if nombre == "non_field_errors":
                ruta = prefijo or "body"
            errores.update(_aplanar_errores(valor, ruta))
        return errores
    if isinstance(detalle, Sequence) and not isinstance(detalle, (str, bytes)):
        errores[prefijo or "body"] = [str(mensaje) for mensaje in detalle]
        return errores
    errores[prefijo or "body"] = [str(detalle)]
    return errores


def manejar_excepcion(exc: Exception, context: dict[str, Any]) -> Response:
    """Normalizá los errores de DRF sin exponer detalles internos."""
    if isinstance(exc, DatosInsuficientesError):
        return _respuesta_error(
            422,
            "No hay datos suficientes para calcular ningún indicador.",
        )
    if isinstance(exc, NoAutorizadoError):
        return _respuesta_error(401, "No autorizado.")

    respuesta = exception_handler(exc, context)
    if respuesta is None:
        logger.error(
            "Error interno al procesar una solicitud.",
            exc_info=(type(exc), exc, exc.__traceback__),
        )
        return _respuesta_error(500, "Error interno del servidor.")

    if isinstance(exc, (ValidationError, ParseError)):
        respuesta.status_code = 422
        detalle: object = (
            "El cuerpo debe ser un JSON válido."
            if isinstance(exc, ParseError)
            else respuesta.data
        )
    elif isinstance(exc, UnsupportedMediaType):
        detalle = "El tipo de contenido no está permitido."
    elif isinstance(exc, MethodNotAllowed):
        detalle = "Método no permitido."
    elif isinstance(exc, NotFound):
        detalle = "Ruta no encontrada."
    elif respuesta.status_code >= 500:
        logger.error(
            "Error interno al procesar una solicitud.",
            exc_info=(type(exc), exc, exc.__traceback__),
        )
        return _respuesta_error(500, "Error interno del servidor.")
    else:
        detalle = respuesta.data

    if isinstance(detalle, Mapping) and set(detalle) == {"detail"}:
        detalle = str(detalle["detail"])
    elif isinstance(detalle, Mapping):
        detalle = _aplanar_errores(detalle)
    return _respuesta_error(respuesta.status_code, detalle)


def manejar_404(
    _request: HttpRequest,
    _exception: Exception | None = None,
) -> JsonResponse:
    return JsonResponse(
        {"ok": False, "error": True, "detail": "Ruta no encontrada."},
        status=404,
    )


def manejar_500(_request: HttpRequest) -> JsonResponse:
    logger.error("Error interno al procesar una solicitud.")
    return JsonResponse(
        {
            "ok": False,
            "error": True,
            "detail": "Error interno del servidor.",
        },
        status=500,
    )
