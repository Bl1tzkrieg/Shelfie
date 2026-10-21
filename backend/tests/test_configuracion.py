"""Configuración lite: nombre, código de sede, tipo de ítem y código de organización MARC
de la biblioteca, y respaldo."""

from app import models


def test_configuracion_por_defecto(client):
    c = client.get("/api/v1/settings").json()
    assert set(c) == {"biblioteca", "respaldo"}
    assert c["biblioteca"] == {"nombre": "Biblioteca", "codigo_sede": "BIB", "tipo_item": "LIB",
                               "codigo_organizacion": ""}
    assert c["respaldo"] == {"carpeta": None, "pg_dump": None, "ultimo": None, "ultimo_ok": None}


def test_nombre_publico_sin_sesion(anonimo, client):
    client.put("/api/v1/settings", json={"biblioteca": {"nombre": "Biblioteca de Prueba"}})

    r = anonimo.get("/api/v1/settings")

    assert r.status_code == 200
    assert r.json() == {"biblioteca": {"nombre": "Biblioteca de Prueba"}}
    assert "respaldo" not in r.json()


def test_catalogador_ve_biblioteca_sin_respaldo(como):
    r = como(["catalogo"]).get("/api/v1/settings")

    assert r.status_code == 200
    assert set(r.json()) == {"biblioteca"}
    assert r.json()["biblioteca"]["codigo_sede"] == "BIB"


def test_solo_el_administrador_guarda(como, anonimo):
    cuerpo = {"biblioteca": {"nombre": "X"}}
    assert como(["catalogo"]).put("/api/v1/settings", json=cuerpo).status_code == 403
    assert anonimo.put("/api/v1/settings", json=cuerpo).status_code == 401


def test_guardar_mezcla_secciones(client):
    r = client.put("/api/v1/settings", json={"biblioteca": {"nombre": "Biblioteca de Prueba"}})

    assert r.status_code == 200
    assert r.json()["biblioteca"]["nombre"] == "Biblioteca de Prueba"
    assert r.json()["biblioteca"]["codigo_sede"] == "BIB"  # el resto conserva sus valores

    client.put("/api/v1/settings", json={"biblioteca": {"codigo_sede": "UNA"}})
    c = client.get("/api/v1/settings").json()
    assert c["biblioteca"]["nombre"] == "Biblioteca de Prueba"
    assert c["biblioteca"]["codigo_sede"] == "UNA"


def test_codigo_de_sede_obligatorio(client):
    for campo in ("codigo_sede", "nombre", "tipo_item"):
        assert client.put("/api/v1/settings", json={"biblioteca": {campo: ""}}).status_code == 422
        assert client.put("/api/v1/settings", json={"biblioteca": {campo: "  "}}).status_code == 422
    assert client.get("/api/v1/settings").json()["biblioteca"]["codigo_sede"] == "BIB"


def test_respaldo_solo_edita_carpeta_y_pg_dump(client, db):
    from app.services import configuracion
    configuracion.guardar(db, {"respaldo": {"ultimo_ok": "2026-10-01T10:00:00"}}, anotar=False)

    r = client.put("/api/v1/settings", json={"respaldo": {
        "carpeta": "E:/Respaldos", "pg_dump": "C:/pg/bin/pg_dump.exe",
        "ultimo_ok": "2020-01-01T00:00:00", "ultimo": {"ok": True}}})

    assert r.status_code == 200
    respaldo = r.json()["respaldo"]
    assert respaldo["carpeta"] == "E:/Respaldos"
    assert respaldo["pg_dump"] == "C:/pg/bin/pg_dump.exe"
    assert respaldo["ultimo_ok"] == "2026-10-01T10:00:00"
    assert respaldo["ultimo"] is None

    # Una carpeta vacía borra el valor (vuelve a «sin configurar»).
    r = client.put("/api/v1/settings", json={"respaldo": {"carpeta": ""}})
    assert r.json()["respaldo"]["carpeta"] is None
    assert r.json()["respaldo"]["pg_dump"] == "C:/pg/bin/pg_dump.exe"


def test_ya_no_hay_ajustes_de_circulacion(client):
    c = client.get("/api/v1/settings").json()
    assert not {"circulacion", "calendario", "notificaciones", "institucion"} & set(c)


def test_guardar_registra_diferencias(client, db):
    client.put("/api/v1/settings", json={"biblioteca": {"nombre": "Nueva", "codigo_sede": "NVA"}})
    client.put("/api/v1/settings", json={"biblioteca": {"nombre": "Nueva"}})  # sin cambios

    filas = db.query(models.RegistroAccion).filter_by(modulo="configuracion").all()

    assert len(filas) == 1
    assert filas[0].datos["seccion"] == "biblioteca"
    assert filas[0].datos["cambios"]["codigo_sede"] == ["BIB", "NVA"]
    assert filas[0].datos["cambios"]["nombre"][1] == "Nueva"


def test_informacion_del_sistema_es_del_personal(client, anonimo, datos):
    datos.ejemplar(datos.titulo())
    info = client.get("/api/v1/settings/system-info").json()
    assert info["total_registros"] == 1
    assert info["total_ejemplares"] == 1
    assert anonimo.get("/api/v1/settings/system-info").status_code == 401


def test_codigo_de_sede_y_tipo_de_item_hasta_10_caracteres(client):
    """Koha guarda el código de sede y el tipo de ítem en varchar(10): uno más largo no
    se podría importar allí."""
    for campo in ("codigo_sede", "tipo_item"):
        assert client.put("/api/v1/settings",
                          json={"biblioteca": {campo: "X" * 11}}).status_code == 422
        assert client.put("/api/v1/settings",
                          json={"biblioteca": {campo: "X" * 10}}).status_code == 200


def test_codigo_de_organizacion_opcional_hasta_16_y_sin_cambiar_mayusculas(client):
    r = client.put("/api/v1/settings", json={"biblioteca": {"codigo_organizacion": " VeMaLUZ "}})
    assert r.status_code == 200
    assert r.json()["biblioteca"]["codigo_organizacion"] == "VeMaLUZ"
    assert client.put("/api/v1/settings", json={
        "biblioteca": {"codigo_organizacion": "X" * 17}}).status_code == 422
    # Vacío vuelve a «sin 003».
    r = client.put("/api/v1/settings", json={"biblioteca": {"codigo_organizacion": ""}})
    assert r.status_code == 200
    assert r.json()["biblioteca"]["codigo_organizacion"] == ""


def test_las_claves_anteriores_ya_no_se_aceptan(client):
    r = client.put("/api/v1/settings", json={"biblioteca": {"codigo": "UNA"}})
    assert r.status_code == 422


def _sembrar_claves_anteriores(db):
    """Una instalación anterior guardó la sección con `codigo` y `tipo_item_koha`."""
    from app.core.tiempo import ahora
    db.add(models.Configuracion(clave="biblioteca", actualizado_en=ahora(), valor={
        "nombre": "Biblioteca Central", "codigo": "BCL", "tipo_item_koha": "TES"}))
    db.commit()


def test_lee_las_claves_anteriores_de_una_instalacion_existente(client, db):
    _sembrar_claves_anteriores(db)
    assert client.get("/api/v1/settings").json()["biblioteca"] == {
        "nombre": "Biblioteca Central", "codigo_sede": "BCL", "tipo_item": "TES",
        "codigo_organizacion": ""}


def test_guardar_reemplaza_las_claves_anteriores(client, db):
    _sembrar_claves_anteriores(db)
    r = client.put("/api/v1/settings", json={"biblioteca": {"nombre": "Central"}})
    assert r.status_code == 200
    fila = db.query(models.Configuracion).filter_by(clave="biblioteca").one()
    db.refresh(fila)
    assert fila.valor == {"nombre": "Central", "codigo_sede": "BCL", "tipo_item": "TES"}
    # El cambio de nombre es lo único que queda en el registro de acciones.
    [accion] = db.query(models.RegistroAccion).filter_by(modulo="configuracion").all()
    assert set(accion.datos["cambios"]) == {"nombre"}


def test_una_clave_nueva_manda_sobre_la_anterior(client, db):
    from app.services import configuracion
    from app.core.tiempo import ahora
    db.add(models.Configuracion(clave="biblioteca", actualizado_en=ahora(), valor={
        "codigo": "VIE", "codigo_sede": "NUE"}))
    db.commit()
    assert configuracion.leer(db, "biblioteca")["codigo_sede"] == "NUE"
