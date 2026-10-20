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
