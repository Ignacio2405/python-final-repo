"""Heurística de edad corporal autorizada para un segmento acotado."""

import math

from core.math_utils import redondear

EDAD_MINIMA_APLICABLE = 30
EDAD_MAXIMA_APLICABLE = 39
PORCENTAJE_GRASA_REFERENCIA = 24.0
FACTOR_AJUSTE_EDAD = 0.5
AJUSTE_EDAD_MINIMO = -8
AJUSTE_EDAD_MAXIMO = 12
EDAD_CORPORAL_MINIMA = 18


def calcular_edad_corporal(
    edad: int | None,
    sexo: str | None,
    porcentaje_mg: float | None,
) -> int | None:
    """Calculá una estimación heurística, no clínica, de edad corporal.

    Ecuación: ajuste = limitar(ROUND_HALF_UP((%MG - 24) * 0.5), -8, 12);
    edad corporal = max(18, edad + ajuste). La edad entra en años y el
    porcentaje de masa grasa en puntos porcentuales; la salida son años enteros.
    Solo aplica a mujeres de 30–39 años con un porcentaje de masa grasa finito.
    Es una heurística autorizada por el responsable del proyecto
    el 25/11/2026, sin fuente bibliográfica ni validación clínica.
    """
    if (
        edad is None
        or sexo != "F"
        or not EDAD_MINIMA_APLICABLE <= edad <= EDAD_MAXIMA_APLICABLE
        or porcentaje_mg is None
        or not math.isfinite(porcentaje_mg)
    ):
        return None

    ajuste_redondeado = redondear(
        (porcentaje_mg - PORCENTAJE_GRASA_REFERENCIA) * FACTOR_AJUSTE_EDAD,
        0,
    )
    if ajuste_redondeado is None:
        return None

    ajuste_limitado = max(
        AJUSTE_EDAD_MINIMO,
        min(AJUSTE_EDAD_MAXIMO, int(ajuste_redondeado)),
    )
    return max(EDAD_CORPORAL_MINIMA, edad + ajuste_limitado)
