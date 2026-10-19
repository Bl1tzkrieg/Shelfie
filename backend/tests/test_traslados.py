"""Traslados entre sedes: reservas que viajan a su sede de retiro, retorno y traslados a mano."""

from datetime import timedelta

import pytest

from app import models
from app.core.tiempo import ahora, fecha_local, hoy
from app.services import configuracion

CHECKIN = "/api/v1/circulation/checkin"
TRASLADOS = "/api/v1/circulation/transfers"


@pytest.fixture(autouse=True)
def calendario_abierto(datos):
    datos.sin_dias_cerrados()


@pytest.fixture()
def sedes(datos):
    """Norte y Sur; Este no es punto de retiro."""
    return datos.sede("NOR", "Sede Norte"), datos.sede("SUR", "Sede Sur"), \
        datos.sede("EST", "Sede Este", punto_retiro=False)


def en(cliente, sede):
    """El personal opera desde `sede` (lo que el frontend manda en cada petición)."""
    cliente.headers["X-Shelfie-Sede"] = str(sede.id)
    return cliente


def _reservar(client, biblio_id, carnet, sede=None):
    cuerpo = {"biblio_id": biblio_id, "nro_carnet": carnet}
    if sede is not None:
        cuerpo["biblioteca_retiro_id"] = sede.id
    r = client.post("/api/v1/catalog/reservations", json=cuerpo)
    assert r.status_code == 201, r.text
    return r.json()["reserva_id"]


def _prestado_en_norte(datos, sedes):
    """Ana tiene prestado el único ejemplar, que es de Norte."""
    norte = sedes[0]
    ana, beto = datos.lector("A1"), datos.lector("B2")
    libro = datos.titulo()
    item = datos.ejemplar(libro, sede=norte)
    datos.prestamo(item, ana)
    return libro, item, ana, beto


def test_la_devolucion_manda_el_ejemplar_a_la_sede_de_retiro(client, datos, db, sedes):
    norte, sur, _ = sedes
    libro, item, _ana, _beto = _prestado_en_norte(datos, sedes)
    reserva_id = _reservar(client, libro.id, "B2", sur)

    r = en(client, norte).post(CHECKIN, json={"codigo_barras": "B-001"})

    assert r.status_code == 200, r.text
    cuerpo = r.json()
    assert cuerpo["accion"] == "transito"
    assert cuerpo["nuevo_estado_item"] == "EnTransito"
    assert cuerpo["traslado"]["hacia"] == "Sede Sur" and cuerpo["traslado"]["enviado"]
    assert cuerpo["reserva"]["carnet"] == "B2" and cuerpo["reserva"]["retirar_hasta"] is None
    reserva = db.get(models.Reserva, reserva_id)
    assert reserva.estado == "EnTransito" and reserva.item_id == item.id
    traslado = db.query(models.Traslado).one()
    assert (traslado.desde_id, traslado.hacia_id, traslado.motivo, traslado.estado) == \
        (norte.id, sur.id, "reserva", "Enviado")


def test_al_llegar_queda_en_espera_y_el_plazo_corre_desde_la_llegada(client, datos, db, sedes):
    norte, sur, _ = sedes
    libro, item, *_ = _prestado_en_norte(datos, sedes)
    reserva_id = _reservar(client, libro.id, "B2", sur)
    en(client, norte).post(CHECKIN, json={"codigo_barras": "B-001"})

    r = en(client, sur).post(CHECKIN, json={"codigo_barras": "B-001"})

    assert r.json()["accion"] == "espera"
    assert r.json()["reserva"]["sede_retiro"] == "Sede Sur"
    assert r.json()["reserva"]["retirar_hasta"] is not None
    reserva = db.get(models.Reserva, reserva_id)
    assert reserva.estado == "EnEspera"
    assert fecha_local(reserva.fecha_expiracion) == hoy() + timedelta(days=3)
    db.refresh(item)
    assert (item.estado, item.biblioteca_actual_id) == ("Reservado", sur.id)
    assert db.query(models.Traslado).one().estado == "Recibido"


def test_recibir_desde_la_pantalla_de_traslados(client, datos, db, sedes):
    norte, sur, _ = sedes
    libro, item, *_ = _prestado_en_norte(datos, sedes)
    _reservar(client, libro.id, "B2", sur)
    en(client, norte).post(CHECKIN, json={"codigo_barras": "B-001"})

    por_recibir = en(client, sur).get(f"{TRASLADOS}?vista=por_recibir").json()
    assert [t["barcode"] for t in por_recibir] == ["B-001"]
    assert por_recibir[0]["patron"] == "Ana Pérez" and por_recibir[0]["reason"] == "reserva"
    assert en(client, norte).get(f"{TRASLADOS}?vista=por_recibir").json() == []
    assert len(en(client, norte).get(f"{TRASLADOS}?vista=enviados").json()) == 1

    r = en(client, sur).post(f"{TRASLADOS}/{por_recibir[0]['id']}/receive")

    assert r.status_code == 200, r.text
    assert r.json()["status"] == "Recibido"
    assert r.json()["resultado"]["accion"] == "espera"
    db.refresh(item)
    assert item.estado == "Reservado"
    assert en(client, sur).get(f"{TRASLADOS}/summary").json() == {
        "sede_id": sur.id, "por_enviar": 0, "por_recibir": 0, "enviados": 0}


def test_sin_reservas_el_ejemplar_vuelve_a_su_sede(client, datos, db, sedes):
    norte, sur, _ = sedes
    _libro, item, *_ = _prestado_en_norte(datos, sedes)

    r = en(client, sur).post(CHECKIN, json={"codigo_barras": "B-001"})

    assert r.json()["accion"] == "retorno"
    assert r.json()["traslado"]["hacia"] == "Sede Norte"
    llegada = en(client, norte).post(CHECKIN, json={"codigo_barras": "B-001"})
    assert llegada.json()["accion"] == "disponible"
    db.refresh(item)
    assert (item.estado, item.biblioteca_actual_id) == ("Disponible", norte.id)


def test_con_el_retorno_apagado_se_queda_donde_lo_devolvieron(client, datos, db, sedes):
    _norte, sur, _ = sedes
    _libro, item, *_ = _prestado_en_norte(datos, sedes)
    configuracion.guardar(db, {"circulacion": {"retorno_a_sede_propia": False}})

    r = en(client, sur).post(CHECKIN, json={"codigo_barras": "B-001"})

    assert r.json()["accion"] == "disponible"
    db.refresh(item)
    assert (item.estado, item.biblioteca_actual_id) == ("Disponible", sur.id)


def test_cancelar_el_traslado_devuelve_la_reserva_al_primer_turno(client, datos, db, sedes):
    norte, sur, _ = sedes
    libro, item, *_ = _prestado_en_norte(datos, sedes)
    beto_id = _reservar(client, libro.id, "B2", sur)
    datos.lector("C3")
    _reservar(client, libro.id, "C3", norte)
    en(client, norte).post(CHECKIN, json={"codigo_barras": "B-001"})
    traslado = db.query(models.Traslado).one()

    r = client.post(f"{TRASLADOS}/{traslado.id}/cancel")

    assert r.json()["status"] == "Cancelado"
    beto = db.get(models.Reserva, beto_id)
    assert (beto.estado, beto.prioridad, beto.item_id) == ("Pendiente", 1, None)
    db.refresh(item)
    assert (item.estado, item.biblioteca_actual_id) == ("Disponible", norte.id)
    # Queda para sacar del estante en Norte.
    por_sacar = en(client, norte).get("/api/v1/circulation/holds/to-pull").json()
    assert [t["firstPatronId"] for t in por_sacar] == ["B2"]
    assert client.post(f"{TRASLADOS}/{traslado.id}/cancel").status_code == 400


def test_si_aparece_en_otra_sede_se_reencamina(client, datos, db, sedes):
    norte, sur, este = sedes
    libro, item, *_ = _prestado_en_norte(datos, sedes)
    reserva_id = _reservar(client, libro.id, "B2", sur)
    en(client, norte).post(CHECKIN, json={"codigo_barras": "B-001"})

    r = en(client, este).post(CHECKIN, json={"codigo_barras": "B-001"})

    assert r.json()["accion"] == "transito"
    viejo, nuevo = db.query(models.Traslado).order_by(models.Traslado.id).all()
    assert viejo.estado == "Cancelado" and "Sede Este" in viejo.comentario
    assert (nuevo.desde_id, nuevo.hacia_id, nuevo.estado) == (este.id, sur.id, "Enviado")
    assert db.get(models.Reserva, reserva_id).estado == "EnTransito"


def test_reserva_vencida_cuyo_siguiente_retira_en_otra_sede(client, datos, db, sedes):
    norte, sur, _ = sedes
    libro, item, *_ = _prestado_en_norte(datos, sedes)
    datos.lector("C3")
    _reservar(client, libro.id, "B2", norte)
    _reservar(client, libro.id, "C3", sur)
    en(client, norte).post(CHECKIN, json={"codigo_barras": "B-001"})
    db.query(models.Reserva).filter_by(estado="EnEspera").one().fecha_expiracion = \
        ahora() - timedelta(minutes=1)
    db.flush()

    client.post("/api/v1/circulation/holds/expire")

    # Nadie lo tiene en la mano: queda por enviar en Norte.
    por_enviar = en(client, norte).get(f"{TRASLADOS}?vista=por_enviar").json()
    assert [(t["barcode"], t["to"], t["status"]) for t in por_enviar] == \
        [("B-001", "Sede Sur", "Solicitado")]
    db.refresh(item)
    assert item.estado == "EnTransito"

    enviado = client.post(f"{TRASLADOS}/{por_enviar[0]['id']}/send")
    assert enviado.json()["status"] == "Enviado"
    assert client.post(f"{TRASLADOS}/{por_enviar[0]['id']}/send").status_code == 400


def test_escanear_en_origen_un_traslado_por_enviar_lo_marca_enviado(client, datos, db, sedes):
    norte, sur, _ = sedes
    libro, *_ = _prestado_en_norte(datos, sedes)
    datos.lector("C3")
    _reservar(client, libro.id, "B2", norte)
    _reservar(client, libro.id, "C3", sur)
    en(client, norte).post(CHECKIN, json={"codigo_barras": "B-001"})
    db.query(models.Reserva).filter_by(estado="EnEspera").one().fecha_expiracion = \
        ahora() - timedelta(minutes=1)
    db.flush()
    client.post("/api/v1/circulation/holds/expire")

    r = en(client, norte).post(CHECKIN, json={"codigo_barras": "B-001"})

    assert r.json()["accion"] == "transito" and r.json()["traslado"]["enviado"]
    assert db.query(models.Traslado).one().estado == "Enviado"


def test_cancelar_la_reserva_en_transito(client, datos, db, sedes):
    norte, sur, _ = sedes
    libro, item, *_ = _prestado_en_norte(datos, sedes)
    reserva_id = _reservar(client, libro.id, "B2", sur)
    en(client, norte).post(CHECKIN, json={"codigo_barras": "B-001"})

    assert client.delete(f"/api/v1/circulation/holds/{reserva_id}").status_code == 200

    # Ya iba en camino: sigue viaje y al llegar queda disponible en Sur.
    assert db.query(models.Traslado).one().estado == "Enviado"
    r = en(client, sur).post(CHECKIN, json={"codigo_barras": "B-001"})
    assert r.json()["accion"] == "disponible"
    db.refresh(item)
    assert (item.estado, item.biblioteca_actual_id) == ("Disponible", sur.id)


def test_no_se_presta_un_ejemplar_en_transito(client, datos, sedes):
    norte, sur, _ = sedes
    libro, *_ = _prestado_en_norte(datos, sedes)
    _reservar(client, libro.id, "B2", sur)
    en(client, norte).post(CHECKIN, json={"codigo_barras": "B-001"})

    r = client.post("/api/v1/circulation/checkout",
                    json={"codigo_barras": "B-001", "nro_carnet": "B2"})

    assert r.status_code == 400
    assert "en tránsito hacia Sede Sur" in r.json()["detail"]


def test_traslado_manual(client, datos, db, sedes):
    norte, sur, _ = sedes
    libro = datos.titulo()
    item = datos.ejemplar(libro, "M-1", sede=norte)
    datos.ejemplar(libro, "M-2", sede=norte, estado="Prestado")

    r = en(client, norte).post(TRASLADOS, json={"codigo_barras": "M-1", "hacia_id": sur.id,
                                                "comentario": "Exposición"})
    assert r.status_code == 201, r.text
    assert (r.json()["reason"], r.json()["status"], r.json()["comment"]) == \
        ("manual", "Enviado", "Exposición")

    prestado = client.post(TRASLADOS, json={"codigo_barras": "M-2", "hacia_id": sur.id})
    assert prestado.status_code == 400 and "disponibles" in prestado.json()["detail"]
    mismo = client.post(TRASLADOS, json={"codigo_barras": "M-1", "hacia_id": sur.id})
    assert mismo.status_code == 400

    recibido = en(client, sur).post(f"{TRASLADOS}/{r.json()['id']}/receive").json()
    # Se queda en Sur: no vuelve a Norte apenas llega.
    assert recibido["resultado"]["accion"] == "disponible"
    db.refresh(item)
    assert (item.estado, item.biblioteca_actual_id) == ("Disponible", sur.id)
    historial = en(client, sur).get(f"{TRASLADOS}?vista=historial").json()
    assert [t["status"] for t in historial] == ["Recibido"]


def test_sede_de_trabajo_desconocida_usa_la_del_personal(como, db, sedes):
    _norte, sur, _ = sedes
    cliente = como(["circulacion"], carnet="S-1")
    db.query(models.Usuario).filter_by(nro_carnet="S-1").one().biblioteca_id = sur.id
    db.flush()
    cliente.headers["X-Shelfie-Sede"] = "999"

    assert cliente.get(f"{TRASLADOS}/summary").json()["sede_id"] == sur.id


def test_prestar_otra_copia_anula_el_traslado_que_no_salio(client, datos, db, sedes):
    """M3: la reserva en tránsito se cumple con otra copia; la primera ya no viaja."""
    from app.services import traslados
    norte, sur, _ = sedes
    beto = datos.lector("B2")
    libro = datos.titulo()
    viajero = datos.ejemplar(libro, "B-001", sede=norte)
    datos.ejemplar(libro, "B-002", sede=norte)
    reserva_id = _reservar(client, libro.id, "B2", sur)
    traslados.ubicar(db, viajero, norte.id, en_mano=False)
    db.commit()
    assert db.get(models.Reserva, reserva_id).estado == "EnTransito"
    assert db.query(models.Traslado).one().estado == "Solicitado"

    r = en(client, norte).post("/api/v1/circulation/checkout",
                               json={"codigo_barras": "B-002", "nro_carnet": beto.nro_carnet})

    assert r.status_code in (200, 201), r.text
    assert db.get(models.Reserva, reserva_id).estado == "Cumplida"
    assert db.query(models.Traslado).one().estado == "Cancelado"
    db.refresh(viajero)
    assert (viajero.estado, viajero.biblioteca_actual_id) == ("Disponible", norte.id)


def test_recibir_solo_desde_destino_y_no_cancelar_lo_que_va_en_camino(client, datos, db, sedes):
    """B2: el mostrador que no tiene el ejemplar no lo recibe ni lo «devuelve» al origen."""
    norte, sur, este = sedes
    libro, item, *_ = _prestado_en_norte(datos, sedes)
    _reservar(client, libro.id, "B2", sur)
    en(client, norte).post(CHECKIN, json={"codigo_barras": "B-001"})
    traslado = db.query(models.Traslado).one()

    r = en(client, este).post(f"{TRASLADOS}/{traslado.id}/receive")
    assert r.status_code == 400 and "Sede Sur" in r.json()["detail"]
    r = en(client, sur).post(f"{TRASLADOS}/{traslado.id}/cancel")
    assert r.status_code == 400 and "en camino" in r.json()["detail"]
    db.refresh(item)
    assert item.estado == "EnTransito"
    assert en(client, sur).post(f"{TRASLADOS}/{traslado.id}/receive").status_code == 200
