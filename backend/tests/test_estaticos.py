"""El backend sirve el frontend exportado (frontend/out) sin tapar la API."""

from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app import estaticos
from app.config import Settings
from app.database import get_db
from app.routers import buscar


@pytest.fixture()
def carpeta(tmp_path):
    out = tmp_path / "out"
    (out / "ingreso").mkdir(parents=True)
    (out / "index.html").write_text("<h1>Buscar</h1>", encoding="utf-8")
    (out / "ingreso" / "index.html").write_text("<h1>Ingreso</h1>", encoding="utf-8")
    (out / "404.html").write_text("<h1>No existe</h1>", encoding="utf-8")
    # Un archivo fuera de la carpeta servida: nunca debe poder leerse.
    (tmp_path / "secreto.txt").write_text("clave", encoding="utf-8")
    return out


@pytest.fixture()
def cliente(db, carpeta):
    app = FastAPI()
    app.include_router(buscar.router)
    app.dependency_overrides[get_db] = lambda: db
    estaticos.montar(app, carpeta)
    with TestClient(app) as c:
        yield c


def test_sirve_index(cliente):
    r = cliente.get("/")
    assert r.status_code == 200
    assert "Buscar" in r.text
    assert r.headers["content-type"].startswith("text/html")


def test_sirve_ruta_con_barra_final(cliente):
    r = cliente.get("/ingreso/")
    assert r.status_code == 200
    assert "Ingreso" in r.text
    # Sin la barra final también llega a la página.
    assert "Ingreso" in cliente.get("/ingreso").text


def test_api_no_se_intercepta(cliente):
    r = cliente.get("/api/v1/buscar", params={"q": "x"})
    assert r.status_code == 200
    assert r.headers["content-type"].startswith("application/json")
    # Una ruta de la API que no existe sigue siendo un 404 en JSON, no la página 404.
    r = cliente.get("/api/v1/no-existe")
    assert r.status_code == 404
    assert r.json() == {"detail": "Not Found"}
    assert cliente.post("/api/v1/no-existe").status_code == 404


def test_404(cliente):
    r = cliente.get("/no-existe/")
    assert r.status_code == 404
    assert "No existe" in r.text


def test_no_sale_de_la_carpeta(cliente):
    for ruta in ("/../secreto.txt", "/%2e%2e/secreto.txt", "/ingreso/../../secreto.txt"):
        r = cliente.get(ruta)
        assert "clave" not in r.text, ruta


def test_carpeta_inexistente_no_monta_nada(tmp_path):
    app = FastAPI()
    estaticos.montar(app, tmp_path / "no-hay")
    assert TestClient(app).get("/").status_code == 404


def test_carpeta_por_defecto_no_depende_del_directorio_actual(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    ruta = Settings().frontend_dir
    assert ruta.is_absolute()
    assert ruta == (Path(__file__).resolve().parents[2] / "frontend" / "out")


def test_las_paginas_se_revalidan_en_cada_visita(cliente, carpeta):
    # Sin Cache-Control el navegador guarda las páginas y los .txt de Next "a ojo" (según la
    # fecha del archivo): tras actualizar mezcla la versión vieja con la nueva y Next recarga
    # la página sin parar. Se piden de nuevo siempre (con ETag, la respuesta es un 304).
    (carpeta / "__next._tree.txt").write_text("arbol", encoding="utf-8")
    for ruta in ("/", "/ingreso/", "/__next._tree.txt"):
        assert cliente.get(ruta).headers["cache-control"] == "no-cache", ruta
    r = cliente.get("/no-existe/")
    assert r.status_code == 404
    assert r.headers["cache-control"] == "no-cache"


def test_los_archivos_con_hash_se_guardan_para_siempre(cliente, carpeta):
    # /_next/static/ lleva el hash del contenido en el nombre: un cambio es otro archivo.
    (carpeta / "_next" / "static" / "chunks").mkdir(parents=True)
    (carpeta / "_next" / "static" / "chunks" / "a1b2.js").write_text("x", encoding="utf-8")
    r = cliente.get("/_next/static/chunks/a1b2.js")
    assert r.status_code == 200
    assert r.headers["cache-control"] == "public, max-age=31536000, immutable"
