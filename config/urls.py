"""Enrutamiento raíz del proyecto."""

from django.urls import include, path, re_path

from core.exceptions import manejar_404

urlpatterns = [
    path("", include("core.urls")),
    re_path(r"^.*$", manejar_404),
]

handler404 = "core.exceptions.manejar_404"
handler500 = "core.exceptions.manejar_500"
