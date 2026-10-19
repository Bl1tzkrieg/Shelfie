"""Hallazgos de severidad baja de la auditoría de octubre de 2026 (uno o dos tests por hallazgo)."""

from datetime import timedelta

from app import models
from app.core.tiempo import hoy

CAT = "/api/v1/catalog"
HOLDS = "/api/v1/circulation/holds"


def _reserva_pendiente(client, datos, carnet="L-1"):
    libro = datos.titulo()
    datos.ejemplar(libro, estado="Prestado")
    datos.lector(carnet)
    r = client.post(f"{CAT}/reservations", json={"biblio_id": libro.id, "nro_carnet": carnet})
    assert r.status_code == 201, r.text
    return libro, r.json()["reserva_id"]


def test_b5_la_fecha_de_reanudacion_sola_suspende(client, datos, db):
    _libro, reserva_id = _reserva_pendiente(client, datos)
    manana = (hoy() + timedelta(days=5)).isoformat()

    r = client.patch(f"{HOLDS}/{reserva_id}", json={"suspendida_hasta": manana})

    assert r.status_code == 200, r.text
    reserva = db.get(models.Reserva, reserva_id)
    assert reserva.suspendida is True and reserva.suspendida_hasta.isoformat() == manana


# --- Catálogo y MARC ------------------------------------------------------------------

def test_b7_anio_fuera_de_rango(client):
    for ano in (10000, -5):
        r = client.post(f"{CAT}/items", json={"titulo": "X", "codigo_barras": f"A{ano}",
                                               "ano_publicacion": ano})
        assert r.status_code == 422, r.text


def test_b8_marc_json_con_tipos_incorrectos(client):
    for marc in ({"leader": "", "fields": 5}, {"leader": "", "fields": [{"245": {"subfields": True}}]}):
        r = client.post(f"{CAT}/records", json={"plantilla": "BKS", "marc": marc})
        assert r.status_code == 422, r.text


def test_b12_plantilla_desconocida(client):
    r = client.post(f"{CAT}/records", json={"plantilla": "TESIS", "marc": {"leader": "", "fields": []}})
    assert r.status_code == 422


def test_b11_isbn_duplicado_con_otro_formato(client, datos):
    from tests.test_marc import _campo, _registro
    datos.titulo(isbn="9780307474728")
    marc = _registro(_campo("020", ("a", "978-0-307-47472-8")), _campo("245", ("a", "Otra edición")))
    r = client.post(f"{CAT}/records", json={"plantilla": "BKS", "marc": marc})
    assert r.status_code == 400 and "ya está en" in r.json()["detail"]


def test_b16_isbn_sin_digitos_no_trae_todo(client, datos):
    datos.titulo()
    r = client.get("/api/v1/opac/advanced-search", params={"isbn": "abc"})
    assert r.status_code == 200 and r.json()["total"] == 0


def test_b18_isbn_con_calificador_pegado():
    from app.services.marc import normalizar_isbn
    assert normalizar_isbn("9780307474728(pbk.)") == "9780307474728"
    assert normalizar_isbn("978-0-307-47472-8 (rústica)") == "978-0-307-47472-8"
    assert normalizar_isbn("84-376-0494-X : 15 €") == "84-376-0494-X"


def test_b10_isbn_repetido_en_el_archivo_igual_en_vista_y_al_aplicar(client, db):
    from tests.test_intercambio_marc import _importar, _libro, _mrc
    archivo = _mrc(_libro("Primero", "9789800000123"), _libro("Segundo", "9789800000123"))
    vista = _importar(client, archivo, modo="vista", duplicados="reemplazar").json()
    hecho = _importar(client, archivo, duplicados="reemplazar").json()
    assert [r["accion"] for r in vista["registros"]] == [r["accion"] for r in hecho["registros"]] \
        == ["nuevo", "omitir"]
    assert db.query(models.RegistroBibliografico).one().titulo == "Primero"


def test_b13_b14_b17_mapeo_del_952_y_campos_ajenos(client, datos, db):
    import pymarc
    from tests.test_intercambio_marc import _importar, _libro
    r = _libro("Con 952 raro", ejemplares=[
        [("p", " R-1 "), ("a", "XYZ"), ("0", "1")],
        [("p", "R-2"), ("7", "1"), ("4", "1")],
        [("p", "R-3"), ("o", "x" * 120)],
    ])
    r.add_field(pymarc.Field(tag="FMT", data="BK"))
    vista = _importar(client, r.as_marc(), modo="vista").json()["registros"][0]
    texto = " | ".join(vista["mensajes"])
    assert vista["accion"] == "nuevo", vista
    assert "no son MARC: FMT" in texto and "Sede «XYZ» desconocida" in texto
    assert "no prestable ($7)" in texto and "dañado ($4)" in texto
    assert "signatura ($o) supera los 100" in texto and vista["ejemplares"] == 2

    _importar(client, r.as_marc())
    retirado = db.query(models.Item).filter_by(codigo_barras="R-1").one()
    assert retirado.estado == "Retirado"


def test_b19_importacion_demasiado_grande_se_rechaza_antes_de_leerla(client):
    r = client.post(f"{CAT}/import", params={"modo": "vista"}, content=b"x",
                    headers={"Content-Type": "application/octet-stream",
                             "Content-Length": str(30 * 1024 * 1024)})
    assert r.status_code == 400 and "20 MB" in r.json()["detail"]


def test_b20_no_se_borra_un_registro_con_pedido_o_suscripcion(client, datos):
    A = "/api/v1/acquisitions"
    proveedor = client.post(f"{A}/suppliers", json={"nombre": "P"}).json()
    pedido_de = datos.titulo("Pedido", None)
    client.post(f"{A}/orders", json={"proveedor_id": proveedor["id"], "lineas": [
        {"biblio_id": pedido_de.id, "precio_unitario": 1}]})
    r = client.delete(f"{CAT}/items/{pedido_de.id}")
    assert r.status_code == 400 and "pedido" in r.json()["detail"]

    suscrita = client.post("/api/v1/serials/subscriptions", json={
        "titulo": "Revista", "numeracion": "Núm. {Y}", "primer_fasciculo": "2026-01-01"}).json()
    r = client.delete(f"{CAT}/items/{suscrita['biblio_id']}")
    assert r.status_code == 400 and "suscripción" in r.json()["detail"]


# --- Adquisiciones y seriadas ---------------------------------------------------------

SER = "/api/v1/serials"
ADQ = "/api/v1/acquisitions"


def test_b27_mensual_del_31_no_deriva_al_28(client):
    r = client.post(f"{SER}/prediction", json={"frecuencia_unidad": "mes", "numeracion": "Núm. {Y}",
                                               "primer_fasciculo": "2026-01-31", "cantidad": 4})
    assert [x["fecha_esperada"] for x in r.json()] == [
        "2026-01-31", "2026-02-28", "2026-03-31", "2026-04-30"]


def test_b28_numero_inicial_cero_se_respeta(client, db):
    sus = client.post(f"{SER}/subscriptions", json={
        "titulo": "Revista", "numeracion": "Vol. {X}, Núm. {Y}", "numeros_por_volumen": 4,
        "volumen_inicial": 0, "numero_inicial": 0, "primer_fasciculo": "2026-01-01"}).json()
    assert sus["fasciculos"][0]["numero"] == "Vol. 0, Núm. 0"


def test_b25_null_explicito_no_da_500(client):
    presupuesto = client.post(f"{ADQ}/budgets", json={
        "nombre": "B", "fecha_inicio": "2026-01-01", "fecha_fin": "2026-12-31",
        "monto_total": 100, "activo": None})
    assert presupuesto.status_code == 201 and presupuesto.json()["activo"] is True
    proveedor = client.post(f"{ADQ}/suppliers", json={"nombre": "P"}).json()
    factura = client.post(f"{ADQ}/invoices", json={"proveedor_id": proveedor["id"], "numero": None})
    assert factura.status_code == 400  # «La factura necesita un número», no un 500
    sus = client.post(f"{SER}/subscriptions", json={
        "titulo": "R", "numeracion": "Núm. {Y}", "primer_fasciculo": "2026-01-01"}).json()
    r = client.put(f"{SER}/subscriptions/{sus['id']}", json={
        "frecuencia_cada": None, "dias_gracia": None, "crear_ejemplares": None})
    assert r.status_code == 200, r.text


def test_b21_cancelar_el_pedido_devuelve_la_sugerencia(client, db):
    proveedor = client.post(f"{ADQ}/suppliers", json={"nombre": "P"}).json()
    sugerencia = client.post(f"{ADQ}/suggestions", json={"titulo": "Pedido por un lector"}).json()
    client.post(f"{ADQ}/suggestions/{sugerencia['id']}/accept", json={})
    pedido = client.post(f"{ADQ}/orders", json={"proveedor_id": proveedor["id"]}).json()
    pedida = client.post(f"{ADQ}/suggestions/{sugerencia['id']}/order",
                         json={"orden_id": pedido["id"], "precio_unitario": 1})
    assert pedida.status_code in (200, 201), pedida.text
    assert db.get(models.Sugerencia, sugerencia["id"]).estado == "Pedida"

    assert client.post(f"{ADQ}/orders/{pedido['id']}/cancel").status_code == 200
    db.expire_all()
    assert db.get(models.Sugerencia, sugerencia["id"]).estado == "Aceptada"


def test_b22_b24_saldo_del_fondo_en_envio_y_presupuesto_bloqueado(client):
    proveedor = client.post(f"{ADQ}/suppliers", json={"nombre": "P"}).json()
    presupuesto = client.post(f"{ADQ}/budgets", json={
        "nombre": "B", "fecha_inicio": "2026-01-01", "fecha_fin": "2026-12-31",
        "monto_total": 100}).json()
    fondo = client.post(f"{ADQ}/budgets/{presupuesto['id']}/funds", json={
        "codigo": "F", "nombre": "F", "monto_asignado": 10}).json()
    r = client.post(f"{ADQ}/invoices", json={"proveedor_id": proveedor["id"], "numero": "1",
                                             "costo_envio": 50, "fondo_envio_id": fondo["id"]})
    assert r.status_code == 400 and "envío cuesta" in r.json()["detail"]

    client.put(f"{ADQ}/budgets/{presupuesto['id']}", json={"bloqueado": True})
    r = client.post(f"{ADQ}/orders", json={"proveedor_id": proveedor["id"], "lineas": [
        {"titulo": "X", "precio_unitario": 1, "fondo_id": fondo["id"]}]})
    assert r.status_code == 400 and "bloqueado" in r.json()["detail"]


# --- Usuarios, autenticación y reportes -----------------------------------------------

def test_b34_salir_anula_el_token_aunque_se_haya_copiado(anonimo, datos):
    from fastapi.testclient import TestClient

    from app.main import app
    from tests.conftest import iniciar_sesion
    datos.personal("P-9", ["circulacion"])
    sesion = iniciar_sesion(TestClient(app), "P-9", "P-9")
    copiada = TestClient(app)
    copiada.cookies.set("shelfie_sesion", sesion.cookies.get("shelfie_sesion"))

    assert sesion.post("/api/v1/auth/logout").status_code == 204
    r = copiada.get("/api/v1/auth/me")
    assert r.status_code == 401 and "se cerró" in r.json()["detail"]
    sesion.close()
    copiada.close()


def test_b35_referer_ajeno_sin_origin_se_rechaza(client):
    r = client.post(f"{CAT}/items", json={"titulo": "X", "codigo_barras": "REF-1"},
                    headers={"Referer": "https://malicioso.example/pagina"})
    assert r.status_code == 403
    r = client.post(f"{CAT}/items", json={"titulo": "X", "codigo_barras": "REF-1"},
                    headers={"Referer": "http://localhost:3000/catalogo"})
    assert r.status_code == 201


def test_b32_csv_sin_formulas(client, datos):
    datos.lector("F-1", nombre='=HYPERLINK("http://x")')
    r = client.get("/api/v1/users-export")
    assert r.status_code == 200
    assert "'=HYPERLINK" in r.text and ",=HYPERLINK" not in r.text


def test_b32_celda_segura_respeta_numeros():
    from app.core.csv import celda_segura
    assert celda_segura("-12.50") == "-12.50"
    assert celda_segura("+58 212") == "'+58 212"
    assert celda_segura("@SUMA") == "'@SUMA"
    assert celda_segura(5) == 5


def test_b29_reportes_disponibles_cuentan_bien(client, datos):
    lector = datos.lector("L-1")
    datos.prestamo(datos.ejemplar(datos.titulo(), "A"), lector, dias_desde=10, dias_hasta=7)
    datos.prestamo(datos.ejemplar(datos.titulo("Otro", None), "B"), lector, devuelto=True)
    filas = {r["id"]: r["rows"] for r in client.get("/api/v1/reports/available").json()}
    for rid in filas:
        generado = client.get("/api/v1/reports/generate",
                              params={"tipo": rid, "formato": "json", "periodo": "all"}).json()
        assert filas[rid] == len(generado["filas"]), rid


# --- Infraestructura ------------------------------------------------------------------

def test_b42_violacion_de_unicidad_da_409():
    """Una restricción que se cuela hasta la base responde 409 con un mensaje, no 500."""
    import json

    from sqlalchemy.exc import IntegrityError

    from app.main import manejar_conflicto
    r = manejar_conflicto(None, IntegrityError("INSERT ...", {}, Exception("duplicate key")))
    assert r.status_code == 409 and "Otro registro" in json.loads(r.body)["detail"]


def test_b42_el_motor_verifica_las_conexiones():
    from app.database import engine
    assert engine.pool._pre_ping is True


def test_b55_el_csv_exportado_se_reimporta_y_un_email_malo_omite_solo_su_fila(client, datos, db):
    filas = [
        {"nro_carnet": "I-1", "nombre": "Ana", "apellido": "Uno", "email": "a@x.com",
         "categoria": "Docente"},
        {"nro_carnet": "I-2", "nombre": "Beto", "apellido": "Dos", "email": "no-es-email"},
        {"nro_carnet": "I-3", "nombre": "Ceci", "apellido": "Tres", "email": "c@x.com",
         "categoria": "Inventada"},
    ]
    r = client.post("/api/v1/users-import", json=filas)
    assert r.status_code == 200, r.text
    cuerpo = r.json()
    assert cuerpo["creados"] == 1
    assert [(o["fila"], o["carnet"]) for o in cuerpo["omitidos"]] == [(2, "I-2"), (3, "I-3")]
    assert "email" in cuerpo["omitidos"][0]["motivo"]
    ana = db.query(models.Usuario).filter_by(nro_carnet="I-1").one()
    assert db.get(models.CategoriaUsuario, ana.categoria_id).codigo == "DOC"
