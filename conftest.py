"""Fixtures compartidas por las pruebas del módulo."""

import os
from collections.abc import Generator
from datetime import date

os.environ["DJANGO_SETTINGS_MODULE"] = "config.settings"
os.environ["DEBUG"] = "True"
os.environ["API_TOKEN"] = "test-token"

import django
import pytest
from django.test import override_settings
from rest_framework.test import APIClient

django.setup()


@pytest.fixture
def cliente() -> Generator[APIClient, None, None]:
    with override_settings(
        DEBUG=True,
        API_TOKEN="test-token",
        ALLOWED_HOSTS=["testserver"],
    ):
        cliente_api = APIClient()
        cliente_api.raise_request_exception = False
        yield cliente_api


@pytest.fixture
def paciente_mujer() -> dict[str, object]:
    hoy = date.today()
    try:
        nacimiento = hoy.replace(year=hoy.year - 32)
    except ValueError:
        nacimiento = hoy.replace(year=hoy.year - 32, day=28)
    return {
        "sexo": "F",
        "edad": 32,
        "fechaNacimiento": nacimiento.isoformat(),
    }


@pytest.fixture
def mediciones_completas() -> dict[str, float]:
    return {
        "peso": 68.5,
        "talla": 165,
        "cuello": 33,
        "brazo": 29,
        "cintura": 76,
        "cadera": 98,
        "pTricipital": 18,
        "pBicipital": 10,
        "pSubescapular": 16,
        "pSuprailiaco": 15,
    }


@pytest.fixture
def solicitud_completa(
    paciente_mujer: dict[str, object],
    mediciones_completas: dict[str, float],
) -> dict[str, object]:
    return {"paciente": paciente_mujer, "mediciones": mediciones_completas}
