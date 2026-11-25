"""Validación y serialización del contrato HTTP."""

import math
from collections.abc import Mapping
from datetime import date
from typing import Any

from rest_framework import serializers

PESO_MIN = 2.0
PESO_MAX = 500.0
TALLA_MIN = 30.0
TALLA_MAX = 272.0
CUELLO_MIN = 10.0
CUELLO_MAX = 80.0
BRAZO_MIN = 5.0
BRAZO_MAX = 80.0
CINTURA_MIN = 20.0
CINTURA_MAX = 250.0
CADERA_MIN = 30.0
CADERA_MAX = 250.0
PLIEGUE_MIN = 0.0
PLIEGUE_MAX = 80.0


def _edad_en_fecha(fecha_nacimiento: date, fecha_referencia: date) -> int:
    """Calculá los años cumplidos a la fecha de referencia."""
    return fecha_referencia.year - fecha_nacimiento.year - (
        (fecha_referencia.month, fecha_referencia.day)
        < (fecha_nacimiento.month, fecha_nacimiento.day)
    )


class SerializerEstricta(serializers.Serializer):
    """Rechazá claves que no formen parte del contrato."""

    def to_internal_value(self, data: object) -> dict[str, Any]:
        if not isinstance(data, Mapping):
            raise serializers.ValidationError("Ingresá un objeto JSON válido.")
        desconocidas = set(data).difference(self.fields)
        if desconocidas:
            raise serializers.ValidationError(
                {
                    str(campo): "Esta clave no está permitida."
                    for campo in sorted(desconocidas, key=str)
                }
            )
        return super().to_internal_value(data)


class NumeroEstrictField(serializers.FloatField):
    """Aceptá únicamente números JSON finitos, nunca cadenas o booleanos."""

    def __init__(
        self,
        *args: object,
        debe_ser_positivo: bool = False,
        **kwargs: object,
    ) -> None:
        self.debe_ser_positivo = debe_ser_positivo
        super().__init__(*args, **kwargs)

    def to_internal_value(self, data: object) -> float:
        if isinstance(data, bool) or not isinstance(data, (int, float)):
            raise serializers.ValidationError("Ingresá un valor numérico.")
        if not math.isfinite(float(data)):
            raise serializers.ValidationError("Ingresá un número finito.")
        if self.debe_ser_positivo and data <= 0:
            raise serializers.ValidationError("Debe ser mayor que 0.")
        return super().to_internal_value(data)


class EnteroEstrictField(serializers.IntegerField):
    """Aceptá enteros JSON, sin convertir cadenas ni truncar decimales."""

    def to_internal_value(self, data: object) -> int:
        if isinstance(data, bool) or not isinstance(data, int):
            raise serializers.ValidationError("Ingresá un número entero.")
        return super().to_internal_value(data)


class DatosPacienteInput(SerializerEstricta):
    """Datos demográficos opcionales usados por algunas fórmulas."""

    sexo = serializers.ChoiceField(
        choices=("M", "F"),
        required=False,
        default=None,
        allow_null=True,
        error_messages={"invalid_choice": "Debe ser 'M' o 'F'."},
    )
    edad = EnteroEstrictField(
        required=False,
        default=None,
        allow_null=True,
        min_value=0,
        max_value=120,
        error_messages={
            "min_value": "La edad debe estar entre 0 y 120 años.",
            "max_value": "La edad debe estar entre 0 y 120 años.",
            "null": "La edad no puede ser nula.",
        },
    )
    fechaNacimiento = serializers.DateField(
        required=False,
        default=None,
        allow_null=True,
        input_formats=["%Y-%m-%d"],
        error_messages={
            "invalid": "Ingresá una fecha válida en formato YYYY-MM-DD.",
            "null": "La fecha de nacimiento no puede ser nula.",
        },
    )

    def validate_fechaNacimiento(self, valor: date | None) -> date | None:
        if valor is not None and valor > date.today():
            raise serializers.ValidationError(
                "La fecha de nacimiento no puede ser futura."
            )
        return valor

    def validate(self, attrs: dict[str, Any]) -> dict[str, Any]:
        fecha_nacimiento = attrs.get("fechaNacimiento")
        if fecha_nacimiento is None:
            return attrs

        edad_derivada = _edad_en_fecha(fecha_nacimiento, date.today())
        edad = attrs.get("edad")
        if edad is not None:
            if abs(edad_derivada - edad) > 1:
                raise serializers.ValidationError(
                    {"edad": "La edad no coincide con la fecha de nacimiento."}
                )
        elif not 0 <= edad_derivada <= 120:
            raise serializers.ValidationError(
                {"edad": "La edad derivada debe estar entre 0 y 120 años."}
            )
        else:
            attrs["edad"] = edad_derivada
        return attrs


def _campo_medicion(
    minimo: float,
    maximo: float,
    unidad: str,
    *,
    positivo: bool = False,
) -> NumeroEstrictField:
    mensaje = f"Debe estar entre {minimo:g} y {maximo:g} {unidad}."
    return NumeroEstrictField(
        required=False,
        default=None,
        allow_null=True,
        min_value=minimo,
        max_value=maximo,
        debe_ser_positivo=positivo,
        error_messages={"min_value": mensaje, "max_value": mensaje},
    )


class MedicionesInput(SerializerEstricta):
    """Mediciones opcionales, expresadas en las unidades del contrato."""

    peso = _campo_medicion(PESO_MIN, PESO_MAX, "kg", positivo=True)
    talla = _campo_medicion(TALLA_MIN, TALLA_MAX, "cm", positivo=True)
    cuello = _campo_medicion(CUELLO_MIN, CUELLO_MAX, "cm", positivo=True)
    brazo = _campo_medicion(BRAZO_MIN, BRAZO_MAX, "cm", positivo=True)
    cintura = _campo_medicion(CINTURA_MIN, CINTURA_MAX, "cm", positivo=True)
    cadera = _campo_medicion(CADERA_MIN, CADERA_MAX, "cm", positivo=True)
    pTricipital = _campo_medicion(PLIEGUE_MIN, PLIEGUE_MAX, "mm")
    pBicipital = _campo_medicion(PLIEGUE_MIN, PLIEGUE_MAX, "mm")
    pSubescapular = _campo_medicion(PLIEGUE_MIN, PLIEGUE_MAX, "mm")
    pSuprailiaco = _campo_medicion(PLIEGUE_MIN, PLIEGUE_MAX, "mm")

    def validate(self, attrs: dict[str, Any]) -> dict[str, Any]:
        if not any(valor is not None for valor in attrs.values()):
            raise serializers.ValidationError(
                {"non_field_errors": "Informá al menos una medición."}
            )
        return attrs


class CalculoAntropometriaRequest(SerializerEstricta):
    """Payload aceptado por POST /calcular-antropometria."""

    paciente = DatosPacienteInput(required=False, allow_null=True)
    mediciones = MedicionesInput(
        required=True,
        error_messages={"required": "Este campo es obligatorio."},
    )


class ResultadosAntropometria(serializers.Serializer):
    """Los siete indicadores; los no calculables se informan como null."""

    imc = serializers.FloatField(allow_null=True)
    porcentajeMG = serializers.FloatField(allow_null=True)
    porcentajeMM = serializers.FloatField(allow_null=True)
    mBasal = serializers.FloatField(allow_null=True)
    bodyAge = serializers.IntegerField(allow_null=True)
    grVisceral = serializers.FloatField(allow_null=True)
    icc = serializers.FloatField(allow_null=True)


class CalculoAntropometriaResponse(serializers.Serializer):
    """Respuesta exitosa con el conjunto fijo de resultados."""

    ok = serializers.BooleanField()
    resultados = ResultadosAntropometria()
