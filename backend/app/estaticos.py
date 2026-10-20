"""Sirve el frontend exportado (`next build` → frontend/out) desde el mismo FastAPI.

Así la instalación es un solo proceso en el puerto 8080: la API en /api/v1 y las
páginas en el resto de las rutas.
"""

from pathlib import Path

from fastapi import FastAPI
from starlette.routing import Match, Mount
from starlette.staticfiles import StaticFiles
from starlette.types import Scope


def _es_de_la_api(ruta: str) -> bool:
    return ruta == "/api" or ruta.startswith("/api/")


class _MontajeSinApi(Mount):
    """Un montaje en "/" que deja pasar /api/*: una ruta de la API que no existe sigue
    respondiendo el 404 en JSON de FastAPI y no la página 404 del frontend."""

    def matches(self, scope: Scope) -> tuple[Match, Scope]:
        if scope["type"] == "http" and _es_de_la_api(scope.get("path", "")):
            return Match.NONE, {}
        return super().matches(scope)


def montar(app: FastAPI, carpeta: Path) -> None:
    """Sirve los archivos de `carpeta`. Una ruta de carpeta (`/ingreso/`) responde su
    `index.html` (`/ingreso` redirige a `/ingreso/`) y lo que no existe, `404.html`
    con estado 404. Va al final de las rutas; si la carpeta no existe no monta nada.

    StaticFiles resuelve la ruta real y rechaza lo que quede fuera de la carpeta
    (`/../`), así que no se puede leer nada más del disco."""
    if not carpeta.is_dir():
        return
    archivos = StaticFiles(directory=carpeta, html=True)
    app.router.routes.append(_MontajeSinApi("/", app=archivos, name="frontend"))
