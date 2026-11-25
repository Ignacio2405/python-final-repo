"""Registro de rutas HTTP del módulo."""

from django.urls import path

from core.views import CalcularAntropometriaView, HealthView

urlpatterns = [
    path("health", HealthView.as_view(), name="health"),
    path(
        "calcular-antropometria",
        CalcularAntropometriaView.as_view(),
        name="calcular-antropometria",
    ),
]
