"""Préstamo, devolución, renovación y pérdida sobre reglas, calendario y cuentas."""

from datetime import timedelta
from decimal import Decimal

import pytest

from app import models
from app.core.tiempo import ahora, fecha_local, fin_del_dia, hoy
from app.services import cuentas


def _checkout(client, barcode="B-001", carnet="1001"):
    return client.post("/api/v1/circulation/checkout",
                       json={"codigo_barras": barcode, "nro_carnet": carnet})


def _checkin(client, barcode="B-001"):
    return client.post("/api/v1/circulation/checkin", json={"codigo_barras": barcode})


@pytest.fixture(autouse=True)
def calendario_abierto(datos):
    """Sin días cerrados salvo que el test los configure: las cuentas de días son exactas."""
    datos.sin_dias_cerrados()


# --- Préstamo -------------------------------------------------------------------

def test_checkout_vence_a_fin_del_dia_segun_la_regla_de_la_categoria(client, datos, db):
    datos.lector()
    item = datos.ejemplar(datos.titulo())

    r = _checkout(client)

    assert r.status_code == 200, r.text
    db.refresh(item)
    assert item.estado == "Prestado"
    prestamo = db.get(models.Prestamo, r.json()["id"])
    assert prestamo.fecha_vencimiento == fin_del_dia(hoy() + timedelta(days=7))


def test_docente_tiene_su_propia_regla(client, datos, db):
    datos.lector("2001", categoria=datos.doc)
    datos.ejemplar(datos.titulo())
    prestamo = db.get(models.Prestamo, _checkout(client, carnet="2001").json()["id"])
    assert fecha_local(prestamo.fecha_vencimiento) == hoy() + timedelta(days=30)


def test_vencimiento_en_dia_cerrado_se_corre_al_siguiente_habil(client, datos, db):
    cerrado = (hoy() + timedelta(days=7)).weekday()
    client.put("/api/v1/calendar/closed-days", json={"dias": [cerrado]})
    datos.lector()
    datos.ejemplar(datos.titulo())

    prestamo = db.get(models.Prestamo, _checkout(client).json()["id"])

    assert fecha_local(prestamo.fecha_vencimiento) == hoy() + timedelta(days=8)


def test_vencimiento_salta_feriados(client, datos, db):
    for dias in (7, 8):
        client.post("/api/v1/calendar/holidays",
                    json={"fecha": str(hoy() + timedelta(days=dias)), "descripcion": "Feriado"})
    datos.lector()
    datos.ejemplar(datos.titulo())

    prestamo = db.get(models.Prestamo, _checkout(client).json()["id"])

    assert fecha_local(prestamo.fecha_vencimiento) == hoy() + timedelta(days=9)


@pytest.mark.parametrize("activo", [True, False])
def test_checkout_rechaza_lector_inexistente_o_inactivo(client, datos, activo):
    if not activo:
        datos.lector(activo=False)
    datos.ejemplar(datos.titulo())
    assert _checkout(client).status_code == 404


@pytest.mark.parametrize("estado", ["Prestado", "Perdido"])
def test_checkout_rechaza_ejemplar_no_disponible(client, datos, estado):
    datos.lector()
    datos.ejemplar(datos.titulo(), estado=estado)
    r = _checkout(client)
    assert r.status_code == 400
    assert f"Estado actual: {estado}" in r.json()["detail"]


def test_checkout_rechaza_ejemplar_inexistente(client, datos):
    datos.lector()
    assert _checkout(client, barcode="NO-EXISTE").status_code == 404


def test_checkout_respeta_el_tope_de_la_regla(client, datos):
    lector = datos.lector()
    libro = datos.titulo()
    for n in range(3):
        datos.prestamo(datos.ejemplar(libro, f"P-{n}"), lector)
    datos.ejemplar(libro, "B-001")

    r = _checkout(client)
    assert r.status_code == 400
    assert "límite de 3" in r.json()["detail"]


def test_deuda_bajo_el_umbral_no_bloquea_y_sobre_el_umbral_si(client, datos, db):
    lector = datos.lector()
    libro = datos.titulo()
    datos.ejemplar(libro, "A")
    datos.ejemplar(libro, "B")

    cuentas.registrar(db, lector, "MULTA_ATRASO", Decimal("5.00"))  # igual al umbral: no bloquea
    assert _checkout(client, "A").status_code == 200

    cuentas.registrar(db, lector, "MULTA_ATRASO", Decimal("0.50"))  # 5.50 > 5.00
    r = _checkout(client, "B")
    assert r.status_code == 400
    assert "Bs. 5.50" in r.json()["detail"]


def test_checkout_exige_categoria(client, datos, db):
    lector = datos.lector()
    lector.categoria_id = None
    db.flush()
    datos.ejemplar(datos.titulo())
    assert _checkout(client).status_code == 400


def test_tipo_de_item_no_prestable(client, datos, db):
    datos.lector()
    referencia = models.TipoItem(codigo="REF", descripcion="Referencia", es_prestable=False)
    db.add(referencia)
    db.flush()
    datos.ejemplar(datos.titulo(), tipo=referencia)

    r = _checkout(client)
    assert r.status_code == 400
    assert "consulta en sala" in r.json()["detail"]


def test_regla_no_prestable_por_tipo_de_item(client, datos, db):
    """Una regla (todas las categorías × tipo REV) gana sobre la de la categoría."""
    datos.lector()
    revista = models.TipoItem(codigo="REV", descripcion="Revista", es_prestable=True)
    db.add(revista)
    db.flush()
    general = datos.regla_de(datos.est)
    r = client.put("/api/v1/circulation-rules", json={
        "tipo_item_id": revista.id, "prestable": False, "dias_prestamo": 0, "max_prestamos": 0,
        "max_renovaciones": 0, "multa_por_dia": float(general.multa_por_dia)})
    assert r.status_code == 200, r.text
    datos.ejemplar(datos.titulo(), tipo=revista)

    assert _checkout(client).status_code == 400


# --- Devolución -----------------------------------------------------------------

def test_checkin_a_tiempo_no_genera_multa(client, datos, db):
    lector = datos.lector()
    item = datos.ejemplar(datos.titulo())
    datos.prestamo(item, lector)

    r = _checkin(client)

    assert r.status_code == 200, r.text
    assert r.json()["multa_aplicada"] == 0.0
    assert r.json()["nuevo_estado_item"] == "Disponible"
    assert r.json()["reserva"] is None
    assert db.query(models.MovimientoCuenta).count() == 0


def test_checkin_con_retraso_registra_multa_en_la_cuenta(client, datos, db):
    lector = datos.lector()
    datos.prestamo(datos.ejemplar(datos.titulo()), lector, dias_desde=10, dias_hasta=7)  # 3 días

    r = _checkin(client)

    assert r.json()["multa_aplicada"] == pytest.approx(4.5)
    db.refresh(lector)
    assert float(lector.saldo_multas) == pytest.approx(4.5)
    movimiento = db.query(models.MovimientoCuenta).one()
    assert (movimiento.tipo, float(movimiento.monto)) == ("MULTA_ATRASO", 4.5)
    assert movimiento.personal_id is not None


def test_los_dias_cerrados_no_cuentan_para_la_multa(client, datos, db):
    lector = datos.lector()
    datos.prestamo(datos.ejemplar(datos.titulo()), lector, dias_desde=10, dias_hasta=7)
    # Cierra el día de ayer (uno de los 3 de atraso).
    client.post("/api/v1/calendar/holidays",
                json={"fecha": str(hoy() - timedelta(days=1)), "descripcion": "Cierre"})

    assert _checkin(client).json()["multa_aplicada"] == pytest.approx(3.0)  # 2 días hábiles


def test_dias_de_gracia_y_tope_de_multa(client, datos, db):
    regla = datos.regla_de(datos.est)
    regla.dias_gracia, regla.multa_maxima = 2, Decimal("6.00")
    db.flush()
    lector = datos.lector()
    libro = datos.titulo()
    datos.prestamo(datos.ejemplar(libro, "G"), lector, dias_desde=9, dias_hasta=7)   # 2 días
    datos.prestamo(datos.ejemplar(libro, "T"), lector, dias_desde=17, dias_hasta=7)  # 10 días

    assert _checkin(client, "G").json()["multa_aplicada"] == 0.0     # dentro de la gracia
    assert _checkin(client, "T").json()["multa_aplicada"] == 6.0     # 15.00 topeado a 6.00


def test_checkin_rechaza_ejemplar_no_prestado(client, datos):
    datos.ejemplar(datos.titulo())
    assert _checkin(client).status_code == 400


# --- Renovación -----------------------------------------------------------------

def test_renovar_extiende_desde_el_vencimiento(client, datos, db):
    prestamo = datos.prestamo(datos.ejemplar(datos.titulo()), datos.lector())
    vencia = fecha_local(prestamo.fecha_vencimiento)

    r = client.post("/api/v1/circulation/renew", json={"prestamo_id": prestamo.id})

    assert r.status_code == 200, r.text
    db.refresh(prestamo)
    assert fecha_local(prestamo.fecha_vencimiento) == vencia + timedelta(days=7)
    assert r.json()["renovaciones_restantes"] == 1
    assert r.json()["multa_aplicada"] == 0


def test_renovar_vencido_cobra_la_mora_y_extiende_desde_hoy(client, datos, db):
    lector = datos.lector()
    prestamo = datos.prestamo(datos.ejemplar(datos.titulo()), lector, dias_desde=10)  # 3 días

    r = client.post("/api/v1/circulation/renew", json={"prestamo_id": prestamo.id})

    assert r.json()["multa_aplicada"] == pytest.approx(4.5)
    db.refresh(prestamo)
    db.refresh(lector)
    assert fecha_local(prestamo.fecha_vencimiento) == hoy() + timedelta(days=7)
    assert float(lector.saldo_multas) == pytest.approx(4.5)
    # Devolverlo a tiempo después de renovar no vuelve a cobrar esos días.
    assert _checkin(client).json()["multa_aplicada"] == 0.0


def test_renovar_respeta_el_tope_de_la_regla(client, datos, db):
    datos.regla_de(datos.est).max_renovaciones = 1
    db.flush()
    prestamo = datos.prestamo(datos.ejemplar(datos.titulo()), datos.lector(), renovaciones=1)

    r = client.post("/api/v1/circulation/renew", json={"prestamo_id": prestamo.id})
    assert r.status_code == 400
    assert "agotó sus 1" in r.json()["detail"]


def test_renovar_rechaza_si_hay_reservas(client, datos, db):
    lector, otro = datos.lector("1001"), datos.lector("1002")
    libro = datos.titulo()
    prestamo = datos.prestamo(datos.ejemplar(libro), lector)
    client.post("/api/v1/catalog/reservations", json={"biblio_id": libro.id, "nro_carnet": "1002"})

    r = client.post("/api/v1/circulation/renew", json={"prestamo_id": prestamo.id})
    assert r.status_code == 400
    assert "reservas pendientes" in r.json()["detail"]


def test_renovar_rechaza_con_deuda_sobre_el_umbral(client, datos, db):
    lector = datos.lector()
    prestamo = datos.prestamo(datos.ejemplar(datos.titulo()), lector)
    cuentas.registrar(db, lector, "AJUSTE", Decimal("10"))
    assert client.post("/api/v1/circulation/renew",
                       json={"prestamo_id": prestamo.id}).status_code == 400


def test_renovar_rechaza_prestamo_devuelto_o_inexistente(client, datos):
    prestamo = datos.prestamo(datos.ejemplar(datos.titulo()), datos.lector(), devuelto=True)
    assert client.post("/api/v1/circulation/renew",
                       json={"prestamo_id": prestamo.id}).status_code == 400
    assert client.post("/api/v1/circulation/renew",
                       json={"prestamo_id": 999999}).status_code == 404


# --- Pérdida --------------------------------------------------------------------

def test_declarar_perdido_cobra_reposicion_y_cierra_el_prestamo(client, datos, db):
    lector = datos.lector()
    item = datos.ejemplar(datos.titulo())
    item.precio_reposicion = Decimal("35.00")
    prestamo = datos.prestamo(item, lector)

    r = client.post(f"/api/v1/circulation/loans/{prestamo.id}/lost")

    assert r.status_code == 200, r.text
    assert r.json()["cargo_reposicion"] == 35.0
    db.refresh(item)
    db.refresh(lector)
    assert item.estado == "Perdido"
    assert float(lector.saldo_multas) == 35.0
    fila = next(f for f in client.get("/api/v1/circulation/loans").json() if f["id"] == str(prestamo.id))
    assert fila["lost"] is True
    assert client.post(f"/api/v1/circulation/loans/{prestamo.id}/lost").status_code == 400


def test_sin_precio_propio_se_usa_el_de_configuracion(client, datos, db):
    prestamo = datos.prestamo(datos.ejemplar(datos.titulo()), datos.lector())
    r = client.post(f"/api/v1/circulation/loans/{prestamo.id}/lost")
    assert r.json()["cargo_reposicion"] == 20.0


def _perder(client, datos, precio="35.00", carnet="1001"):
    lector = datos.lector(carnet)
    item = datos.ejemplar(datos.titulo())
    item.precio_reposicion = Decimal(precio)
    prestamo = datos.prestamo(item, lector)
    assert client.post(f"/api/v1/circulation/loans/{prestamo.id}/lost").status_code == 200
    return lector, item, prestamo


def test_ejemplar_perdido_que_aparece_vuelve_al_inventario_y_reintegra(client, datos, db):
    lector, item, prestamo = _perder(client, datos)
    fila = next(f for f in client.get("/api/v1/circulation/loans").json()
                if f["id"] == str(prestamo.id))
    assert fila["recoverable"] is True

    r = _checkin(client)

    assert r.status_code == 200, r.text
    cuerpo = r.json()
    assert (cuerpo["recuperado"], cuerpo["reintegro"]) == (True, 35.0)
    assert cuerpo["nuevo_estado_item"] == "Disponible"
    assert cuerpo["lector_reintegro"] == "Ana Pérez"
    db.refresh(item)
    db.refresh(lector)
    assert item.estado == "Disponible"
    assert float(lector.saldo_multas) == 0.0
    tipos = [m["tipo"] for m in client.get("/api/v1/users/1001/account").json()["movimientos"]]
    assert tipos[0] == "REINTEGRO"
    fila = next(f for f in client.get("/api/v1/circulation/loans").json()
                if f["id"] == str(prestamo.id))
    # El historial conserva que se perdió, pero ya no hay nada que recuperar.
    assert (fila["lost"], fila["recoverable"]) == (True, False)
    # Ya está en el estante: una segunda devolución no tiene sentido.
    assert _checkin(client).status_code == 400


def test_reposicion_ya_pagada_queda_como_saldo_a_favor(client, datos, db):
    lector, item, _ = _perder(client, datos)
    assert client.post("/api/v1/users/1001/account/payments",
                       json={"monto": 35}).status_code == 200

    assert _checkin(client).json()["reintegro"] == 35.0

    cuenta = client.get("/api/v1/users/1001/account").json()
    assert cuenta["saldo"] == -35.0
    assert cuenta["bloqueado"] is False


def _cargo_de_reposicion(client):
    cuenta = client.get("/api/v1/users/1001/account").json()
    return next(c for c in cuenta["cargos"] if c["tipo"] == "REPOSICION")


def test_reposicion_condonada_no_se_reintegra(client, datos, db):
    lector, item, _ = _perder(client, datos)
    cargo = _cargo_de_reposicion(client)
    assert (cargo["monto"], cargo["pendiente"]) == (35.0, 35.0)
    r = client.post("/api/v1/users/1001/account/waivers",
                    json={"monto": 35, "motivo": "Lo perdió en una inundación",
                          "cargo_id": cargo["id"]})
    assert r.status_code == 200, r.text
    assert r.json()["cargos"] == []

    cuerpo = _checkin(client).json()

    # Lo perdonado no vuelve como saldo a favor.
    assert (cuerpo["recuperado"], cuerpo["reintegro"]) == (True, 0.0)
    db.refresh(lector)
    assert float(lector.saldo_multas) == 0.0


def test_condonacion_parcial_reintegra_solo_lo_cargado(client, datos, db):
    lector, item, _ = _perder(client, datos)
    cargo = _cargo_de_reposicion(client)
    client.post("/api/v1/users/1001/account/waivers",
                json={"monto": 15, "motivo": "Acuerdo con el lector", "cargo_id": cargo["id"]})
    assert _cargo_de_reposicion(client)["pendiente"] == 20.0
    demasiado = client.post("/api/v1/users/1001/account/waivers",
                            json={"monto": 25, "motivo": "Excede", "cargo_id": cargo["id"]})
    assert demasiado.status_code == 400 and "20.00" in demasiado.json()["detail"]

    assert _checkin(client).json()["reintegro"] == 20.0
    db.refresh(lector)
    assert float(lector.saldo_multas) == 0.0


def test_condonar_la_multa_del_mismo_prestamo_no_afecta_el_reintegro(client, datos, db):
    lector, item, prestamo = _perder(client, datos)
    multa = cuentas.registrar(db, lector, "MULTA_ATRASO", Decimal("4"), prestamo_id=prestamo.id)
    db.flush()
    client.post("/api/v1/users/1001/account/waivers",
                json={"monto": 4, "motivo": "Error de fecha", "cargo_id": multa.id})

    assert _checkin(client).json()["reintegro"] == 35.0


def test_reposicion_reintegrada_ya_no_se_ofrece_para_condonar(client, datos, db):
    _perder(client, datos)
    assert _checkin(client).json()["reintegro"] == 35.0
    cuenta = client.get("/api/v1/users/1001/account").json()
    assert cuenta["cargos"] == []
    reintegro = next(m for m in cuenta["movimientos"] if m["tipo"] == "REINTEGRO")
    reposicion = next(m for m in cuenta["movimientos"] if m["tipo"] == "REPOSICION")
    assert reintegro["cargo_id"] == reposicion["id"]


def test_condonar_un_cargo_ajeno(client, datos, db):
    _perder(client, datos)
    otro = datos.lector("2002")
    ajeno = cuentas.registrar(db, otro, "AJUSTE", Decimal("3"))
    db.flush()
    r = client.post("/api/v1/users/1001/account/waivers",
                    json={"monto": 1, "motivo": "Prueba", "cargo_id": ajeno.id})
    assert r.status_code == 404


def test_reintegro_solo_una_vez_aunque_se_vuelva_a_perder(client, datos, db):
    lector, item, _ = _perder(client, datos)
    assert _checkin(client).json()["reintegro"] == 35.0
    # Se presta de nuevo y se pierde otra vez: el segundo hallazgo reintegra el segundo cargo.
    otro = datos.prestamo(item, lector)
    item.estado = "Prestado"
    db.flush()
    assert client.post(f"/api/v1/circulation/loans/{otro.id}/lost").status_code == 200
    assert _checkin(client).json()["reintegro"] == 35.0
    db.refresh(lector)
    assert float(lector.saldo_multas) == 0.0


def test_ejemplar_perdido_que_aparece_se_aparta_para_la_reserva(client, datos, db):
    _lector, item, _ = _perder(client, datos)
    datos.lector("2002", nombre="Beto")
    assert client.post("/api/v1/catalog/reservations",
                       json={"biblio_id": item.biblio_id, "nro_carnet": "2002"}).status_code == 201

    cuerpo = _checkin(client).json()

    assert cuerpo["nuevo_estado_item"] == "Reservado"
    assert cuerpo["reserva"]["carnet"] == "2002"


def test_perdido_sin_prestamo_asociado_vuelve_sin_reintegro(client, datos, db):
    item = datos.ejemplar(datos.titulo(), estado="Perdido")

    cuerpo = _checkin(client).json()

    assert (cuerpo["reintegro"], cuerpo["lector_reintegro"]) == (0.0, None)
    db.refresh(item)
    assert item.estado == "Disponible"


# --- Listado y exportación ------------------------------------------------------

def test_listado_de_prestamos_clasifica_estado_y_tipo_de_lector(client, datos):
    est = datos.lector("1001")
    doc = datos.lector("2001", categoria=datos.doc)
    libro = datos.titulo()
    datos.prestamo(datos.ejemplar(libro, "A"), est)
    datos.prestamo(datos.ejemplar(libro, "B"), doc, dias_desde=20)
    datos.prestamo(datos.ejemplar(libro, "C"), est, devuelto=True)

    filas = {f["bookCode"]: f for f in client.get("/api/v1/circulation/loans").json()}

    assert (filas["A"]["status"], filas["A"]["userType"]) == ("active", "student")
    assert (filas["B"]["status"], filas["B"]["userType"]) == ("overdue", "teacher")
    assert filas["C"]["status"] == "returned"
    assert filas["C"]["returnDate"] is not None
    assert set(filas["A"]) == {"id", "bookTitle", "bookCode", "userName", "userId", "userType",
                               "loanDate", "dueDate", "returnDate", "renewals", "status", "lost",
                               "renewalsAllowed", "recoverable"}
    assert filas["A"]["renewalsAllowed"] == 2


def test_fechas_en_espanol_y_hora_local(client, datos):
    datos.prestamo(datos.ejemplar(datos.titulo()), datos.lector())
    fila = client.get("/api/v1/circulation/loans").json()[0]
    dia, mes, anio = fila["loanDate"].split()
    assert mes in {"ene", "feb", "mar", "abr", "may", "jun", "jul", "ago", "sep", "oct",
                   "nov", "dic"}
    assert int(anio) == hoy().year


def test_exportar_prestamos_devuelve_csv_con_bom(client, datos):
    datos.prestamo(datos.ejemplar(datos.titulo()), datos.lector())

    r = client.get("/api/v1/circulation/loans/export")

    assert r.headers["content-type"].startswith("text/csv")
    assert "attachment" in r.headers["content-disposition"]
    assert r.text.startswith("﻿id,bookTitle,bookCode")
    assert "B-001" in r.text
