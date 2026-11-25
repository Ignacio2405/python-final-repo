"""Endpoints HTTP del módulo, sin lógica matemática."""

from rest_framework.permissions import AllowAny
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from core.serializers import (
    CalculoAntropometriaRequest,
    CalculoAntropometriaResponse,
)
from core.security import RequiereApiKey
from core.services import AntropometriaService


class HealthView(APIView):
    """Comprobá que el servicio esté disponible sin requerir autenticación."""

    authentication_classes = []
    permission_classes = [AllowAny]

    def get(self, _request: Request) -> Response:
        return Response({"status": "ok", "service": "Calculos Nutricionales"})


class CalcularAntropometriaView(APIView):
    """Validá el pedido y delegá el cálculo al servicio de dominio."""

    authentication_classes = []
    permission_classes = [RequiereApiKey]

    def post(self, request: Request) -> Response:
        entrada = CalculoAntropometriaRequest(data=request.data)
        entrada.is_valid(raise_exception=True)
        resultados = AntropometriaService.calcular(entrada)
        salida = CalculoAntropometriaResponse(
            {"ok": True, "resultados": resultados}
        )
        return Response(salida.data)
