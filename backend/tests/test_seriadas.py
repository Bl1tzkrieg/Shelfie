"""Seriadas: patrón de predicción, recepción que da de alta ejemplares, faltantes y reclamos."""

from datetime import date, timedelta

import pytest

from app import models
from app.core.tiempo import hoy
from app.services import seriadas

SER = "/api/v1/serials"


@pytest.fixture(autouse=True)
def calendario_abierto(datos):
    datos.sin_dias_cerrados()


def _suscripcion(client, **extra):
    cuerpo = {"titulo": "Revista Agronómica", "issn": "1234-5678", "frecuencia_unidad": "mes",
              "frecuencia_cada": 3, "numeracion": "Vol. {X}, Núm. {Y}", "numeros_por_volumen": 4,
              "volumen_inicial": 12, "numero_inicial": 3, "primer_fasciculo": "2026-01-15",
              "fecha_inicio": "2026-01-01", **extra}
    r = client.post(f"{SER}/subscriptions", json=cuerpo)
    assert r.status_code == 201, r.text
    return r.json()


def _esperado(sus):
    return next(f for f in sus["fasciculos"] if f["estado"] in ("Esperado", "Reclamado"))


# --- Patrón ---------------------------------------------------------------------------

def test_prediccion_con_cambio_de_volumen():
    p = seriadas.predecir("mes", 3, "Vol. {X}, Núm. {Y} ({MES} {ANO})", 4, 12, 3,
                          date(2026, 1, 31), cantidad=4)
    assert [x["numero"] for x in p] == [
        "Vol. 12, Núm. 3 (enero 2026)", "Vol. 12, Núm. 4 (abril 2026)",
        "Vol. 13, Núm. 1 (julio 2026)", "Vol. 13, Núm. 2 (octubre 2026)"]
    # Fin de mes: el 31 de enero + 3 meses es el 30 de abril.
    assert [x["fecha_esperada"] for x in p][:2] == ["2026-01-31", "2026-04-30"]


@pytest.mark.parametrize("unidad,cada,esperado", [
    ("dia", 1, date(2026, 3, 2)), ("semana", 2, date(2026, 3, 15)),
    ("anio", 1, date(2027, 3, 1)), ("mes", 12, date(2027, 3, 1)),
])
def test_frecuencias(unidad, cada, esperado):
    assert seriadas.sumar(date(2026, 3, 1), unidad, cada) == esperado


def test_vista_previa_y_patrones_invalidos(client):
    r = client.post(f"{SER}/prediction", json={"frecuencia_unidad": "semana", "numeracion": "Núm. {Y}",
                                               "primer_fasciculo": "2026-01-05", "cantidad": 3})
    assert [x["numero"] for x in r.json()] == ["Núm. 1", "Núm. 2", "Núm. 3"]

    for patron, texto in [
        ({"numeracion": "Tomo {T}"}, "desconocidos: T"),
        ({"numeracion": "Sin marcadores"}, "al menos un marcador"),
        ({"numeracion": "Vol. {X}", "numeros_por_volumen": None}, "cuántos números"),
        ({"frecuencia_unidad": "lustro"}, "Frecuencia desconocida"),
    ]:
        r = client.post(f"{SER}/prediction", json={"primer_fasciculo": "2026-01-05", **patron})
        assert r.status_code == 400 and texto in r.json()["detail"], (patron, r.text)


# --- Suscripción ----------------------------------------------------------------------

def test_crear_suscripcion_crea_el_registro_y_el_primer_numero(client, datos, db):
    sus = _suscripcion(client)

    biblio = db.get(models.RegistroBibliografico, sus["biblio_id"])
    assert biblio.plantilla == "SER" and biblio.titulo == "Revista Agronómica"
    etiquetas = [next(iter(c)) for c in biblio.marc_json["fields"]]
    assert "022" in etiquetas and "310" in etiquetas
    assert sus["periodicidad"] == "Trimestral"
    assert [(f["numero"], f["fecha_esperada"], f["estado"]) for f in sus["fasciculos"]] == \
        [("Vol. 12, Núm. 3", "2026-01-15", "Esperado")]

    # Con un registro existente no se crea otro.
    existente = datos.titulo("Boletín", isbn=None)
    otra = _suscripcion(client, biblio_id=existente.id, titulo=None)
    assert otra["biblio_id"] == existente.id and otra["titulo"] == "Boletín"


def test_recibir_da_de_alta_el_ejemplar_y_predice_el_siguiente(client, datos, db):
    datos.tipo_item("REV", "Revista")
    sus = _suscripcion(client)
    primero = _esperado(sus)

    r = client.post(f"{SER}/issues/{primero['id']}/receive", json={})

    assert r.status_code == 200, r.text
    estados = [(f["numero"], f["estado"]) for f in r.json()["fasciculos"]]
    assert estados == [("Vol. 12, Núm. 4", "Esperado"), ("Vol. 12, Núm. 3", "Recibido")]
    codigo = r.json()["recibido"]["codigo_barras"]
    assert codigo == f"SER{sus['id']:04d}-{primero['id']:05d}"
    item = db.query(models.Item).filter_by(codigo_barras=codigo).one()
    assert (item.biblio_id, item.enumeracion, item.estado) == \
        (sus["biblio_id"], "Vol. 12, Núm. 3", "Disponible")
    assert db.get(models.TipoItem, item.tipo_item_id).codigo == "REV"
    assert client.post(f"{SER}/issues/{primero['id']}/receive", json={}).status_code == 400

    # El siguiente cambia de volumen.
    segundo = _esperado(r.json())
    tercero = client.post(f"{SER}/issues/{segundo['id']}/receive",
                          json={"crear_ejemplar": False}).json()
    assert _esperado(tercero)["numero"] == "Vol. 13, Núm. 1"
    assert db.query(models.Item).count() == 1


def test_codigo_propio_y_reservas_de_la_revista(client, datos, db):
    sus = _suscripcion(client)
    datos.lector("R1")
    assert client.post("/api/v1/catalog/reservations",
                       json={"biblio_id": sus["biblio_id"], "nro_carnet": "R1"}).status_code == 201

    r = client.post(f"{SER}/issues/{_esperado(sus)['id']}/receive",
                    json={"codigo_barras": "REV-001"}).json()

    assert r["destino"]["accion"] == "espera" and r["destino"]["reserva"]["carnet"] == "R1"
    assert db.query(models.Item).filter_by(codigo_barras="REV-001").one().estado == "Reservado"


def test_faltante_tambien_predice_el_siguiente(client, datos):
    sus = _suscripcion(client)
    r = client.post(f"{SER}/issues/{_esperado(sus)['id']}/missing", json={"notas": "Agotado"}).json()

    assert [(f["numero"], f["estado"]) for f in r["fasciculos"]] == \
        [("Vol. 12, Núm. 4", "Esperado"), ("Vol. 12, Núm. 3", "Faltante")]
    assert r["fasciculos"][1]["notas"] == "Agotado"


def test_la_prediccion_respeta_la_fecha_de_fin(client, datos):
    sus = _suscripcion(client, fecha_fin="2026-03-31")
    r = client.post(f"{SER}/issues/{_esperado(sus)['id']}/receive",
                    json={"crear_ejemplar": False}).json()
    # El siguiente saldría el 15 de abril: fuera de la suscripción.
    assert r["proximo"] is None and r["por_vencer"] is True

    renovada = client.post(f"{SER}/subscriptions/{sus['id']}/renew",
                           json={"fecha_fin": "2026-12-31"}).json()
    assert renovada["proximo"]["numero"] == "Vol. 12, Núm. 4"


def test_atrasos_y_reclamos(client, datos):
    p = client.post("/api/v1/acquisitions/suppliers",
                    json={"nombre": "Suscripciones Andinas", "email": "s@example.com"}).json()
    hace_20 = (hoy() - timedelta(days=20)).isoformat()
    sus = _suscripcion(client, proveedor_id=p["id"], primer_fasciculo=hace_20, dias_gracia=15)
    _suscripcion(client, titulo="Al día", primer_fasciculo=hoy().isoformat())

    late = client.get(f"{SER}/issues/late").json()
    assert [(x["titulo"], x["dias_atraso"], x["proveedor_email"]) for x in late] == \
        [("Revista Agronómica", 5, "s@example.com")]
    assert client.get(f"{SER}/subscriptions").json()[1]["fasciculos_atrasados"] == 1

    reclamado = client.post(f"{SER}/issues/{late[0]['id']}/claim").json()
    f = _esperado(reclamado)
    assert (f["estado"], f["reclamos"]) == ("Reclamado", 1)
    client.post(f"{SER}/issues/{late[0]['id']}/claim")
    assert client.get(f"{SER}/issues/late").json()[0]["reclamos"] == 2
    # Llega después del reclamo.
    assert client.post(f"{SER}/issues/{late[0]['id']}/receive",
                       json={"crear_ejemplar": False}).status_code == 200
    assert client.get(f"{SER}/issues/late").json() == []


def test_numero_especial_y_suscripcion_irregular(client, datos):
    sus = _suscripcion(client, frecuencia_unidad="irregular", numeracion="")
    assert sus["fasciculos"] == [] and sus["periodicidad"] == "Irregular"

    base = f"{SER}/subscriptions/{sus['id']}/issues"
    especial = client.post(base, json={"numero": "Número especial 50 años"})
    assert especial.status_code == 201
    assert client.post(base, json={"numero": "Número especial 50 años"}).status_code == 400
    r = client.post(f"{SER}/issues/{especial.json()['id']}/receive", json={"crear_ejemplar": False})
    # Irregular: nada que predecir.
    assert r.json()["proximo"] is None


def test_cancelar_y_editar(client, datos):
    sus = _suscripcion(client)
    editada = client.put(f"{SER}/subscriptions/{sus['id']}",
                         json={"dias_gracia": 30, "notas": "Canje con la UCV"}).json()
    assert (editada["dias_gracia"], editada["notas"]) == (30, "Canje con la UCV")
    mal = client.put(f"{SER}/subscriptions/{sus['id']}", json={"numeracion": "Sin nada"})
    assert mal.status_code == 400

    cancelada = client.post(f"{SER}/subscriptions/{sus['id']}/cancel").json()
    assert cancelada["estado"] == "Cancelada"
    assert [f["estado"] for f in cancelada["fasciculos"]] == ["Faltante"]
    assert client.get(f"{SER}/subscriptions?estado=Activa").json() == []
    assert client.get(f"{SER}/subscriptions/999999").status_code == 404
    assert client.post(f"{SER}/subscriptions", json={"titulo": "X", "proveedor_id": 999999}
                       ).status_code == 404


def test_lo_esperado_para_recibir(client, datos):
    _suscripcion(client)
    _suscripcion(client, titulo="Otra", primer_fasciculo="2026-01-01")

    esperados = client.get(f"{SER}/issues/expected").json()

    assert [x["titulo"] for x in esperados] == ["Otra", "Revista Agronómica"]
    assert client.get(f"{SER}/issues/pending").json() == esperados


def test_proveedores_para_seriadas(como):
    admin = como(["superbibliotecario"], carnet="A-1")
    admin.post("/api/v1/acquisitions/suppliers", json={"nombre": "Activo"})
    inactivo = admin.post("/api/v1/acquisitions/suppliers", json={"nombre": "Inactivo"}).json()
    admin.put(f"/api/v1/acquisitions/suppliers/{inactivo['id']}", json={"activo": False})

    solo_seriadas = como(["seriadas"], carnet="S-1")
    assert [p["nombre"] for p in solo_seriadas.get(f"{SER}/suppliers").json()] == ["Activo"]
