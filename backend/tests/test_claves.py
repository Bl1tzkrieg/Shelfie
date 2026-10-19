"""Cambio de la propia contraseña y restablecimiento por el personal."""

from fastapi.testclient import TestClient

from app.main import app
from tests.conftest import iniciar_sesion


def test_cambiar_la_propia_contrasena(como, anonimo):
    yo = como(["circulacion"], carnet="P-1")

    malo = yo.post("/api/v1/auth/password", json={"actual": "otra", "nueva": "nueva-clave-1"})
    assert malo.status_code == 400 and "actual" in malo.json()["detail"]
    for nueva, texto in [("corta", "8 caracteres"), ("P-1", "distinta")]:
        r = yo.post("/api/v1/auth/password", json={"actual": "P-1", "nueva": nueva})
        assert r.status_code == 400 and texto in r.json()["detail"]

    # Otra sesión abierta antes del cambio.
    otra = iniciar_sesion(TestClient(app), "P-1", "P-1")
    r = yo.post("/api/v1/auth/password", json={"actual": "P-1", "nueva": "nueva-clave-1"})
    assert r.status_code == 204

    assert yo.get("/api/v1/auth/me").status_code == 200   # esta sesión sigue
    vieja = otra.get("/api/v1/auth/me")
    assert vieja.status_code == 401 and "contraseña cambió" in vieja.json()["detail"]
    assert anonimo.post("/api/v1/auth/login",
                        json={"username": "P-1", "password": "P-1"}).status_code == 401
    assert anonimo.post("/api/v1/auth/login",
                        json={"username": "P-1", "password": "nueva-clave-1"}).status_code == 200
    otra.close()


def test_restablecer_la_de_un_lector(como, datos, anonimo):
    datos.lector("L-9")
    lectores = como(["lectores"], carnet="P-2")

    r = lectores.post("/api/v1/users/L-9/password", json={"nueva": "clave-del-lector"})

    assert r.status_code == 204
    assert lectores.post("/api/v1/users/L-9/password", json={"nueva": "L-9"}).status_code == 400
    assert como(["circulacion"], carnet="P-3").post(
        "/api/v1/users/L-9/password", json={"nueva": "otra-clave-1"}).status_code == 403


def test_la_del_personal_solo_la_restablece_un_superbibliotecario(como):
    lectores = como(["lectores"], carnet="P-4")
    como(["catalogo"], carnet="P-5")
    admin = como(["superbibliotecario"], carnet="A-1")

    r = lectores.post("/api/v1/users/P-5/password", json={"nueva": "clave-nueva-5"})
    assert r.status_code == 403 and "superbibliotecario" in r.json()["detail"]
    assert admin.post("/api/v1/users/P-5/password", json={"nueva": "clave-nueva-5"}).status_code == 204
    propia = admin.post("/api/v1/users/A-1/password", json={"nueva": "clave-nueva-a"})
    assert propia.status_code == 400 and "Cambiar contraseña" in propia.json()["detail"]
