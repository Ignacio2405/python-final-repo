"""Pruebas del contrato HTTP y sus envelopes de error."""

import os
import subprocess
import sys
from copy import deepcopy
from datetime import date
from pathlib import Path

import pytest
from rest_framework.test import APIClient

from core.serializers import DatosPacienteInput
from core.services import AntropometriaService


def test_endpoint_calcular_responder_con_siete_claves(
    cliente: APIClient,
    solicitud_completa: dict[str, object],
) -> None:
    # 1) El payload de SPEC §6.2 da los resultados calculados a mano en §8.
    respuesta = cliente.post(
        "/calcular-antropometria",
        data=solicitud_completa,
        format="json",
        headers={"X-API-Key": "test-token"},
    )

    assert respuesta.status_code == 200
    assert respuesta.json() == {
        "ok": True,
        "resultados": {
            "imc": 25.16,
            "porcentajeMG": 30.4,
            "porcentajeMM": 32.1,
            "mBasal": 1395.3,
            "bodyAge": 35,
            "grVisceral": 1.08,
            "icc": 0.78,
        },
    }


def test_endpoint_health_no_requerir_token(cliente: APIClient) -> None:
    # 1) Health responde sin autenticación.
    respuesta = cliente.get("/health")

    assert respuesta.status_code == 200
    assert respuesta.json() == {
        "status": "ok",
        "service": "Calculos Nutricionales",
    }


def test_endpoint_envolver_ruta_inexistente_y_tipo_de_contenido(cliente: APIClient) -> None:
    # 1) Las rutas desconocidas conservan el envelope incluso con DEBUG activo.
    no_encontrada = cliente.get("/ruta-inexistente")
    assert no_encontrada.status_code == 404
    assert no_encontrada.json() == {
        "ok": False,
        "error": True,
        "detail": "Ruta no encontrada.",
    }

    # 2) Un Content-Type no admitido devuelve 415 con un mensaje localizado.
    tipo_no_admitido = cliente.post(
        "/calcular-antropometria",
        data="{}",
        content_type="text/plain",
        headers={"X-API-Key": "test-token"},
    )
    assert tipo_no_admitido.status_code == 415
    assert tipo_no_admitido.json() == {
        "ok": False,
        "error": True,
        "detail": "El tipo de contenido no está permitido.",
    }


def test_endpoint_calcular_devolver_nulos_si_faltan_datos(
    cliente: APIClient,
) -> None:
    # 1) Peso y talla permiten IMC; los indicadores con otros insumos quedan en null.
    respuesta = cliente.post(
        "/calcular-antropometria",
        data={"mediciones": {"peso": 68.5, "talla": 165}},
        format="json",
        headers={"X-API-Key": "test-token"},
    )

    assert respuesta.status_code == 200
    resultados = respuesta.json()["resultados"]
    assert resultados["imc"] == 25.16
    assert resultados["icc"] is None
    assert resultados["bodyAge"] is None
    assert len(resultados) == 7


def test_endpoint_rechazar_falta_o_error_de_token(
    cliente: APIClient,
    solicitud_completa: dict[str, object],
) -> None:
    # 1) La falta del header y un valor incorrecto responden igual.
    sin_token = cliente.post(
        "/calcular-antropometria",
        data=solicitud_completa,
        format="json",
    )
    token_incorrecto = cliente.post(
        "/calcular-antropometria",
        data=solicitud_completa,
        format="json",
        headers={"X-API-Key": "incorrecto"},
    )

    for respuesta in (sin_token, token_incorrecto):
        assert respuesta.status_code == 401
        assert respuesta.json() == {
            "ok": False,
            "error": True,
            "detail": "No autorizado.",
        }


def test_endpoint_validar_rangos_y_mediciones_vacias(cliente: APIClient) -> None:
    # 1) La plausibilidad de talla limita el dato a 272 cm.
    rango = cliente.post(
        "/calcular-antropometria",
        data={"mediciones": {"talla": 5000}},
        format="json",
        headers={"X-API-Key": "test-token"},
    )
    assert rango.status_code == 422
    assert rango.json()["detail"]["mediciones.talla"] == [
        "Debe estar entre 30 y 272 cm."
    ]

    # 2) Un objeto mediciones vacío es inválido.
    vacia = cliente.post(
        "/calcular-antropometria",
        data={"mediciones": {}},
        format="json",
        headers={"X-API-Key": "test-token"},
    )
    assert vacia.status_code == 422
    assert vacia.json()["detail"]["mediciones"] == ["Informá al menos una medición."]

    # 3) Una medición válida sin cobertura para ningún indicador también es 422.
    insuficiente = cliente.post(
        "/calcular-antropometria",
        data={"mediciones": {"cuello": 33}},
        format="json",
        headers={"X-API-Key": "test-token"},
    )
    assert insuficiente.status_code == 422
    assert insuficiente.json()["detail"] == (
        "No hay datos suficientes para calcular ningún indicador."
    )


def test_endpoint_rechazar_claves_desconocidas_en_todos_los_niveles(
    cliente: APIClient,
    solicitud_completa: dict[str, object],
) -> None:
    # 1) Una clave desconocida en la raíz se rechaza.
    raiz = deepcopy(solicitud_completa)
    raiz["resultados"] = {}
    # 2) Una clave desconocida del paciente se rechaza.
    paciente = deepcopy(solicitud_completa)
    paciente["paciente"]["sexo_extra"] = "F"
    # 3) Una clave desconocida de mediciones se rechaza.
    mediciones = deepcopy(solicitud_completa)
    mediciones["mediciones"]["pTriciptal"] = 18

    for payload in (raiz, paciente, mediciones):
        respuesta = cliente.post(
            "/calcular-antropometria",
            data=payload,
            format="json",
            headers={"X-API-Key": "test-token"},
        )
        assert respuesta.status_code == 422
        assert respuesta.json()["ok"] is False


def test_endpoint_validar_fecha_y_consistencia_de_edad(cliente: APIClient) -> None:
    # 1) Una fecha futura no puede usarse como fecha de nacimiento.
    fecha_futura = cliente.post(
        "/calcular-antropometria",
        data={
            "paciente": {"fechaNacimiento": "2999-01-01"},
            "mediciones": {"cuello": 33},
        },
        format="json",
        headers={"X-API-Key": "test-token"},
    )
    assert fecha_futura.status_code == 422

    # 2) Una edad que difiere en más de un año se informa bajo paciente.edad.
    edad_inconsistente = cliente.post(
        "/calcular-antropometria",
        data={
            "paciente": {"edad": 32, "fechaNacimiento": "1980-01-01"},
            "mediciones": {"peso": 68.5, "talla": 165},
        },
        format="json",
        headers={"X-API-Key": "test-token"},
    )
    assert edad_inconsistente.status_code == 422
    assert "paciente.edad" in edad_inconsistente.json()["detail"]

    # 3) Una fecha válida no alcanza para derivar una edad mayor de 120 años.
    edad_fuera_rango = cliente.post(
        "/calcular-antropometria",
        data={
            "paciente": {"fechaNacimiento": "1890-01-01"},
            "mediciones": {"peso": 68.5, "talla": 165},
        },
        format="json",
        headers={"X-API-Key": "test-token"},
    )
    assert edad_fuera_rango.status_code == 422
    assert "paciente.edad" in edad_fuera_rango.json()["detail"]


def test_serializer_derivar_edad_si_solo_llega_fecha_de_nacimiento() -> None:
    # 1) La edad se deriva en años cumplidos según la fecha actual del servidor.
    hoy = date.today()
    try:
        nacimiento = hoy.replace(year=hoy.year - 32)
    except ValueError:
        nacimiento = hoy.replace(year=hoy.year - 32, day=28)

    paciente = DatosPacienteInput(data={"fechaNacimiento": nacimiento.isoformat()})
    assert paciente.is_valid(), paciente.errors
    assert paciente.validated_data["edad"] == 32


def test_endpoint_validar_sexo_y_edad(cliente: APIClient) -> None:
    # 1) El sexo solo admite M o F.
    sexo_invalido = cliente.post(
        "/calcular-antropometria",
        data={
            "paciente": {"sexo": "X"},
            "mediciones": {"peso": 68.5, "talla": 165},
        },
        format="json",
        headers={"X-API-Key": "test-token"},
    )
    assert sexo_invalido.status_code == 422

    # 2) La edad debe ser un entero dentro de 0–120.
    edad_invalida = cliente.post(
        "/calcular-antropometria",
        data={
            "paciente": {"edad": 121},
            "mediciones": {"peso": 68.5, "talla": 165},
        },
        format="json",
        headers={"X-API-Key": "test-token"},
    )
    assert edad_invalida.status_code == 422


@pytest.mark.parametrize(
    ("valor", "mensaje"),
    [
        ("68.5", "Ingresá un valor numérico."),
        ("NaN", "Ingresá un número finito."),
        ("Infinity", "Ingresá un número finito."),
    ],
)
def test_endpoint_rechazar_tipo_y_valores_no_finitos(
    cliente: APIClient,
    valor: str,
    mensaje: str,
) -> None:
    # 1) Los campos numéricos no aceptan texto, NaN ni infinito.
    if valor in {"NaN", "Infinity", "-Infinity"}:
        respuesta = cliente.post(
            "/calcular-antropometria",
            data=f'{{"mediciones":{{"peso":{valor}}}}}',
            content_type="application/json",
            headers={"X-API-Key": "test-token"},
        )
    else:
        respuesta = cliente.post(
            "/calcular-antropometria",
            data={"mediciones": {"peso": valor}},
            format="json",
            headers={"X-API-Key": "test-token"},
        )

    assert respuesta.status_code == 422
    if valor in {"NaN", "Infinity", "-Infinity"}:
        assert respuesta.json()["detail"] == "El cuerpo debe ser un JSON válido."
    else:
        assert respuesta.json()["detail"]["mediciones.peso"] == [mensaje]


def test_endpoint_rechazar_peso_no_positivo(cliente: APIClient) -> None:
    # 1) El límite exclusivo de cero tiene un mensaje directo en español.
    respuesta = cliente.post(
        "/calcular-antropometria",
        data={"mediciones": {"peso": 0}},
        format="json",
        headers={"X-API-Key": "test-token"},
    )

    assert respuesta.status_code == 422
    assert respuesta.json()["detail"]["mediciones.peso"] == [
        "Debe ser mayor que 0."
    ]


def test_endpoint_aislar_fallo_de_un_indicador(
    cliente: APIClient,
    solicitud_completa: dict[str, object],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # 1) Un fallo de IMC no impide devolver otros indicadores calculables.
    def fallar_imc(*_args: object) -> float:
        raise RuntimeError("dato interno que no debe exponerse")

    monkeypatch.setattr("core.services.calcular_imc", fallar_imc)
    respuesta = cliente.post(
        "/calcular-antropometria",
        data=solicitud_completa,
        format="json",
        headers={"X-API-Key": "test-token"},
    )

    assert respuesta.status_code == 200
    assert respuesta.json()["resultados"]["imc"] is None
    assert respuesta.json()["resultados"]["icc"] == 0.78
    assert "dato interno" not in respuesta.text


def test_endpoint_ocultar_error_interno(
    cliente: APIClient,
    solicitud_completa: dict[str, object],
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    # 1) Una excepción fuera del cálculo devuelve un envelope genérico.
    def fallar_servicio(_request: object) -> None:
        raise RuntimeError("detalle interno confidencial")

    monkeypatch.setattr(AntropometriaService, "calcular", fallar_servicio)
    respuesta = cliente.post(
        "/calcular-antropometria",
        data=solicitud_completa,
        format="json",
        headers={"X-API-Key": "test-token"},
    )

    assert respuesta.status_code == 500
    assert respuesta.json() == {
        "ok": False,
        "error": True,
        "detail": "Error interno del servidor.",
    }
    assert "detalle interno confidencial" not in respuesta.text
    assert "68.5" not in caplog.text


def test_configuracion_prohibir_token_vacio_en_produccion() -> None:
    # 1) Sin DEBUG ni token, la importación falla con un mensaje explícito.
    raiz = Path(__file__).resolve().parents[2]
    entorno = os.environ.copy()
    entorno["DEBUG"] = "False"
    entorno["API_TOKEN"] = ""
    proceso = subprocess.run(
        [sys.executable, "-c", "import config.settings"],
        cwd=raiz,
        env=entorno,
        capture_output=True,
        text=True,
        check=False,
    )

    assert proceso.returncode != 0
    assert "API_TOKEN es obligatorio" in proceso.stderr
