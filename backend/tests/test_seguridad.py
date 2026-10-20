"""Auditoría: contraseña inicial e intentos fallidos."""

import pytest
from fastapi.testclient import TestClient

from app import models
from app.database import get_db
from app.main import app
from app.services import configuracion

LOGIN = "/api/v1/auth/login"

@pytest.fixture()
def forzado(db):
    configuracion.guardar(db, {"seguridad": {"forzar_cambio_clave": True}})


@pytest.fixture()
def nuevo(db):
    app.dependency_overrides[get_db] = lambda: db
    abiertos = []

    def _cliente():
        c = TestClient(app)
        abiertos.append(c)
        return c
    yield _cliente
    for c in abiertos:
        c.close()
    app.dependency_overrides.clear()


def test_entrar_con_el_usuario_como_clave_obliga_a_cambiarla(forzado, nuevo, datos):
    datos.personal("ADM", ["superbibliotecario"])
    admin = nuevo()
    r = admin.post("/api/v1/auth/login", json={"username": "ADM", "password": "ADM"})
    assert r.json()["usuario"]["debe_cambiar_clave"] is True
    bloqueado = admin.get("/api/v1/catalog/items")
    assert bloqueado.status_code == 403 and "contraseña nueva" in bloqueado.json()["detail"]
    assert admin.get("/api/v1/auth/me").status_code == 200
    admin.post("/api/v1/auth/password", json={"actual": "ADM", "nueva": "admin-propia-1"})
    assert admin.get("/api/v1/catalog/items").status_code == 200
    assert admin.get("/api/v1/auth/me").json()["debe_cambiar_clave"] is False


def test_sin_forzar_no_se_bloquea(nuevo, datos):
    datos.personal("1001", ["catalogo"])
    c = nuevo()
    r = c.post("/api/v1/auth/login", json={"username": "1001", "password": "1001"})
    assert r.json()["usuario"]["debe_cambiar_clave"] is False
    assert c.get("/api/v1/catalog/items").status_code == 200


def test_intentos_fallidos_frenan_y_se_reinician(nuevo, datos, db):
    datos.personal("1001", ["catalogo"])
    c = nuevo()
    for _ in range(5):
        assert c.post(LOGIN, json={"username": "1001", "password": "x"}).status_code == 401
    frenado = c.post(LOGIN, json={"username": "1001", "password": "1001"})
    assert frenado.status_code == 429 and "15 minutos" in frenado.json()["detail"]
    # Otro usuario sigue entrando; al pasar el tiempo (aquí: borrar los intentos) vuelve a entrar.
    datos.personal("1002", ["catalogo"])
    assert c.post(LOGIN, json={"username": "1002", "password": "1002"}).status_code == 200
    db.query(models.IntentoAcceso).delete()
    db.flush()
    assert c.post(LOGIN, json={"username": "1001", "password": "1001"}).status_code == 200
    assert db.query(models.IntentoAcceso).count() == 0


def test_usuario_inexistente_cuenta_como_intento(nuevo):
    c = nuevo()
    for _ in range(5):
        c.post("/api/v1/auth/login", json={"username": "nadie", "password": "x"})
    assert c.post("/api/v1/auth/login",
                  json={"username": "nadie", "password": "x"}).status_code == 429


