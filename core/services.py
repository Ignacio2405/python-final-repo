"""Orquestación del cálculo de indicadores antropométricos."""

import logging
from collections.abc import Callable

from core.exceptions import DatosInsuficientesError
from core.formulas.edad_corporal import calcular_edad_corporal
from core.formulas.grasa_visceral import calcular_grasa_visceral
from core.formulas.icc import calcular_icc
from core.formulas.imc import calcular_imc
from core.formulas.masa_grasa import calcular_porcentaje_mg
from core.formulas.masa_muscular import calcular_porcentaje_mm
from core.formulas.metabolismo_basal import calcular_metabolismo_basal
from core.math_utils import redondear
from core.serializers import CalculoAntropometriaRequest

logger = logging.getLogger(__name__)

_DECIMALES = {
    "imc": 2,
    "porcentajeMG": 1,
    "porcentajeMM": 1,
    "mBasal": 1,
    "grVisceral": 2,
    "icc": 2,
}


class AntropometriaService:
    """Calculá indicadores de forma independiente y armá el resultado."""

    @staticmethod
    def calcular(
        request: CalculoAntropometriaRequest,
    ) -> dict[str, float | int | None]:
        datos = request.validated_data
        mediciones = datos["mediciones"]
        paciente = datos.get("paciente") or {}
        sexo = paciente.get("sexo")
        edad = paciente.get("edad")

        calculos: tuple[tuple[str, Callable[[], float | int | None]], ...] = (
            ("imc", lambda: calcular_imc(mediciones["peso"], mediciones["talla"])),
            ("porcentajeMG", lambda: calcular_porcentaje_mg(
                sexo,
                edad,
                mediciones["pBicipital"],
                mediciones["pTricipital"],
                mediciones["pSubescapular"],
                mediciones["pSuprailiaco"],
            )),
            ("porcentajeMM", lambda: calcular_porcentaje_mm(
                mediciones["peso"],
                mediciones["talla"],
                mediciones["brazo"],
                mediciones["pTricipital"],
                sexo,
                edad,
            )),
            ("mBasal", lambda: calcular_metabolismo_basal(
                mediciones["peso"],
                mediciones["talla"],
                edad,
                sexo,
            )),
            ("bodyAge", calcular_edad_corporal),
            ("grVisceral", lambda: calcular_grasa_visceral(
                mediciones["cintura"],
                mediciones["peso"],
                mediciones["talla"],
            )),
            (
                "icc",
                lambda: calcular_icc(mediciones["cintura"], mediciones["cadera"]),
            ),
        )

        valores: dict[str, float | int | None] = {}
        for indicador, calculo in calculos:
            try:
                valores[indicador] = calculo()
            except Exception:
                logger.exception("No se pudo calcular el indicador %s.", indicador)
                valores[indicador] = None

        if all(valor is None for valor in valores.values()):
            raise DatosInsuficientesError

        redondeados = {
            indicador: redondear(valor, _DECIMALES[indicador])
            if indicador in _DECIMALES
            else valor
            for indicador, valor in valores.items()
        }
        return redondeados
