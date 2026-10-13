"""Ciclo de vida de las reservas: cola, en espera, retiro, expiración y cancelación."""

from datetime import timedelta
from decimal import Decimal

import pytest

from app import models
from app.core.tiempo import ahora, fecha_local, hoy
from app.services import cuentas


@pytest.fixture(autouse=True)
def calendario_abierto(datos):
    datos.sin_dias_cerrados()


def _reservar(client, biblio_id, carnet):
    return client.post("/api/v1/catalog/reservations",
                       json={"biblio_id": biblio_id, "nro_carnet": carnet})


def _escenario(datos):
    """Ana tiene prestado el único ejemplar; Beto y Carla esperan en cola."""
    ana, beto, carla = datos.lector("A1"), datos.lector("B2"), datos.lector("C3")
    libro = datos.titulo()
    item = datos.ejemplar(libro)
    datos.prestamo(item, ana)
    return libro, item, ana, beto, carla


def test_la_devolucion_aparta_el_ejemplar_para_el_primero_de_la_cola(client, datos, db):
    libro, item, _ana, _beto, _carla = _escenario(datos)
    _reservar(client, libro.id, "B2")
    _reservar(client, libro.id, "C3")

    r = client.post("/api/v1/circulation/checkin", json={"codigo_barras": "B-001"})

    assert r.json()["nuevo_estado_item"] == "Reservado"
    assert r.json()["reserva"]["carnet"] == "B2"
    reserva = db.query(models.Reserva).filter_by(estado="EnEspera").one()
    assert reserva.item_id == item.id
    # 3 días hábiles para retirarlo (configuración por defecto).
    assert fecha_local(reserva.fecha_expiracion) == hoy() + timedelta(days=3)
    # Carla pasa a ser la primera de las pendientes.
    pendiente = db.query(models.Reserva).filter_by(estado="Pendiente").one()
    assert pendiente.prioridad == 1


def test_el_plazo_de_retiro_cuenta_dias_habiles(client, datos, db):
    libro, *_ = _escenario(datos)
    manana = (hoy() + timedelta(days=1)).weekday()
    client.put("/api/v1/calendar/closed-days", json={"dias": [manana]})
    _reservar(client, libro.id, "B2")

    client.post("/api/v1/circulation/checkin", json={"codigo_barras": "B-001"})

    reserva = db.query(models.Reserva).filter_by(estado="EnEspera").one()
    assert fecha_local(reserva.fecha_expiracion) == hoy() + timedelta(days=4)


def test_solo_quien_reservo_puede_retirar_el_ejemplar_apartado(client, datos, db):
    libro, *_ = _escenario(datos)
    _reservar(client, libro.id, "B2")
    client.post("/api/v1/circulation/checkin", json={"codigo_barras": "B-001"})

    otro = client.post("/api/v1/circulation/checkout",
                       json={"codigo_barras": "B-001", "nro_carnet": "C3"})
    assert otro.status_code == 400
    assert "apartado para" in otro.json()["detail"]

    titular = client.post("/api/v1/circulation/checkout",
                          json={"codigo_barras": "B-001", "nro_carnet": "B2"})
    assert titular.status_code == 200, titular.text
    assert db.query(models.Reserva).filter_by(usuario_id=titular.json()["usuario_id"]).one().estado \
        == "Cumplida"


def test_reserva_vencida_pasa_al_siguiente_de_la_cola(client, datos, db):
    libro, item, *_ = _escenario(datos)
    _reservar(client, libro.id, "B2")
    _reservar(client, libro.id, "C3")
    client.post("/api/v1/circulation/checkin", json={"codigo_barras": "B-001"})
    en_espera = db.query(models.Reserva).filter_by(estado="EnEspera").one()
    en_espera.fecha_expiracion = ahora() - timedelta(minutes=1)
    db.flush()

    r = client.post("/api/v1/circulation/holds/expire")

    assert r.json() == {"expiradas": 1}
    db.refresh(en_espera)
    assert en_espera.estado == "Expirada"
    nueva = db.query(models.Reserva).filter_by(estado="EnEspera").one()
    assert db.get(models.Usuario, nueva.usuario_id).nro_carnet == "C3"
    db.refresh(item)
    assert item.estado == "Reservado"


def test_reserva_vencida_sin_cola_libera_el_ejemplar(client, datos, db):
    libro, item, *_ = _escenario(datos)
    _reservar(client, libro.id, "B2")
    client.post("/api/v1/circulation/checkin", json={"codigo_barras": "B-001"})
    db.query(models.Reserva).filter_by(estado="EnEspera").one().fecha_expiracion = \
        ahora() - timedelta(minutes=1)
    db.flush()

    # La expiración también ocurre sola al operar en circulación.
    client.get("/api/v1/circulation/holds")

    db.refresh(item)
    assert item.estado == "Disponible"


def test_cancelar_una_reserva_en_espera_libera_el_ejemplar(client, datos, db):
    libro, item, *_ = _escenario(datos)
    reserva_id = _reservar(client, libro.id, "B2").json()["reserva_id"]
    client.post("/api/v1/circulation/checkin", json={"codigo_barras": "B-001"})

    assert client.delete(f"/api/v1/catalog/reservations/{reserva_id}").status_code == 200

    db.refresh(item)
    assert item.estado == "Disponible"
    assert client.delete(f"/api/v1/catalog/reservations/{reserva_id}").status_code == 400


def test_prestar_un_ejemplar_libre_cumple_la_reserva_pendiente_del_lector(client, datos, db):
    datos.lector("B2")
    libro = datos.titulo()
    datos.ejemplar(libro, "X")
    _reservar(client, libro.id, "B2")

    client.post("/api/v1/circulation/checkout", json={"codigo_barras": "X", "nro_carnet": "B2"})

    assert db.query(models.Reserva).one().estado == "Cumplida"


def test_reglas_para_reservar(client, datos, db):
    libro, _item, ana, beto, _carla = _escenario(datos)

    assert _reservar(client, libro.id, "A1").status_code == 400  # ya lo tiene prestado
    assert _reservar(client, libro.id, "B2").status_code == 201
    assert _reservar(client, libro.id, "B2").status_code == 400  # ya tiene reserva activa

    cuentas.registrar(db, datos.lector("D4"), "AJUSTE", Decimal("9"))
    assert "debe Bs. 9.00" in _reservar(client, libro.id, "D4").json()["detail"]

    datos.regla_de(datos.est).max_reservas = 1
    db.flush()
    otro = datos.titulo("Otro", "123")
    r = _reservar(client, otro.id, "B2")
    assert r.status_code == 400
    assert "límite de 1 reservas" in r.json()["detail"]


def test_listado_de_reservas_activas(client, datos):
    libro, *_ = _escenario(datos)
    _reservar(client, libro.id, "B2")
    reserva_id = _reservar(client, libro.id, "C3").json()["reserva_id"]
    client.delete(f"/api/v1/catalog/reservations/{reserva_id}")

    activas = client.get("/api/v1/circulation/holds").json()
    todas = client.get("/api/v1/circulation/holds?activas=false").json()

    assert [r["userId"] for r in activas] == ["B2"]
    assert {r["status"] for r in todas} == {"Pendiente", "Cancelada"}
    assert activas[0]["reservedOn"] is not None
