"""Fase 8: registro de acciones (action_logs de Koha)."""

from datetime import timedelta

from app import models
from app.core.tiempo import ahora
from app.services import registro

LOGS = "/api/v1/logs"


def _acciones(db, **filtro):
    db.expire_all()
    return db.query(models.RegistroAccion).filter_by(**filtro).order_by(
        models.RegistroAccion.id).all()


def test_cambio_de_rol(client, datos, db):
    ana = datos.personal("ana", ["catalogo"])
    client.put(f"/api/v1/staff/{ana.id}/role", json={"rol": "administrador"})

    [rol] = _acciones(db, modulo="configuracion")
    assert rol.accion == "permisos" and rol.datos["cambios"]["rol"] == ["catalogador", "administrador"]
    assert rol.lector_id == ana.id
    # Se filtra por el username del usuario afectado.
    assert client.get(LOGS, params={"lector": "ANA"}).json()["total"] == 1


def test_entradas_fallos_y_salidas_sin_la_contrasena(anonimo, datos, db):
    datos.personal("P-9", ["catalogo"])
    assert anonimo.post("/api/v1/auth/login", json={"username": "P-9", "password": "mala-clave"}).status_code == 401
    assert anonimo.post("/api/v1/auth/login", json={"username": "P-9", "password": "P-9"}).status_code == 200
    assert anonimo.post("/api/v1/auth/logout").status_code == 204

    fallo, entrada, salida = _acciones(db, modulo="sesion")
    assert (fallo.accion, fallo.usuario_id) == ("entrada_fallida", None)
    assert "P-9" in fallo.descripcion and "mala-clave" not in fallo.descripcion
    assert entrada.accion == "entrada" and entrada.usuario_id is not None
    assert salida.accion == "salida" and salida.usuario_id == entrada.usuario_id
    assert all(f.ip for f in (fallo, entrada, salida))


def test_editar_el_marc_guarda_el_anterior(client, datos, db):
    from tests.test_marc import _campo, _registro
    libro = client.post("/api/v1/catalog/records", json={
        "plantilla": "BKS", "marc": _registro(_campo("245", ("a", "Título viejo")))}).json()
    r = client.put(f"/api/v1/catalog/items/{libro['id']}/marc", json={
        "plantilla": "BKS", "marc": _registro(_campo("245", ("a", "Título nuevo")))})
    assert r.status_code == 200, r.text

    alta, edicion = _acciones(db, modulo="catalogo")
    assert alta.accion == "alta" and edicion.accion == "edicion"
    assert edicion.datos["cambios"]["titulo"] == ["Título viejo", "Título nuevo"]
    assert "Título viejo" in str(edicion.datos["marc_anterior"])
    historial = client.get(LOGS, params={"biblio_id": libro["id"]}).json()
    assert historial["total"] == 2


def test_editar_un_ejemplar(client, datos, db):
    libro = datos.titulo()
    item = datos.ejemplar(libro, "B-1")
    client.patch(f"/api/v1/catalog/items/{libro.id}/ejemplares/{item.id}", json={"nota": "Roto"})
    [edicion] = _acciones(db, modulo="catalogo")
    assert edicion.accion == "edicion" and edicion.datos["cambios"]["nota"] == [None, "Roto"]


def test_ajustes_con_antes_y_despues(client, db):
    client.put("/api/v1/settings", json={"biblioteca": {"codigo": "UNA"}})
    [cambio] = _acciones(db, modulo="configuracion")
    assert cambio.datos["seccion"] == "biblioteca"
    assert cambio.datos["cambios"]["codigo"] == ["BIB", "UNA"]


def test_apagar_un_modulo_deja_de_registrarlo_pero_el_cambio_queda(client, datos, db):
    r = client.put(f"{LOGS}/settings", json={"modulos": {"catalogo": False, "configuracion": False}})
    assert r.status_code == 200 and r.json()["modulos"]["catalogo"] is False
    libro = datos.titulo()
    item = datos.ejemplar(libro, "R-1")
    client.patch(f"/api/v1/catalog/items/{libro.id}/ejemplares/{item.id}", json={"nota": "Roto"})

    assert _acciones(db, modulo="catalogo") == []
    # Apagar el registro de configuración no impide que se vea quién lo apagó.
    [ajuste] = _acciones(db, modulo="configuracion")
    assert ajuste.datos["cambios"]["modulos.catalogo"] == [True, False]
    assert client.put(f"{LOGS}/settings", json={"modulos": {"inventado": True}}).status_code == 400


def test_exportar_y_buscar_por_texto(client, datos):
    libro = datos.titulo()
    item = datos.ejemplar(libro, "B-1")
    client.delete(f"/api/v1/catalog/items/{libro.id}/ejemplares/{item.id}")
    assert client.get(LOGS, params={"q": "eliminó el ejemplar"}).json()["total"] == 1
    r = client.get(f"{LOGS}/export", params={"modulo": "catalogo"})
    assert r.status_code == 200 and "Eliminó el ejemplar B-1" in r.text


def test_retencion_borra_lo_viejo(client, db):
    viejo = models.RegistroAccion(fecha=ahora() - timedelta(days=800), modulo="sesion",
                                  accion="entrada", descripcion="viejo")
    reciente = models.RegistroAccion(fecha=ahora() - timedelta(days=10), modulo="sesion",
                                     accion="entrada", descripcion="reciente")
    db.add_all([viejo, reciente])
    db.commit()
    assert registro.depurar(db) == 1
    client.put(f"{LOGS}/settings", json={"dias_retencion": 0})
    assert registro.depurar(db) == 0  # 0 = guardar todo


def test_los_secretos_no_llegan_al_registro():
    limpio = registro._sin_secretos({"password": "x", "smtp_clave": "y", "otro": {"token": "z"},
                                     "nombre": "Ana"})
    assert limpio == {"password": "***", "smtp_clave": "***", "otro": {"token": "***"},
                      "nombre": "Ana"}
