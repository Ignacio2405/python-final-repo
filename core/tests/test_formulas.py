"""Pruebas unitarias de las fórmulas documentadas en SPEC §8."""

import pytest

from core.formulas.edad_corporal import calcular_edad_corporal
from core.formulas.grasa_visceral import calcular_grasa_visceral
from core.formulas.icc import calcular_icc
from core.formulas.imc import calcular_imc
from core.formulas.masa_grasa import calcular_porcentaje_mg
from core.formulas.masa_muscular import calcular_porcentaje_mm
from core.formulas.metabolismo_basal import calcular_metabolismo_basal


def test_calcular_imc_con_datos_manuales() -> None:
    # 1) 68.5 / (165 / 100)² = 25.1607 kg/m².
    assert calcular_imc(68.5, 165) == pytest.approx(25.1607, abs=0.0001)

    # 2) Si falta una medida, el resultado queda no disponible.
    assert calcular_imc(68.5, None) is None

    # 3) Una talla cero no debe generar una división inválida.
    assert calcular_imc(68.5, 0) is None


def test_calcular_icc_con_datos_manuales() -> None:
    # 1) 76 / 98 = 0.775510..., antes del redondeo del servicio.
    assert calcular_icc(76, 98) == pytest.approx(0.7755102, abs=0.0000001)

    # 2) Si falta la cadera, el resultado queda no disponible.
    assert calcular_icc(76, None) is None

    # 3) Una cadera cero no produce una excepción.
    assert calcular_icc(76, 0) is None


def test_calcular_metabolismo_basal_por_sexo_y_edad() -> None:
    # 1) F: 685 + 1031.25 - 160 - 161 = 1395.25 kcal/día.
    assert calcular_metabolismo_basal(68.5, 165, 32, "F") == pytest.approx(1395.25)

    # 2) M: 685 + 1031.25 - 160 + 5 = 1561.25 kcal/día.
    assert calcular_metabolismo_basal(68.5, 165, 32, "M") == pytest.approx(1561.25)

    # 3) Si falta un insumo obligatorio, no se estima el resultado.
    assert calcular_metabolismo_basal(68.5, 165, None, "F") is None

    # 4) La ecuación no se aplica a menores de 18 años.
    assert calcular_metabolismo_basal(68.5, 165, 17, "F") is None


def test_calcular_grasa_visceral_como_indice_de_conicidad() -> None:
    # 1) 0.76 / (0.109 * sqrt(68.5 / 1.65)) = 1.0821.
    assert calcular_grasa_visceral(76, 68.5, 165) == pytest.approx(1.0821, abs=0.0001)

    # 2) Si falta una medida, el resultado queda no disponible.
    assert calcular_grasa_visceral(76, None, 165) is None

    # 3) Una talla o un peso cero evita la raíz o división inválida.
    assert calcular_grasa_visceral(76, 68.5, 0) is None
    assert calcular_grasa_visceral(76, 0, 165) is None


def test_calcular_porcentaje_mg_con_tabla_por_sexo() -> None:
    # 1) F, 32 años: S=59; log10(S)=1.770852; D=1.030382; 495/D-450=30.404%.
    assert calcular_porcentaje_mg("F", 32, 10, 18, 16, 15) == pytest.approx(
        30.4043,
        abs=0.0001,
    )

    # 2) M, 32 años: S=59; D=1.045866; 495/D-450=23.292%.
    assert calcular_porcentaje_mg("M", 32, 10, 18, 16, 15) == pytest.approx(
        23.2921,
        abs=0.0001,
    )

    # 3) Si falta uno de los cuatro pliegues, no se calcula el porcentaje.
    assert calcular_porcentaje_mg("F", 32, 10, 18, 16, None) is None

    # 4) Una suma de pliegues cero no se pasa al logaritmo.
    assert calcular_porcentaje_mg("F", 32, 0, 0, 0, 0) is None

    # 5) Durnin-Womersley no aplica fuera de 17–72 años.
    assert calcular_porcentaje_mg("F", 16, 10, 18, 16, 15) is None
    assert calcular_porcentaje_mg("F", 73, 10, 18, 16, 15) is None


def test_calcular_porcentaje_mm_con_correccion_por_sexo() -> None:
    # 1) F: CAMA=36.86934 cm²; MME=21.99798 kg; 100*MME/68.5=32.11384%.
    assert calcular_porcentaje_mm(68.5, 165, 29, 18, "F", 32) == pytest.approx(
        32.1138,
        abs=0.0001,
    )

    # 2) M: CAMA=33.36934 cm²; MME=20.32323 kg; 100*MME/68.5=29.66895%.
    assert calcular_porcentaje_mm(68.5, 165, 29, 18, "M", 32) == pytest.approx(
        29.6690,
        abs=0.0001,
    )

    # 3) Si falta una medición obligatoria, no se calcula el porcentaje.
    assert calcular_porcentaje_mm(68.5, 165, 29, None, "F", 32) is None

    # 4) Un área corregida no positiva o una edad menor de 18 devuelve None.
    assert calcular_porcentaje_mm(68.5, 165, 5, 80, "F", 32) is None
    assert calcular_porcentaje_mm(68.5, 165, 29, 18, "F", 17) is None


def test_calcular_edad_corporal_heuristica_autorizada() -> None:
    # 1) F, 32 años: (30.4043 - 24) * 0.5 = 3.20215; ajuste = 3; edad = 35.
    assert calcular_edad_corporal(32, "F", 30.4043) == 35

    # 2) El redondeo de una mitad positiva y negativa sigue ROUND_HALF_UP.
    assert calcular_edad_corporal(32, "F", 25) == 33
    assert calcular_edad_corporal(32, "F", 23) == 31

    # 3) El ajuste queda limitado a -8 y +12 años.
    assert calcular_edad_corporal(32, "F", 0) == 24
    assert calcular_edad_corporal(32, "F", 100) == 44


def test_calcular_edad_corporal_restringir_poblacion_e_insumos() -> None:
    # 1) La heurística solo está autorizada para mujeres de 30–39 años.
    assert calcular_edad_corporal(29, "F", 30) is None
    assert calcular_edad_corporal(40, "F", 30) is None
    assert calcular_edad_corporal(32, "M", 30) is None

    # 2) Sin porcentaje de grasa válido, no se estima la edad corporal.
    assert calcular_edad_corporal(32, "F", None) is None
    assert calcular_edad_corporal(32, "F", float("nan")) is None
    assert calcular_edad_corporal(32, "F", float("inf")) is None
