"""Configuración lite: nombre y código de la biblioteca, tipo de ítem de Koha y respaldo."""

from app import models


def test_configuracion_por_defecto(client):
    c = client.get("/api/v1/settings").json()
    assert set(c) == {"biblioteca", "respaldo"}
    assert c["biblioteca"]["codigo"] == "BIB"
    assert c["biblioteca"]["tipo_item_koha"] == "LIB"
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
    assert r.json()["biblioteca"]["codigo"] == "BIB"


def test_solo_el_administrador_guarda(como, anonimo):
    cuerpo = {"biblioteca": {"nombre": "X"}}
    assert como(["catalogo"]).put("/api/v1/settings", json=cuerpo).status_code == 403
    assert anonimo.put("/api/v1/settings", json=cuerpo).status_code == 401


def test_guardar_mezcla_secciones(client):
    r = client.put("/api/v1/settings", json={"biblioteca": {"nombre": "Biblioteca de Prueba"}})

    assert r.status_code == 200
    assert r.json()["biblioteca"]["nombre"] == "Biblioteca de Prueba"
    assert r.json()["biblioteca"]["codigo"] == "BIB"  # el resto conserva sus valores

    client.put("/api/v1/settings", json={"biblioteca": {"codigo": "UNA"}})
    c = client.get("/api/v1/settings").json()
    assert c["biblioteca"]["nombre"] == "Biblioteca de Prueba"
    assert c["biblioteca"]["codigo"] == "UNA"


def test_codigo_biblioteca_obligatorio(client):
    for campo in ("codigo", "nombre", "tipo_item_koha"):
        assert client.put("/api/v1/settings", json={"biblioteca": {campo: ""}}).status_code == 422
        assert client.put("/api/v1/settings", json={"biblioteca": {campo: "  "}}).status_code == 422
    assert client.get("/api/v1/settings").json()["biblioteca"]["codigo"] == "BIB"


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
    client.put("/api/v1/settings", json={"biblioteca": {"nombre": "Nueva", "codigo": "NVA"}})
    client.put("/api/v1/settings", json={"biblioteca": {"nombre": "Nueva"}})  # sin cambios

    filas = db.query(models.RegistroAccion).filter_by(modulo="configuracion").all()

    assert len(filas) == 1
    assert filas[0].datos["seccion"] == "biblioteca"
    assert filas[0].datos["cambios"]["codigo"] == ["BIB", "NVA"]
    assert filas[0].datos["cambios"]["nombre"][1] == "Nueva"


def test_informacion_del_sistema_es_del_personal(client, anonimo, datos):
    datos.ejemplar(datos.titulo())
    info = client.get("/api/v1/settings/system-info").json()
    assert info["total_registros"] == 1
    assert info["total_ejemplares"] == 1
    assert anonimo.get("/api/v1/settings/system-info").status_code == 401
