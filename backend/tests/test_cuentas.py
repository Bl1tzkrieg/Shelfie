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
