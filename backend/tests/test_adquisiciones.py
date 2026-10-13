"""Adquisiciones: proveedores, presupuestos y fondos, pedidos, facturas, recepción y sugerencias."""

from datetime import timedelta

import pytest

from app import models
from app.core.tiempo import ahora, hoy

A = "/api/v1/acquisitions"


@pytest.fixture(autouse=True)
def calendario_abierto(datos):
    datos.sin_dias_cerrados()


def _proveedor(client, **extra):
    r = client.post(f"{A}/suppliers", json={"nombre": "Librería Técnica",
                                            "email": "ventas@example.com", **extra})
    assert r.status_code == 201, r.text
    return r.json()


def _presupuesto(client, total=1000, **extra):
    r = client.post(f"{A}/budgets", json={
        "nombre": "Ejercicio 2026", "fecha_inicio": "2026-01-01", "fecha_fin": "2026-12-31",
        "monto_total": total, **extra})
    assert r.status_code == 201, r.text
    return r.json()


def _fondo(client, presupuesto_id, codigo="CIEN", monto=500):
    r = client.post(f"{A}/budgets/{presupuesto_id}/funds",
                    json={"codigo": codigo, "nombre": f"Fondo {codigo}", "monto_asignado": monto})
    assert r.status_code == 201, r.text
    return r.json()


def _pedido(client, proveedor_id, lineas=None):
    r = client.post(f"{A}/orders", json={"proveedor_id": proveedor_id, "nombre": "Compra marzo",
                                         "lineas": lineas or []})
    assert r.status_code == 201, r.text
    return r.json()


def _factura(client, proveedor_id, numero="F-001", **extra):
    r = client.post(f"{A}/invoices", json={"proveedor_id": proveedor_id, "numero": numero,
                                           "fecha": hoy().isoformat(), **extra})
    assert r.status_code == 201, r.text
    return r.json()


def _fondo_de(client, fondo_id):
    return next(f for f in client.get(f"{A}/funds").json() if f["id"] == fondo_id)


# --- Proveedores ----------------------------------------------------------------------

def test_proveedores(client):
    p = _proveedor(client, rif="J-12345678-9", descuento=10, dias_entrega=15)
    assert (p["activo"], p["rif"], p["descuento"], p["dias_entrega"]) == \
        (True, "J-12345678-9", 10.0, 15)

    editado = client.put(f"{A}/suppliers/{p['id']}", json={"telefono": "0212-5550000",
                                                           "activo": False}).json()
    assert editado["telefono"] == "0212-5550000" and editado["activo"] is False
    assert editado["nombre"] == "Librería Técnica"
    assert client.post(f"{A}/suppliers", json={"nombre": " "}).status_code == 400
    assert client.post(f"{A}/suppliers", json={"nombre": "X", "descuento": 120}).status_code == 422
    fila = client.get(f"{A}/suppliers").json()[0]
    assert fila["pedidos_vivos"] == 0
    # Un proveedor inactivo no recibe pedidos nuevos.
    assert client.post(f"{A}/orders", json={"proveedor_id": p["id"]}).status_code == 400


# --- Presupuestos y fondos ------------------------------------------------------------

def test_presupuesto_y_fondos(client):
    presupuesto = _presupuesto(client, total=1000)
    _fondo(client, presupuesto["id"], "CIEN", 600)

    r = client.post(f"{A}/budgets/{presupuesto['id']}/funds",
                    json={"codigo": "LIT", "nombre": "Literatura", "monto_asignado": 500})
    assert r.status_code == 400 and "400.00 sin asignar" in r.json()["detail"]
    repetido = client.post(f"{A}/budgets/{presupuesto['id']}/funds",
                           json={"codigo": "cien", "nombre": "Otra", "monto_asignado": 10})
    assert repetido.status_code == 400 and "Ya hay un fondo CIEN" in repetido.json()["detail"]

    vista = client.get(f"{A}/budgets/{presupuesto['id']}").json()
    assert (vista["asignado"], vista["sin_asignar"]) == (600.0, 400.0)
    menor = client.put(f"{A}/budgets/{presupuesto['id']}", json={"monto_total": 500})
    assert menor.status_code == 400

    al_reves = client.post(f"{A}/budgets", json={"nombre": "X", "fecha_inicio": "2026-12-31",
                                                 "fecha_fin": "2026-01-01", "monto_total": 1})
    assert al_reves.status_code == 400


def test_presupuesto_bloqueado(client):
    presupuesto = _presupuesto(client)
    fondo = _fondo(client, presupuesto["id"])
    client.put(f"{A}/budgets/{presupuesto['id']}", json={"bloqueado": True})

    assert client.put(f"{A}/funds/{fondo['id']}", json={"monto_asignado": 100}).status_code == 400
    assert client.put(f"{A}/budgets/{presupuesto['id']}", json={"nombre": "Otro"}).status_code == 400
    assert client.put(f"{A}/budgets/{presupuesto['id']}",
                      json={"bloqueado": False}).json()["bloqueado"] is False


def test_lo_comprometido_y_lo_gastado(client, datos):
    p = _proveedor(client, descuento=10)
    fondo = _fondo(client, _presupuesto(client)["id"], monto=500)
    pedido = _pedido(client, p["id"], [
        {"titulo": "Fisiología Vegetal", "cantidad": 3, "precio_unitario": 100,
         "fondo_id": fondo["id"]},
    ])
    linea = pedido["lineas"][0]
    # El descuento habitual del proveedor se aplica: 100 - 10 % = 90 por unidad.
    assert (linea["costo_estimado"], linea["total_estimado"]) == (90.0, 270.0)
    assert _fondo_de(client, fondo["id"])["comprometido"] == 270.0

    client.post(f"{A}/orders/{pedido['id']}/close")
    factura = _factura(client, p["id"], costo_envio=12, fondo_envio_id=fondo["id"])
    r = client.post(f"{A}/invoices/{factura['id']}/receive",
                    json={"linea_id": linea["id"], "cantidad": 2, "costo_unitario": 95})
    assert r.status_code == 200, r.text

    estado = _fondo_de(client, fondo["id"])
    # Pendiente 1 × 90 comprometido; gastado 2 × 95 + 12 de envío.
    assert (estado["comprometido"], estado["gastado"], estado["disponible"]) == \
        (90.0, 202.0, 208.0)


def test_el_fondo_no_se_excede(client, datos):
    p = _proveedor(client)
    fondo = _fondo(client, _presupuesto(client)["id"], monto=100)
    pedido = _pedido(client, p["id"])

    r = client.post(f"{A}/orders/{pedido['id']}/lines", json={
        "titulo": "Caro", "cantidad": 2, "precio_unitario": 60, "fondo_id": fondo["id"]})
    assert r.status_code == 400 and "Bs. 100.00 disponibles" in r.json()["detail"]

    ok = client.post(f"{A}/orders/{pedido['id']}/lines", json={
        "titulo": "Justo", "cantidad": 1, "precio_unitario": 60, "fondo_id": fondo["id"]}).json()
    linea_id = ok["linea_id"]
    # Editar la misma línea cuenta lo que ella ya comprometía.
    assert client.put(f"{A}/orders/{pedido['id']}/lines/{linea_id}",
                      json={"precio_unitario": 100}).status_code == 200
    assert client.put(f"{A}/orders/{pedido['id']}/lines/{linea_id}",
                      json={"cantidad": 2}).status_code == 400

    client.put(f"{A}/funds/{fondo['id']}", json={"activo": False})
    inactivo = client.post(f"{A}/orders/{pedido['id']}/lines", json={
        "titulo": "Otro", "precio_unitario": 1, "fondo_id": fondo["id"]})
    assert inactivo.status_code == 400 and "no está activo" in inactivo.json()["detail"]
    # Un fondo con pedidos no se borra; se desactiva.
    assert client.delete(f"{A}/funds/{fondo['id']}").status_code == 400


# --- Pedidos --------------------------------------------------------------------------

def test_ciclo_del_pedido(client, datos, db):
    p = _proveedor(client)
    pedido = _pedido(client, p["id"])
    assert pedido["estado"] == "Abierta"
    assert client.post(f"{A}/orders/{pedido['id']}/close").status_code == 400  # sin títulos

    existente = datos.titulo(titulo="Fisiología Vegetal", isbn="9781111111111")
    r = client.post(f"{A}/orders/{pedido['id']}/lines",
                    json={"isbn": "978-1-111-11111-1", "titulo": "Fisiología", "cantidad": 2,
                          "precio_unitario": 30})
    assert r.json()["lineas"][0]["biblio_id"] == existente.id  # reutiliza por ISBN
    nuevo = client.post(f"{A}/orders/{pedido['id']}/lines",
                        json={"titulo": "Edafología", "autor": "Rojas, Ana",
                              "precio_unitario": 15.5}).json()
    biblio_nuevo = db.get(models.RegistroBibliografico, nuevo["lineas"][1]["biblio_id"])
    # El registro se crea al pedir, como en Koha: ya se puede reservar.
    assert biblio_nuevo.titulo == "Edafología" and biblio_nuevo.autor == "Rojas, Ana"
    assert nuevo["total"] == 75.5

    cerrado = client.post(f"{A}/orders/{pedido['id']}/close").json()
    assert cerrado["estado"] == "Cerrada" and cerrado["fecha_cierre"]
    assert client.post(f"{A}/orders/{pedido['id']}/lines",
                       json={"titulo": "Tarde"}).status_code == 400
    assert client.post(f"{A}/orders/{pedido['id']}/reopen").json()["estado"] == "Abierta"
    assert client.post(f"{A}/orders/{pedido['id']}/cancel").json()["estado"] == "Cancelada"
    assert client.get(f"{A}/orders/999999").status_code == 404


def test_recibir_en_parciales(client, datos, db):
    sede = db.query(models.Biblioteca).first()
    p = _proveedor(client)
    pedido = _pedido(client, p["id"], [{"titulo": "Edafología", "cantidad": 3,
                                        "precio_unitario": 20}])
    linea = pedido["lineas"][0]
    factura = _factura(client, p["id"])
    # Hay que cerrar (enviar) el pedido antes de recibir.
    sin_cerrar = client.post(f"{A}/invoices/{factura['id']}/receive", json={"linea_id": linea["id"]})
    assert sin_cerrar.status_code == 400
    client.post(f"{A}/orders/{pedido['id']}/close")
    assert [l["id"] for l in client.get(f"{A}/suppliers/{p['id']}/receivable").json()] == \
        [linea["id"]]

    r = client.post(f"{A}/invoices/{factura['id']}/receive",
                    json={"linea_id": linea["id"], "cantidad": 2, "signatura": "631.4 R6"})
    assert r.json()["estado_linea"] == "Parcial" and r.json()["estado_pedido"] == "Cerrada"
    assert [e["codigo_barras"] for e in r.json()["ejemplares"]] == \
        [f"OC{pedido['id']:04d}-L{linea['id']:03d}-01", f"OC{pedido['id']:04d}-L{linea['id']:03d}-02"]
    item = db.query(models.Item).filter_by(codigo_barras=r.json()["ejemplares"][0]["codigo_barras"]).one()
    assert (item.signatura_topografica, float(item.precio_reposicion), item.biblioteca_propia_id) == \
        ("631.4 R6", 20.0, sede.id)

    demasiado = client.post(f"{A}/invoices/{factura['id']}/receive",
                            json={"linea_id": linea["id"], "cantidad": 2})
    assert demasiado.status_code == 400 and "Quedan 1" in demasiado.json()["detail"]
    propios = client.post(f"{A}/invoices/{factura['id']}/receive",
                          json={"linea_id": linea["id"], "codigos_barras": ["MIO-1"]})
    assert propios.json()["estado_pedido"] == "Recibida"
    assert client.get(f"{A}/orders/{pedido['id']}").json()["recibidos"] == 3

    detalle = client.get(f"{A}/invoices/{factura['id']}").json()
    assert (detalle["unidades"], detalle["total"]) == (3, 60.0)
    assert detalle["recepciones"][1]["ejemplares"] == ["MIO-1"]


def test_cancelar_lo_pendiente(client, datos):
    p = _proveedor(client)
    pedido = _pedido(client, p["id"], [{"titulo": "A", "cantidad": 3, "precio_unitario": 10},
                                       {"titulo": "B", "cantidad": 1, "precio_unitario": 10}])
    a, b = pedido["lineas"]
    client.post(f"{A}/orders/{pedido['id']}/close")
    factura = _factura(client, p["id"])
    client.post(f"{A}/invoices/{factura['id']}/receive", json={"linea_id": a["id"], "cantidad": 1})
    # Con algo recibido ya no se cancela el pedido entero.
    assert client.post(f"{A}/orders/{pedido['id']}/cancel").status_code == 400

    r = client.post(f"{A}/orders/{pedido['id']}/lines/{a['id']}/cancel").json()
    linea_a = next(l for l in r["lineas"] if l["id"] == a["id"])
    assert (linea_a["estado"], linea_a["cantidad"], linea_a["pendiente"]) == ("Recibida", 1, 0)
    assert "Se cancelaron 2" in linea_a["notas"]
    final = client.post(f"{A}/orders/{pedido['id']}/lines/{b['id']}/cancel").json()
    assert final["estado"] == "Recibida"


def test_la_recepcion_atiende_las_reservas_del_titulo(client, datos, db):
    datos.lector("R1")
    p = _proveedor(client)
    pedido = _pedido(client, p["id"], [{"titulo": "Novedad", "precio_unitario": 10}])
    biblio_id = pedido["lineas"][0]["biblio_id"]
    reserva = client.post("/api/v1/catalog/reservations",
                          json={"biblio_id": biblio_id, "nro_carnet": "R1"})
    assert reserva.status_code == 201, reserva.text
    client.post(f"{A}/orders/{pedido['id']}/close")

    r = client.post(f"{A}/invoices/{_factura(client, p['id'])['id']}/receive",
                    json={"linea_id": pedido["lineas"][0]["id"]})

    assert r.json()["ejemplares"][0]["accion"] == "espera"
    assert r.json()["ejemplares"][0]["reserva"]["carnet"] == "R1"


def test_deshacer_una_recepcion(client, datos, db):
    p = _proveedor(client)
    pedido = _pedido(client, p["id"], [{"titulo": "A", "cantidad": 2, "precio_unitario": 10}])
    client.post(f"{A}/orders/{pedido['id']}/close")
    factura = _factura(client, p["id"])
    r = client.post(f"{A}/invoices/{factura['id']}/receive",
                    json={"linea_id": pedido["lineas"][0]["id"]}).json()
    assert r["estado_pedido"] == "Recibida"
    assert client.delete(f"{A}/invoices/{factura['id']}").status_code == 400

    deshecho = client.delete(f"{A}/receipts/{r['recepcion_id']}").json()

    assert deshecho["estado"] == "Cerrada" and deshecho["lineas"][0]["pendiente"] == 2
    assert db.query(models.Item).count() == 0
    assert client.delete(f"{A}/invoices/{factura['id']}").status_code == 200


def test_no_se_deshace_lo_que_ya_circulo(client, datos, db):
    datos.lector("L1")
    p = _proveedor(client)
    pedido = _pedido(client, p["id"], [{"titulo": "A", "precio_unitario": 10}])
    client.post(f"{A}/orders/{pedido['id']}/close")
    r = client.post(f"{A}/invoices/{_factura(client, p['id'])['id']}/receive",
                    json={"linea_id": pedido["lineas"][0]["id"], "codigos_barras": ["C-1"]}).json()
    client.post("/api/v1/circulation/checkout", json={"codigo_barras": "C-1", "nro_carnet": "L1"})

    no = client.delete(f"{A}/receipts/{r['recepcion_id']}")
    assert no.status_code == 400 and "C-1" in no.json()["detail"]


def test_facturas(client, datos):
    p = _proveedor(client)
    otro = _proveedor(client, nombre="Otra librería")
    fondo = _fondo(client, _presupuesto(client)["id"])
    factura = _factura(client, p["id"], "F-9")

    assert client.post(f"{A}/invoices", json={"proveedor_id": p["id"],
                                              "numero": "F-9"}).status_code == 400
    assert client.post(f"{A}/invoices", json={"proveedor_id": otro["id"],
                                              "numero": "F-9"}).status_code == 201
    sin_fondo = client.put(f"{A}/invoices/{factura['id']}", json={"costo_envio": 5})
    assert sin_fondo.status_code == 400 and "fondo" in sin_fondo.json()["detail"]
    con_fondo = client.put(f"{A}/invoices/{factura['id']}",
                           json={"costo_envio": 5, "fondo_envio_id": fondo["id"]}).json()
    assert con_fondo["total"] == 5.0 and con_fondo["fondo_envio"] == "CIEN"

    cerrada = client.post(f"{A}/invoices/{factura['id']}/close").json()
    assert cerrada["cerrada"] is True
    assert client.put(f"{A}/invoices/{factura['id']}", json={"notas": "x"}).status_code == 400
    assert [f["numero"] for f in client.get(f"{A}/invoices?abiertas=true").json()] == ["F-9"]
    assert client.post(f"{A}/invoices/{factura['id']}/reopen").json()["cerrada"] is False

    # No se recibe en una factura de otro proveedor.
    pedido = _pedido(client, p["id"], [{"titulo": "A", "precio_unitario": 1}])
    client.post(f"{A}/orders/{pedido['id']}/close")
    ajena = client.get(f"{A}/invoices?proveedor_id={otro['id']}").json()[0]
    r = client.post(f"{A}/invoices/{ajena['id']}/receive",
                    json={"linea_id": pedido["lineas"][0]["id"]})
    assert r.status_code == 400 and "otro proveedor" in r.json()["detail"]


def test_pedidos_atrasados(client, datos, db):
    p = _proveedor(client, dias_entrega=10)
    pedido = _pedido(client, p["id"], [{"titulo": "A", "precio_unitario": 1}])
    client.post(f"{A}/orders/{pedido['id']}/close")
    assert client.get(f"{A}/orders/late").json() == []

    db.get(models.OrdenCompra, pedido["id"]).fecha_cierre = ahora() - timedelta(days=13)
    db.flush()

    atrasados = client.get(f"{A}/orders/late").json()
    assert [(a["orden_id"], a["dias_atraso"]) for a in atrasados] == [(pedido["id"], 3)]
    assert client.get(f"{A}/summary").json()["pedidos_atrasados"] == 1


# --- Sugerencias ----------------------------------------------------------------------

def test_sugerencias(client, datos):
    datos.lector("S1")
    p = _proveedor(client)
    pedido = _pedido(client, p["id"])

    s = client.post(f"{A}/suggestions", json={"titulo": "Agroecología", "autor": "Altieri",
                                              "nro_carnet": "S1", "nota": "Para tesis"}).json()
    assert (s["estado"], s["carnet"]) == ("Pendiente", "S1")
    otra = client.post(f"{A}/suggestions", json={"titulo": "Sin motivo"}).json()
    assert otra["carnet"] == "ADMIN"  # a nombre de quien la registra
    sin_motivo = client.post(f"{A}/suggestions/{otra['id']}/reject", json={})
    assert sin_motivo.status_code == 400
    rechazada = client.post(f"{A}/suggestions/{otra['id']}/reject",
                            json={"motivo": "Fuera de la colección"}).json()
    assert rechazada["estado"] == "Rechazada"

    aceptada = client.post(f"{A}/suggestions/{s['id']}/accept", json={}).json()
    assert aceptada["estado"] == "Aceptada" and aceptada["gestionada_por"]
    pedida = client.post(f"{A}/suggestions/{s['id']}/order",
                         json={"orden_id": pedido["id"], "cantidad": 2,
                               "precio_unitario": 25}).json()
    assert pedida["estado"] == "Pedida" and pedida["orden_id"] == pedido["id"]
    linea = client.get(f"{A}/orders/{pedido['id']}").json()["lineas"][0]
    assert (linea["titulo"], linea["cantidad"]) == ("Agroecología", 2)
    assert "Sugerencia" in linea["notas"]
    assert [x["titulo"] for x in client.get(f"{A}/suggestions?estado=Pendiente,Aceptada").json()] == []

    # Quitar la línea devuelve la sugerencia a Aceptada.
    client.delete(f"{A}/orders/{pedido['id']}/lines/{linea['id']}")
    assert client.get(f"{A}/suggestions?estado=Aceptada").json()[0]["id"] == s["id"]


def test_resumen(client, datos):
    p = _proveedor(client)
    _fondo(client, _presupuesto(client)["id"])
    _pedido(client, p["id"])
    client.post(f"{A}/suggestions", json={"titulo": "X"})

    r = client.get(f"{A}/summary").json()

    assert (r["pedidos_abiertos"], r["sugerencias_pendientes"]) == (1, 1)
    assert [f["codigo"] for f in r["fondos"]] == ["CIEN"]
