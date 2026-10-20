"""Cambio de la propia contraseña."""

from fastapi.testclient import TestClient

from app.main import app
from tests.conftest import iniciar_sesion


def test_cambiar_la_propia_contrasena(como, anonimo):
    yo = como(["catalogo"], username="P-1")

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


