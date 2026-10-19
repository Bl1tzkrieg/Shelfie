"""Cuenta del lector: estado, pagos y condonaciones."""

from decimal import Decimal

from app.services import cuentas


def _con_deuda(datos, db, monto="12.50", carnet="1001"):
    lector = datos.lector(carnet)
    cuentas.registrar(db, lector, "MULTA_ATRASO", Decimal(monto), descripcion="Atraso")
    return lector


def test_estado_de_cuenta(client, datos, db):
    _con_deuda(datos, db)
    c = client.get("/api/v1/users/1001/account").json()
    assert c["saldo"] == 12.5
    assert c["umbral_bloqueo"] == 5.0
    assert c["bloqueado"] is True
    assert [m["tipo"] for m in c["movimientos"]] == ["MULTA_ATRASO"]


def test_pago_parcial_y_total(client, datos, db):
    lector = _con_deuda(datos, db)

    parcial = client.post("/api/v1/users/1001/account/payments", json={"monto": 10})
    assert parcial.status_code == 200, parcial.text
    assert parcial.json()["saldo"] == 2.5
    assert parcial.json()["bloqueado"] is False  # 2.50 ya no supera el umbral

    total = client.post("/api/v1/users/1001/account/payments", json={"monto": 2.5})
    assert total.json()["saldo"] == 0
    db.refresh(lector)
    assert float(lector.saldo_multas) == 0
    tipos = [m["tipo"] for m in total.json()["movimientos"]]
    assert tipos.count("PAGO") == 2


def test_no_se_paga_mas_de_lo_que_se_debe(client, datos, db):
    _con_deuda(datos, db, "3")
    r = client.post("/api/v1/users/1001/account/payments", json={"monto": 5})
    assert r.status_code == 400
    assert "supera la deuda" in r.json()["detail"]
    assert client.post("/api/v1/users/1001/account/payments",
                       json={"monto": 0}).status_code == 422


def test_condonar_exige_motivo_y_permiso_de_lectores(client, como, datos, db):
    _con_deuda(datos, db)
    cajero = como(["circulacion"])

    assert cajero.post("/api/v1/users/1001/account/payments", json={"monto": 1}).status_code == 200
    assert cajero.post("/api/v1/users/1001/account/waivers",
                       json={"monto": 1, "motivo": "Error"}).status_code == 403
    assert client.post("/api/v1/users/1001/account/waivers",
                       json={"monto": 1, "motivo": ""}).status_code == 422

    r = client.post("/api/v1/users/1001/account/waivers",
                    json={"monto": 11.5, "motivo": "Devolvió en buen estado"})
    assert r.status_code == 200
    assert r.json()["saldo"] == 0
    assert r.json()["movimientos"][0]["descripcion"] == "Devolvió en buen estado"


def test_ficha_del_lector_indica_bloqueo(client, datos, db):
    _con_deuda(datos, db, "4.00", "1001")
    _con_deuda(datos, db, "6.00", "1002")
    fichas = {u["nro_carnet"]: u for u in client.get("/api/v1/users").json()}
    assert fichas["1001"]["bloqueado_por_deuda"] is False
    assert fichas["1002"]["bloqueado_por_deuda"] is True


def test_umbral_configurable(client, datos, db):
    _con_deuda(datos, db, "4.00")
    client.put("/api/v1/settings", json={"circulacion": {"umbral_bloqueo": 3}})
    assert client.get("/api/v1/users/1001/account").json()["bloqueado"] is True


# --- Imputación de créditos (auditoría A3, M5) ------------------------------------------------

def test_pago_general_se_imputa_al_cargo_mas_viejo(client, datos, db):
    lector = datos.lector("1001")
    multa = cuentas.registrar(db, lector, "MULTA_ATRASO", Decimal("10"), descripcion="Atraso")
    reposicion = cuentas.registrar(db, lector, "REPOSICION", Decimal("35"), descripcion="Perdido")
    r = client.post("/api/v1/users/1001/account/payments", json={"monto": 10}).json()
    # La multa quedó pagada y ya no aparece como cargo pendiente.
    assert [(c["id"], c["pendiente"]) for c in r["cargos"]] == [(reposicion.id, 35.0)]
    # Por eso ya no se puede condonar "la multa".
    mal = client.post("/api/v1/users/1001/account/waivers",
                      json={"monto": 10, "motivo": "error", "cargo_id": multa.id})
    assert mal.status_code == 400


def test_pago_dirigido_a_un_cargo(client, datos, db):
    lector = datos.lector("1001")
    cuentas.registrar(db, lector, "MULTA_ATRASO", Decimal("10"), descripcion="Atraso")
    reposicion = cuentas.registrar(db, lector, "REPOSICION", Decimal("35"), descripcion="Perdido")
    r = client.post("/api/v1/users/1001/account/payments",
                    json={"monto": 20, "cargo_id": reposicion.id}).json()
    pendientes = {c["tipo"]: (c["pagado"], c["pendiente"]) for c in r["cargos"]}
    assert pendientes == {"MULTA_ATRASO": (0.0, 10.0), "REPOSICION": (20.0, 15.0)}


def _perdido(client, datos, db, carnet="1001"):
    datos.sin_dias_cerrados()
    lector = datos.lector(carnet)
    item = datos.ejemplar(datos.titulo(), "P-1")
    item.precio_reposicion = Decimal("35")
    prestamo = datos.prestamo(item, lector)
    db.flush()
    client.post(f"/api/v1/circulation/loans/{prestamo.id}/lost", json={})
    return lector


def test_condonacion_general_y_el_libro_aparece_no_deja_credito(client, datos, db):
    _perdido(client, datos, db)
    client.post("/api/v1/users/1001/account/waivers", json={"monto": 35, "motivo": "Inundación"})
    r = client.post("/api/v1/circulation/checkin", json={"codigo_barras": "P-1"}).json()
    assert r["recuperado"] and r["reintegro"] == 0
    assert client.get("/api/v1/users/1001/account").json()["saldo"] == 0


def test_pago_general_y_el_libro_aparece_reintegra_lo_pagado(client, datos, db):
    _perdido(client, datos, db)
    client.post("/api/v1/users/1001/account/payments", json={"monto": 35})
    r = client.post("/api/v1/circulation/checkin", json={"codigo_barras": "P-1"}).json()
    assert r["reintegro"] == 35
    assert client.get("/api/v1/users/1001/account").json()["saldo"] == -35


def test_mitad_condonada_mitad_pendiente(client, datos, db):
    _perdido(client, datos, db)
    client.post("/api/v1/users/1001/account/waivers", json={"monto": 15, "motivo": "Acuerdo"})
    r = client.post("/api/v1/circulation/checkin", json={"codigo_barras": "P-1"}).json()
    # Se anula lo que seguía pendiente (20); lo condonado no se devuelve.
    assert r["reintegro"] == 20
    assert client.get("/api/v1/users/1001/account").json()["saldo"] == 0


# --- Mora al declarar perdido (M2) ---------------------------------------------------------

def test_declarar_perdido_cobra_la_mora(client, datos, db):
    from app.services import configuracion
    datos.sin_dias_cerrados()
    lector = datos.lector("1001")
    regla = datos.regla_de(datos.est)
    regla.multa_por_dia, regla.dias_gracia, regla.multa_maxima = 1, 0, None
    item = datos.ejemplar(datos.titulo(), "P-2")
    item.precio_reposicion = Decimal("20")
    prestamo = datos.prestamo(item, lector, dias_desde=17, dias_hasta=7)  # 10 días de atraso
    db.flush()
    r = client.post(f"/api/v1/circulation/loans/{prestamo.id}/lost", json={}).json()
    assert (r["cargo_reposicion"], r["multa_atraso"]) == (20.0, 10.0)
    assert client.get("/api/v1/users/1001/account").json()["saldo"] == 30

    configuracion.guardar(db, {"circulacion": {"perdonar_mora_al_perder": True}})
    otro = datos.prestamo(datos.ejemplar(datos.titulo("Otro", None), "P-3"), lector,
                          dias_desde=17, dias_hasta=7)
    db.flush()
    assert client.post(f"/api/v1/circulation/loans/{otro.id}/lost", json={}).json()["multa_atraso"] == 0
