"""Fase 8: registro de acciones (action_logs de Koha)."""

from datetime import timedelta

from app import models
from app.core.tiempo import ahora
from app.services import registro

LOGS = "/api/v1/logs"
CIRC = "/api/v1/circulation"


def _acciones(db, **filtro):
    db.expire_all()
    return db.query(models.RegistroAccion).filter_by(**filtro).order_by(
        models.RegistroAccion.id).all()


def test_prestamo_devolucion_y_renovacion_quedan_con_quien_y_sobre_que(client, datos, db):
    libro = datos.titulo()
    item = datos.ejemplar(libro, "R-1")
    lector = datos.lector("L-1")
    admin = db.query(models.Usuario).filter_by(nro_carnet="ADMIN").one()

    assert client.post(f"{CIRC}/checkout", json={"codigo_barras": "R-1", "nro_carnet": "L-1"}).status_code in (200, 201)
    prestamo = db.query(models.Prestamo).filter_by(item_id=item.id).one()
    assert client.post(f"{CIRC}/renew", json={"prestamo_id": prestamo.id}).status_code == 200
    assert client.post(f"{CIRC}/checkin", json={"codigo_barras": "R-1"}).status_code == 200

    filas = _acciones(db, modulo="circulacion")
    assert [f.accion for f in filas] == ["prestamo", "renovacion", "devolucion"]
    for f in filas:
        assert (f.usuario_id, f.lector_id, f.item_id, f.biblio_id) == (admin.id, lector.id, item.id, libro.id)
        assert f.desde_opac is False
    assert "R-1" in filas[0].descripcion and "Cien años de soledad" in filas[0].descripcion

    # La consulta filtra por lector, por código y por módulo.
    r = client.get(LOGS, params={"lector": "L-1"}).json()
    assert r["total"] == 3 and r["filas"][0]["accion"] == "devolucion"
    assert r["filas"][0]["actor_carnet"] == "ADMIN" and r["filas"][0]["codigo_barras"] == "R-1"
    assert client.get(LOGS, params={"codigo": "r-1", "modulo": "circulacion"}).json()["total"] == 3
    assert client.get(LOGS, params={"accion": "prestamo"}).json()["total"] == 1


def test_una_operacion_rechazada_no_queda_registrada(client, datos, db):
    referencia = datos.tipo_item("REF", "Referencia", prestable=False)
    datos.ejemplar(datos.titulo(), "REF-1", tipo=referencia)
    datos.lector("L-1")
    r = client.post(f"{CIRC}/checkout", json={"codigo_barras": "REF-1", "nro_carnet": "L-1"})
    assert r.status_code == 400
    assert _acciones(db, modulo="circulacion") == []


def test_cobros_con_montos(client, datos, db):
    from decimal import Decimal

    from app.services import cuentas
    lector = datos.lector("L-1")
    cuentas.registrar(db, lector, "MULTA_ATRASO", Decimal("10"), descripcion="Atraso")
    db.commit()
    r = client.post("/api/v1/users/L-1/account/payments", json={"monto": 4})
    assert r.status_code == 200, r.text
    client.post("/api/v1/users/L-1/account/waivers", json={"monto": 1, "motivo": "error de fecha"})

    pago, condonacion = _acciones(db, modulo="cuentas")
    assert (pago.accion, pago.lector_id) == ("pago", lector.id)
    assert pago.datos["monto"] == 4 and pago.datos["deuda_despues"] == 6
    assert condonacion.accion == "condonacion" and "error de fecha" in condonacion.descripcion


def test_cambios_de_lector_y_de_permisos(client, datos, db):
    datos.lector("L-1")
    client.put("/api/v1/users/L-1", json={"email": "nueva@example.com", "nombre": "Ana María"})
    client.patch("/api/v1/users/L-1/status", json={"activo": False})
    client.put("/api/v1/staff/L-1", json={"es_personal": True, "permisos": ["circulacion"]})

    edicion, suspension, permisos = _acciones(db, modulo="lectores")
    assert edicion.accion == "edicion"
    assert edicion.datos["cambios"]["email"][1] == "nueva@example.com"
    assert set(edicion.datos["cambios"]) == {"email", "nombre"}
    assert suspension.accion == "suspension"
    assert permisos.accion == "permisos" and permisos.datos["cambios"]["permisos"] == [[], ["circulacion"]]


def test_entradas_fallos_y_salidas_sin_la_contrasena(anonimo, datos, db):
    datos.personal("P-9", ["circulacion"])
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


def test_dar_de_baja_un_ejemplar(client, datos, db):
    libro = datos.titulo()
    item = datos.ejemplar(libro, "B-1")
    client.patch(f"/api/v1/catalog/items/{libro.id}/ejemplares/{item.id}", json={"estado": "Retirado"})
    [baja] = _acciones(db, modulo="catalogo")
    assert baja.accion == "baja" and baja.datos["cambios"]["estado"] == ["Disponible", "Retirado"]


def test_ajustes_con_antes_y_despues(client, db):
    client.put("/api/v1/settings", json={"circulacion": {"umbral_bloqueo": 12}})
    [cambio] = _acciones(db, modulo="configuracion")
    assert cambio.datos["seccion"] == "circulacion"
    assert cambio.datos["cambios"]["umbral_bloqueo"] == [5.0, 12]


def test_apagar_un_modulo_deja_de_registrarlo_pero_el_cambio_queda(client, datos, db):
    r = client.put(f"{LOGS}/settings", json={"modulos": {"circulacion": False, "configuracion": False}})
    assert r.status_code == 200 and r.json()["modulos"]["circulacion"] is False
    datos.ejemplar(datos.titulo(), "R-1")
    datos.lector("L-1")
    client.post(f"{CIRC}/checkout", json={"codigo_barras": "R-1", "nro_carnet": "L-1"})

    assert _acciones(db, modulo="circulacion") == []
    # Apagar el registro de configuración no impide que se vea quién lo apagó.
    [ajuste] = _acciones(db, modulo="configuracion")
    assert ajuste.datos["cambios"]["modulos.circulacion"] == [True, False]
    assert client.put(f"{LOGS}/settings", json={"modulos": {"inventado": True}}).status_code == 400


def test_lo_hecho_desde_el_opac_se_marca(datos, db):
    from fastapi.testclient import TestClient

    from app.database import get_db
    from app.main import app
    lector = datos.lector("1001")
    item = datos.ejemplar(datos.titulo(), "X-1", estado="Prestado")
    prestamo = datos.prestamo(item, lector)
    db.commit()
    app.dependency_overrides[get_db] = lambda: db
    try:
        with TestClient(app) as opac:
            assert opac.post("/api/v1/opac/login",
                             json={"username": "1001", "password": "1001"}).status_code == 200
            r = opac.post(f"/api/v1/opac/account/loans/{prestamo.id}/renew", json={})
            assert r.status_code == 200, r.text
    finally:
        app.dependency_overrides.clear()
    [renovacion] = _acciones(db, accion="renovacion")
    assert renovacion.desde_opac is True and renovacion.usuario_id == lector.id


def test_permisos_para_consultar_y_configurar(como):
    assert como(["circulacion"]).get(LOGS).status_code == 403
    registro_ = como(["registro"])
    assert registro_.get(LOGS).status_code == 200
    assert registro_.put(f"{LOGS}/settings", json={"dias_retencion": 1}).status_code == 403


def test_exportar_y_buscar_por_texto(client, datos):
    datos.lector("L-1")
    client.patch("/api/v1/users/L-1/status", json={"activo": False})
    assert client.get(LOGS, params={"q": "suspendió"}).json()["total"] == 1
    r = client.get(f"{LOGS}/export", params={"modulo": "lectores"})
    assert r.status_code == 200 and "Suspendió la cuenta" in r.text


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
