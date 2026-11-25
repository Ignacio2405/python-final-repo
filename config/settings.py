"""Configuración del proyecto Django desde variables de entorno."""

import logging
import logging.config
import os
import secrets
from pathlib import Path

from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / ".env")

DEBUG = os.getenv("DEBUG", "False") == "True"
API_TOKEN = os.getenv("API_TOKEN", "").strip()
SECRET_KEY = os.getenv("DJANGO_SECRET_KEY", "").strip()

ALLOWED_HOSTS = [
    host.strip()
    for host in os.getenv("ALLOWED_HOSTS", "").split(",")
    if host.strip()
]

try:
    PORT = int(os.getenv("PORT", "8000"))
except ValueError as exc:
    raise ValueError("PORT debe ser un número entero.") from exc

if not 1 <= PORT <= 65535:
    raise ValueError("PORT debe estar entre 1 y 65535.")

LOG_LEVEL_NAME = os.getenv("LOG_LEVEL", "INFO").upper()
LOG_LEVEL = logging.getLevelNamesMapping().get(LOG_LEVEL_NAME)
if not isinstance(LOG_LEVEL, int):
    raise ValueError("LOG_LEVEL debe ser un nivel de logging válido.")

if not DEBUG and not API_TOKEN:
    raise RuntimeError("API_TOKEN es obligatorio cuando DEBUG no está activo.")
if not DEBUG and not os.getenv("DJANGO_SECRET_KEY", "").strip():
    raise RuntimeError("DJANGO_SECRET_KEY es obligatorio cuando DEBUG no está activo.")
if not DEBUG and not ALLOWED_HOSTS:
    raise RuntimeError("ALLOWED_HOSTS es obligatorio cuando DEBUG no está activo.")
if not SECRET_KEY:
    SECRET_KEY = secrets.token_urlsafe(50)

ROOT_URLCONF = "config.urls"
ASGI_APPLICATION = "config.asgi.application"
WSGI_APPLICATION = "config.wsgi.application"
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"
LANGUAGE_CODE = "es"
TIME_ZONE = "UTC"
USE_I18N = True
USE_TZ = True
APPEND_SLASH = False

INSTALLED_APPS = [
    "django.contrib.contenttypes",
    "rest_framework",
    "core.apps.CoreConfig",
]

MIDDLEWARE = []

REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": [],
    "DEFAULT_PERMISSION_CLASSES": ["rest_framework.permissions.AllowAny"],
    "DEFAULT_RENDERER_CLASSES": ["rest_framework.renderers.JSONRenderer"],
    "DEFAULT_PARSER_CLASSES": ["rest_framework.parsers.JSONParser"],
    "EXCEPTION_HANDLER": "core.exceptions.manejar_excepcion",
    "UNAUTHENTICATED_USER": None,
}

logging.config.dictConfig(
    {
        "version": 1,
        "disable_existing_loggers": False,
        "formatters": {
            "simple": {
                "format": "[{asctime}] {levelname} {name}: {message}",
                "style": "{",
            }
        },
        "handlers": {
            "console": {
                "class": "logging.StreamHandler",
                "stream": "ext://sys.stdout",
                "formatter": "simple",
            }
        },
        "root": {"handlers": ["console"], "level": LOG_LEVEL},
    }
)

if DEBUG and not API_TOKEN:
    logging.getLogger(__name__).warning(
        "La autenticación X-API-Key está desactivada porque DEBUG está activo."
    )
