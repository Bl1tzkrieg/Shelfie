"""Auditoría: contraseña inicial, intentos fallidos, alta de usuarios y sesión al equivocarse."""

import pytest
from fastapi.testclient import TestClient

from app import models
from app.database import get_db
from app.main import app
from app.services import configuracion

OPAC = "/api/v1/opac"


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


def test_entrar_con_el_carnet_obliga_a_cambiar_la_clave(forzado, nuevo, datos):
    datos.lector("1001")
    lector = nuevo()
    r = lector.post(f"{OPAC}/login", json={"username": "1001", "password": "1001"})
    assert r.status_code == 200 and r.json()["debe_cambiar_clave"] is True
    # Solo puede ver su resumen y cambiar la clave.
    assert lector.get(f"{OPAC}/account").status_code == 200
    bloqueado = lector.get(f"{OPAC}/account/loans")
    assert bloqueado.status_code == 403 and "contraseña nueva" in bloqueado.json()["detail"]
    assert lector.post(f"{OPAC}/account/password",
                       json={"actual": "1001", "nueva": "mi-clave-propia"}).status_code == 204
    assert lector.get(f"{OPAC}/account/loans").status_code == 200
    assert lector.get(f"{OPAC}/account").json()["debe_cambiar_clave"] is False


def test_personal_tambien_y_la_restablecida_por_el_personal(forzado, nuevo, datos, db):
    datos.personal("ADM", ["superbibliotecario"])
    admin = nuevo()
    r = admin.post("/api/v1/auth/login", json={"username": "ADM", "password": "ADM"})
    assert r.json()["usuario"]["debe_cambiar_clave"] is True
    assert admin.get("/api/v1/circulation/loans").status_code == 403
    assert admin.get("/api/v1/auth/me").status_code == 200
    admin.post("/api/v1/auth/password", json={"actual": "ADM", "nueva": "admin-propia-1"})
    assert admin.get("/api/v1/circulation/loans").status_code == 200

    lector = datos.lector("1001")
    admin.post("/api/v1/users/1001/password", json={"nueva": "temporal-123"})
    db.refresh(lector)
    assert lector.debe_cambiar_clave is True


def test_sin_forzar_no_se_bloquea(nuevo, datos):
    datos.lector("1001")
    c = nuevo()
    r = c.post(f"{OPAC}/login", json={"username": "1001", "password": "1001"})
    assert r.json()["debe_cambiar_clave"] is False
    assert c.get(f"{OPAC}/account/loans").status_code == 200


def test_intentos_fallidos_frenan_y_se_reinician(nuevo, datos, db):
    datos.lector("1001")
    c = nuevo()
    for _ in range(5):
        assert c.post(f"{OPAC}/login", json={"username": "1001", "password": "x"}).status_code == 401
    frenado = c.post(f"{OPAC}/login", json={"username": "1001", "password": "1001"})
    assert frenado.status_code == 429 and "15 minutos" in frenado.json()["detail"]
    # Otro carnet sigue entrando; al pasar el tiempo (aquí: borrar los intentos) vuelve a entrar.
    datos.lector("1002")
    assert c.post(f"{OPAC}/login", json={"username": "1002", "password": "1002"}).status_code == 200
    db.query(models.IntentoAcceso).delete()
    db.flush()
    assert c.post(f"{OPAC}/login", json={"username": "1001", "password": "1001"}).status_code == 200
    assert db.query(models.IntentoAcceso).count() == 0


def test_carnet_inexistente_cuenta_como_intento(nuevo):
    c = nuevo()
    for _ in range(5):
        c.post("/api/v1/auth/login", json={"username": "nadie", "password": "x"})
    assert c.post("/api/v1/auth/login",
                  json={"username": "nadie", "password": "x"}).status_code == 429


def test_alta_valida_la_clave_y_recorta_datos(client, datos):
    corta = client.post("/api/v1/users", json={"nro_carnet": "3001", "nombre": "A", "apellido": "B",
                                                "email": "a@example.com", "password": "corta"})
    assert corta.status_code == 400
    igual = client.post("/api/v1/users", json={"nro_carnet": "3001", "nombre": "A", "apellido": "B",
                                                "email": "a@example.com", "password": "3001"})
    assert igual.status_code == 400
    sede = datos.sede("NOR", "Norte")
    ok = client.post("/api/v1/users", json={"nro_carnet": " 3001 ", "nombre": "A", "apellido": "B",
                                             "email": "A@Example.com", "biblioteca_id": sede.id})
    assert ok.status_code == 201, ok.text
    assert (ok.json()["nro_carnet"], ok.json()["email"], ok.json()["biblioteca_id"]) == \
        ("3001", "a@example.com", sede.id)
    repetido = client.post("/api/v1/users", json={"nro_carnet": "3002", "nombre": "A",
                                                   "apellido": "B", "email": "a@EXAMPLE.com"})
    assert repetido.status_code == 400
    otra = datos.sede("SUR", "Sur")
    editado = client.put("/api/v1/users/3001", json={"biblioteca_id": otra.id}).json()
    assert editado["biblioteca_id"] == otra.id
    assert client.put("/api/v1/users/3001", json={"biblioteca_id": 99999}).status_code == 404


def test_equivocarse_de_clave_actual_no_cierra_la_sesion(nuevo, datos):
    datos.lector("1001")
    c = nuevo()
    c.post(f"{OPAC}/login", json={"username": "1001", "password": "1001"})
    r = c.post(f"{OPAC}/account/password", json={"actual": "otra", "nueva": "clave-nueva-1"})
    assert r.status_code == 400 and "actual" in r.json()["detail"]
    assert c.get(f"{OPAC}/account/loans").status_code == 200
