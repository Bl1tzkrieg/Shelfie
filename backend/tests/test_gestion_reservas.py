"""Gestión de reservas: turno, suspensión, fecha límite, sede de retiro y "para sacar del estante"."""

from datetime import timedelta

import pytest

from app import models
from app.core.tiempo import hoy

CHECKIN = "/api/v1/circulation/checkin"
HOLDS = "/api/v1/circulation/holds"


@pytest.fixture(autouse=True)
def calendario_abierto(datos):
    datos.sin_dias_cerrados()


def _reservar(client, biblio_id, carnet, **extra):
    r = client.post("/api/v1/catalog/reservations",
                    json={"biblio_id": biblio_id, "nro_carnet": carnet, **extra})
    assert r.status_code == 201, r.text
    return r.json()["reserva_id"]


def _cola(datos, lectores=("B2", "C3", "D4")):
    """El único ejemplar está prestado; varios esperan."""
    for carnet in ("A1", *lectores):
        datos.lector(carnet)
    libro = datos.titulo()
    item = datos.ejemplar(libro)
    datos.prestamo(item, datos.db.query(models.Usuario).filter_by(nro_carnet="A1").one())
    return libro, item


def _turnos(client, libro):
    filas = client.get(f"{HOLDS}?biblio_id={libro.id}").json()
    return [(f["userId"], f["priority"]) for f in filas if f["status"] == "Pendiente"]


def test_mover_el_turno(client, datos):
    libro, _ = _cola(datos)
    ids = [_reservar(client, libro.id, c) for c in ("B2", "C3", "D4")]

    r = client.patch(f"{HOLDS}/{ids[2]}", json={"prioridad": 1})

    assert r.status_code == 200, r.text
    assert r.json()["priority"] == 1
    assert _turnos(client, libro) == [("D4", 1), ("B2", 2), ("C3", 3)]
    client.patch(f"{HOLDS}/{ids[2]}", json={"prioridad": 99})  # al final
    assert _turnos(client, libro) == [("B2", 1), ("C3", 2), ("D4", 3)]


def test_la_suspendida_conserva_su_turno_pero_no_recibe_el_ejemplar(client, datos, db):
    libro, _ = _cola(datos, ("B2", "C3"))
    beto = _reservar(client, libro.id, "B2")
    _reservar(client, libro.id, "C3")
    client.patch(f"{HOLDS}/{beto}", json={"suspendida": True})

    r = client.post(CHECKIN, json={"codigo_barras": "B-001"})

    assert r.json()["reserva"]["carnet"] == "C3"
    reserva = db.get(models.Reserva, beto)
    assert (reserva.estado, reserva.suspendida, reserva.prioridad) == ("Pendiente", True, 1)

    reanudada = client.patch(f"{HOLDS}/{beto}", json={"suspendida": False}).json()
    assert reanudada["suspended"] is False


def test_la_suspension_con_fecha_se_reanuda_sola(client, datos, db):
    libro, _ = _cola(datos, ("B2",))
    beto = _reservar(client, libro.id, "B2")
    manana = (hoy() + timedelta(days=1)).isoformat()

    r = client.patch(f"{HOLDS}/{beto}", json={"suspendida": True, "suspendida_hasta": manana})
    assert r.json()["suspendedUntil"] == manana
    assert client.patch(f"{HOLDS}/{beto}", json={
        "suspendida": True, "suspendida_hasta": hoy().isoformat()}).status_code == 400

    db.get(models.Reserva, beto).suspendida_hasta = hoy()
    db.flush()
    fila = client.get(f"{HOLDS}?biblio_id={libro.id}").json()[0]

    assert fila["suspended"] is False and fila["suspendedUntil"] is None


def test_las_suspendidas_no_impiden_renovar(client, datos, db):
    libro, item = _cola(datos, ("B2",))
    beto = _reservar(client, libro.id, "B2")
    prestamo = db.query(models.Prestamo).filter_by(item_id=item.id).one()

    assert client.post("/api/v1/circulation/renew",
                       json={"prestamo_id": prestamo.id}).status_code == 400
    client.patch(f"{HOLDS}/{beto}", json={"suspendida": True})
    assert client.post("/api/v1/circulation/renew",
                       json={"prestamo_id": prestamo.id}).status_code == 200


def test_fecha_limite(client, datos, db):
    libro, _ = _cola(datos, ("B2", "C3"))
    ayer = (hoy() - timedelta(days=1)).isoformat()
    r = client.post("/api/v1/catalog/reservations",
                    json={"biblio_id": libro.id, "nro_carnet": "B2", "fecha_limite": ayer})
    assert r.status_code == 400

    beto = _reservar(client, libro.id, "B2", fecha_limite=(hoy() + timedelta(days=5)).isoformat())
    _reservar(client, libro.id, "C3")
    db.get(models.Reserva, beto).fecha_limite = hoy() - timedelta(days=1)
    db.flush()

    client.post(f"{HOLDS}/expire")

    assert db.get(models.Reserva, beto).estado == "Expirada"
    assert _turnos(client, libro) == [("C3", 1)]


def test_notas_y_quitar_la_fecha_limite(client, datos):
    libro, _ = _cola(datos, ("B2",))
    beto = _reservar(client, libro.id, "B2", notas="  Edición de bolsillo  ",
                     fecha_limite=(hoy() + timedelta(days=5)).isoformat())

    r = client.patch(f"{HOLDS}/{beto}", json={"fecha_limite": None, "notas": "Llamar antes"})

    assert (r.json()["notNeededAfter"], r.json()["notes"]) == (None, "Llamar antes")


def test_sede_de_retiro(client, datos, db):
    norte, sur = datos.sede("NOR", "Sede Norte"), datos.sede("SUR", "Sede Sur")
    deposito = datos.sede("DEP", "Depósito", punto_retiro=False)
    libro, _ = _cola(datos, ("B2", "C3"))
    db.query(models.Usuario).filter_by(nro_carnet="B2").one().biblioteca_id = sur.id
    db.flush()

    # Por defecto, la sede del lector.
    beto = _reservar(client, libro.id, "B2")
    assert db.get(models.Reserva, beto).biblioteca_retiro_id == sur.id
    # En una sede que no es punto de retiro, no.
    r = client.post("/api/v1/catalog/reservations", json={
        "biblio_id": libro.id, "nro_carnet": "C3", "biblioteca_retiro_id": deposito.id})
    assert r.status_code == 400 and "no se retiran" in r.json()["detail"]

    cambio = client.patch(f"{HOLDS}/{beto}", json={"biblioteca_retiro_id": norte.id})
    assert cambio.json()["pickupBranch"] == "Sede Norte"


def test_solo_se_cambia_el_turno_de_una_pendiente(client, datos):
    libro, _ = _cola(datos, ("B2",))
    beto = _reservar(client, libro.id, "B2")
    client.post(CHECKIN, json={"codigo_barras": "B-001"})

    for cambio in ({"prioridad": 1}, {"suspendida": True}):
        r = client.patch(f"{HOLDS}/{beto}", json=cambio)
        assert r.status_code == 400 and "pendiente" in r.json()["detail"]
    # Las notas sí.
    assert client.patch(f"{HOLDS}/{beto}", json={"notas": "Viene el lunes"}).status_code == 200


def test_para_sacar_del_estante_y_apartar_escaneando(client, datos, db):
    datos.lector("B2")
    libro = datos.titulo()
    item = datos.ejemplar(libro, "LIBRE-1")
    r = client.post("/api/v1/catalog/reservations",
                    json={"biblio_id": libro.id, "nro_carnet": "B2"})
    assert "Para sacar del estante" in r.json()["mensaje"]

    por_sacar = client.get(f"{HOLDS}/to-pull").json()
    assert len(por_sacar) == 1
    assert (por_sacar[0]["firstPatronId"], por_sacar[0]["toPull"]) == ("B2", 1)
    assert [i["barcode"] for i in por_sacar[0]["items"]] == ["LIBRE-1"]

    apartado = client.post(CHECKIN, json={"codigo_barras": "LIBRE-1"})

    assert apartado.status_code == 200, apartado.text
    assert apartado.json()["accion"] == "espera"
    db.refresh(item)
    assert item.estado == "Reservado"
    assert client.get(f"{HOLDS}/to-pull").json() == []
    # Un ejemplar disponible sin nadie que lo espere no tiene nada que devolver.
    datos.ejemplar(libro, "LIBRE-2")
    assert client.post(CHECKIN, json={"codigo_barras": "LIBRE-2"}).status_code == 400


def test_prestar_otra_copia_libera_la_que_tenia_apartada(client, datos, db):
    datos.lector("B2"), datos.lector("C3")
    libro = datos.titulo()
    apartada = datos.ejemplar(libro, "AP-1")
    datos.ejemplar(libro, "AP-2", estado="Prestado")
    beto = _reservar(client, libro.id, "B2")
    _reservar(client, libro.id, "C3")
    client.post(CHECKIN, json={"codigo_barras": "AP-1"})
    db.get(models.Item, db.query(models.Item).filter_by(codigo_barras="AP-2").one().id).estado = \
        "Disponible"
    db.flush()

    r = client.post("/api/v1/circulation/checkout",
                    json={"codigo_barras": "AP-2", "nro_carnet": "B2"})

    assert r.status_code == 200, r.text
    assert db.get(models.Reserva, beto).estado == "Cumplida"
    # AP-1 pasa a Carla.
    db.refresh(apartada)
    assert apartada.estado == "Reservado"
    carla = db.query(models.Reserva).filter_by(estado="EnEspera").one()
    assert db.get(models.Usuario, carla.usuario_id).nro_carnet == "C3"


def test_listado_con_los_datos_de_gestion(client, datos):
    libro, _ = _cola(datos, ("B2",))
    _reservar(client, libro.id, "B2")
    client.post(CHECKIN, json={"codigo_barras": "B-001"})

    fila = client.get(HOLDS).json()[0]

    assert fila["status"] == "EnEspera"
    assert fila["biblioId"] == str(libro.id) and fila["author"] == "Gabriel García Márquez"
    assert fila["daysWaiting"] == 0 and fila["waitingSince"] is not None
    assert fila["itemBarcode"] == "B-001" and fila["callNumber"] == "PQ 8180"
