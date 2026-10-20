"""Gestión del personal (solo administrador) y los ejemplares del modelo reducido."""

import pytest
from fastapi.testclient import TestClient

from app import models
from app.main import app
from app.services import configuracion
from tests.conftest import iniciar_sesion

STAFF = "/api/v1/staff"


def _por_usuario(client, username):
    return next(u for u in client.get(STAFF).json() if u["username"] == username)


def test_admin_crea_catalogador_y_debe_cambiar_clave(client, db):
    configuracion.guardar(db, {"seguridad": {"forzar_cambio_clave": True}}, anotar=False)
    r = client.post(STAFF, json={"username": "maria", "nombre": "María", "apellido": "Rojas",
                                 "rol": "catalogador", "clave_temporal": "temporal-123"})
    assert r.status_code == 201, r.text
    vista = r.json()
    assert set(vista) == {"id", "username", "nombre", "apellido", "rol", "activo",
                          "debe_cambiar_clave"}
    assert (vista["username"], vista["rol"], vista["activo"], vista["debe_cambiar_clave"]) == (
        "maria", "catalogador", True, True)
    usuario = db.get(models.Usuario, vista["id"])
    assert usuario.permisos == ["catalogo"]

    # Entra con la clave temporal, pero antes de seguir tiene que elegir una propia.
    nueva = iniciar_sesion(TestClient(app), "MARIA", "temporal-123")
    assert nueva.get("/api/v1/catalog/items").status_code == 403
    assert nueva.post("/api/v1/auth/password", json={"actual": "temporal-123",
                                                      "nueva": "propia-456"}).status_code == 204
    assert nueva.get("/api/v1/catalog/items").status_code == 200
    nueva.close()

    repetido = client.post(STAFF, json={"username": "Maria", "nombre": "Otra", "apellido": "X",
                                        "rol": "catalogador", "clave_temporal": "temporal-123"})
    assert repetido.status_code == 400 and "maria" in repetido.json()["detail"].lower()
    assert client.post(STAFF, json={"username": "x", "nombre": "X", "apellido": "X",
                                    "rol": "lector", "clave_temporal": "temporal-123"}
                       ).status_code == 422

    # Restablecer la clave vuelve a pedir el cambio.
    assert client.post(f"{STAFF}/{vista['id']}/password",
                       json={"clave_temporal": "otra-temporal"}).status_code == 200
    db.refresh(usuario)
    assert usuario.debe_cambiar_clave is True
    assert _por_usuario(client, "maria")["debe_cambiar_clave"] is True


def test_rol_y_estado(client, datos, anonimo):
    catalogador = datos.personal("ana", ["catalogo"])

    r = client.put(f"{STAFF}/{catalogador.id}/role", json={"rol": "administrador"})
    assert r.status_code == 200 and r.json()["rol"] == "administrador"

    r = client.put(f"{STAFF}/{catalogador.id}/active", json={"activo": False})
    assert r.status_code == 200 and r.json()["activo"] is False
    # Desactivado no entra (mismo 401 que una clave mala: no revela que la cuenta existe).
    assert anonimo.post("/api/v1/auth/login",
                        json={"username": "ana", "password": "ana"}).status_code == 401
    assert client.put(f"{STAFF}/999999/active", json={"activo": True}).status_code == 404


def test_no_quedar_sin_administradores(client, db):
    admin = db.query(models.Usuario).filter_by(username="ADMIN").one()
    for ruta, cuerpo in (("role", {"rol": "catalogador"}), ("active", {"activo": False})):
        r = client.put(f"{STAFF}/{admin.id}/{ruta}", json=cuerpo)
        assert r.status_code == 400, r.text
        assert "administrador" in r.json()["detail"]
    db.refresh(admin)
    assert admin.activo and admin.permisos == ["superbibliotecario"]


def test_con_otro_administrador_si_se_puede_degradar(client, datos, db):
    datos.personal("otro-admin", ["superbibliotecario"])
    admin = db.query(models.Usuario).filter_by(username="ADMIN").one()
    r = client.put(f"{STAFF}/{admin.id}/role", json={"rol": "catalogador"})
    assert r.status_code == 200 and r.json()["rol"] == "catalogador"


def test_catalogador_no_gestiona_personal(como, datos):
    otro = datos.personal("otro", ["catalogo"])
    catalogador = como(["catalogo"])
    assert catalogador.get(STAFF).status_code == 403
    assert catalogador.post(STAFF, json={"username": "x", "nombre": "X", "apellido": "X",
                                         "rol": "catalogador",
                                         "clave_temporal": "temporal-123"}).status_code == 403
    assert catalogador.put(f"{STAFF}/{otro.id}/role", json={"rol": "administrador"}).status_code == 403
    assert catalogador.put(f"{STAFF}/{otro.id}/active", json={"activo": False}).status_code == 403
    assert catalogador.post(f"{STAFF}/{otro.id}/password",
                            json={"clave_temporal": "temporal-123"}).status_code == 403


# --- Ejemplares: el código de barras es opcional, pero único si existe -----------------

def test_dos_codigos_vacios_no_chocan(datos, db):
    libro = datos.titulo()
    datos.ejemplar(libro)
    datos.ejemplar(libro, copia="c.2")
    assert db.query(models.Item).filter(models.Item.codigo_barras.is_(None)).count() == 2


def test_codigo_repetido_da_409(client, datos, db):
    libro = datos.titulo()
    datos.ejemplar(libro, "B-1")
    r = client.post(f"/api/v1/catalog/items/{libro.id}/ejemplares", json={"codigo_barras": "B-1"})
    assert r.status_code == 409 and "B-1" in r.json()["detail"]

    # Aunque se cuele por la base, el índice único lo frena.
    from sqlalchemy.exc import IntegrityError
    with pytest.raises(IntegrityError):
        with db.begin_nested():
            datos.ejemplar(libro, "B-1")
