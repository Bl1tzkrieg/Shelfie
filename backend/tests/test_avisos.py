"""Fase 7: plantillas, cola de correos, tareas programadas y recuperar la contraseña."""

from datetime import timedelta
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app import models
from app.config import settings
from app.core.tiempo import hoy
from app.main import app
from app.services import avisos, correo, tareas

N = "/api/v1/notices"


@pytest.fixture(autouse=True)
def calendario_abierto(datos):
    datos.sin_dias_cerrados()


@pytest.fixture()
def buzon(tmp_path, monkeypatch):
    """Los correos van a una carpeta propia de la prueba: se pueden leer y contar."""
    monkeypatch.setattr(settings, "CORREO_MODO", "archivo")
    monkeypatch.setattr(settings, "CARPETA_CORREO", str(tmp_path))

    def leer():
        return sorted(p.read_text(encoding="utf-8") for p in Path(tmp_path).glob("*.eml"))
    return leer


def _texto(eml: str) -> str:
    from email import message_from_string, policy
    return message_from_string(eml, policy=policy.default).get_content()


def _enlace(eml: str) -> str:
    return _texto(eml).split("token=")[1].split()[0]


def _cola(db, **filtro):
    return db.query(models.Aviso).filter_by(**filtro).order_by(models.Aviso.id).all()


# --- Plantillas ------------------------------------------------------------------------------

def test_plantillas_por_defecto_editar_y_restablecer(client):
    todas = {p["codigo"]: p for p in client.get(f"{N}/templates").json()}
    assert {"PREAVISO", "VENCIDO", "RESERVA_LISTA", "RESERVA_EXPIRADA", "RECUPERAR_CLAVE",
            "RECLAMO_SERIADA"} == set(todas)
    assert "{titulo}" in todas["RESERVA_LISTA"]["asunto"] and not todas["RESERVA_LISTA"]["modificada"]

    r = client.put(f"{N}/templates/RESERVA_LISTA", json={"asunto": "Ya puedes pasar por {titulo}"})
    assert r.status_code == 200 and r.json()["modificada"]
    previa = client.post(f"{N}/templates/RESERVA_LISTA/preview", json={}).json()
    assert previa["asunto"] == "Ya puedes pasar por Cien años de soledad"

    mal = client.put(f"{N}/templates/RESERVA_LISTA", json={"cuerpo": "Hola {nombre}, {multa}"})
    assert mal.status_code == 400 and "{multa}" in mal.json()["detail"]
    assert client.put(f"{N}/templates/NADA", json={}).status_code == 404

    restablecida = client.put(f"{N}/templates/RESERVA_LISTA", json={"restablecer": True}).json()
    assert restablecida["asunto"] == avisos.TIPOS["RESERVA_LISTA"]["asunto"]


def test_plantilla_desactivada_no_encola(client, datos, db):
    client.put(f"{N}/templates/RESERVA_LISTA", json={"activo": False})
    novela = datos.titulo()
    datos.ejemplar(novela, "A")
    client.post("/api/v1/catalog/reservations", json={"biblio_id": novela.id,
                                                      "nro_carnet": datos.lector("1001").nro_carnet})
    client.post("/api/v1/circulation/checkin", json={"codigo_barras": "A"})
    assert _cola(db, codigo="RESERVA_LISTA") == []


def test_solo_configuracion_edita(como):
    consulta = como(["circulacion"])
    assert consulta.get(f"{N}/templates").status_code == 200
    assert consulta.put(f"{N}/templates/PREAVISO", json={"asunto": "x"}).status_code == 403
    assert consulta.post(f"{N}/tasks/diarias/run").status_code == 403


# --- Reservas ------------------------------------------------------------------------------

def test_reserva_lista_y_expirada_avisan_al_lector(client, datos, db, buzon):
    novela = datos.titulo()
    datos.ejemplar(novela, "A")
    ana = datos.lector("1001", nombre="Ana", email="ana@example.com")
    client.post("/api/v1/catalog/reservations", json={"biblio_id": novela.id, "nro_carnet": "1001"})
    client.post("/api/v1/circulation/checkin", json={"codigo_barras": "A"})
    # Pasar dos veces el ejemplar no repite el aviso.
    client.post("/api/v1/circulation/checkin", json={"codigo_barras": "A"})

    [lista] = _cola(db, codigo="RESERVA_LISTA")
    assert (lista.destinatario, lista.estado) == ("ana@example.com", "Pendiente")
    assert lista.asunto == "Tu reserva está lista: Cien años de soledad"
    assert "Hola, Ana" in lista.cuerpo and "hasta el" in lista.cuerpo

    r = client.post(f"{N}/queue/send").json()
    assert r["ok"] and r["resultado"]["enviados"] == 1
    [eml] = buzon()
    assert "To: ana@example.com" in eml and "Cien años de soledad" in _texto(eml)
    assert _cola(db, codigo="RESERVA_LISTA")[0].estado == "Enviado"

    # Nadie lo retira: al expirar se avisa.
    reserva = db.query(models.Reserva).filter_by(usuario_id=ana.id).one()
    reserva.fecha_expiracion = reserva.fecha_expiracion - timedelta(days=10)
    db.flush()
    assert client.post(f"{N}/tasks/reservas/run").json()["resultado"]["expiradas"] == 1
    [expirada] = _cola(db, codigo="RESERVA_EXPIRADA")
    assert "expiró" in expirada.asunto


# --- Recordatorios y vencidos ------------------------------------------------------------------

def test_recordatorio_de_vencimiento_agrupa_por_lector(client, datos, db):
    client.put(f"{N}/settings", json={"recordatorio_dias_antes": 3})
    ana = datos.lector("1001", email="ana@example.com")
    for codigo in ("A", "B"):
        datos.prestamo(datos.ejemplar(datos.titulo(f"Libro {codigo}", None), codigo), ana,
                       dias_hasta=3)
    datos.prestamo(datos.ejemplar(datos.titulo("Lejano", None), "C"), ana, dias_hasta=10)

    r = client.post(f"{N}/tasks/recordatorios/run").json()
    assert r["resultado"]["encolados"] == 1
    [aviso] = _cola(db, codigo="PREAVISO")
    assert "Libro A" in aviso.cuerpo and "Libro B" in aviso.cuerpo and "Lejano" not in aviso.cuerpo
    assert aviso.asunto == "Tus préstamos vencen en 3 días"
    # Correrla de nuevo el mismo día no duplica.
    client.post(f"{N}/tasks/recordatorios/run")
    assert len(_cola(db, codigo="PREAVISO")) == 1


def test_vencidos_en_los_dias_de_atraso_configurados(client, datos, db):
    client.put(f"{N}/settings", json={"dias_vencido": [7, 1]})
    assert client.get(f"{N}/settings").json()["dias_vencido"] == [1, 7]
    ana, beto = datos.lector("1001"), datos.lector("1002")
    datos.prestamo(datos.ejemplar(datos.titulo("Un día", None), "A"), ana,
                   dias_desde=8, dias_hasta=7)       # 1 día de atraso: toca
    datos.prestamo(datos.ejemplar(datos.titulo("Tres días", None), "B"), beto,
                   dias_desde=10, dias_hasta=7)      # 3 días: no toca hoy
    r = client.post(f"{N}/tasks/vencidos/run").json()["resultado"]
    assert (r["encolados"], r["lectores_con_vencidos"]) == (1, 2)
    [aviso] = _cola(db, codigo="VENCIDO")
    assert aviso.usuario_id == ana.id and "1 día de atraso" in aviso.cuerpo

    assert client.put(f"{N}/settings", json={"dias_vencido": [0]}).status_code == 400


def test_diarias_registran_su_corrida_y_envian(client, datos, buzon):
    datos.prestamo(datos.ejemplar(datos.titulo("Un día", None), "A"),
                   datos.lector("1001", email="a@example.com"), dias_desde=8, dias_hasta=7)
    corrida = client.post(f"{N}/tasks/diarias/run").json()
    assert corrida["ok"] and corrida["origen"] == "manual"
    assert corrida["resultado"]["enviar_cola"]["enviados"] == 1
    assert len(buzon()) == 1
    listado = {t["clave"]: t for t in client.get(f"{N}/tasks").json()["tareas"]}
    assert listado["diarias"]["ultima"]["ok"] is True
    assert client.get(f"{N}/tasks/history").json()[0]["tarea"] == "diarias"
    assert client.post(f"{N}/tasks/nada/run").status_code == 404


def test_planificador_corre_las_diarias_una_vez_al_dia(db, datos, monkeypatch):
    monkeypatch.setattr(settings, "HORA_TAREAS", "00:00")
    assert tareas._toca_diarias(db)
    tareas.ejecutar(db, "diarias", origen="automatica")
    assert not tareas._toca_diarias(db)


# --- Cola: fallos y reintentos ------------------------------------------------------------------

def test_fallo_de_envio_reintenta_y_queda_fallido(client, datos, db, monkeypatch):
    lector = datos.lector("1001")
    avisos.para_lector(db, "VENCIDO", lector, {"prestamos": "- X"})
    db.flush()

    def caido(*_):
        raise correo.CorreoNoEnviado("Servidor caído")
    monkeypatch.setattr(correo, "enviar", caido)
    for _ in range(avisos.MAX_INTENTOS):
        client.post(f"{N}/queue/send")
    [aviso] = _cola(db)
    assert (aviso.estado, aviso.intentos, aviso.error) == ("Fallido", 3, "Servidor caído")
    assert client.get(f"{N}").json()["fallidos"] == 1

    monkeypatch.undo()
    monkeypatch.setattr(settings, "CARPETA_CORREO", str(Path(settings.CARPETA_CORREO)))
    r = client.post(f"{N}/queue/{aviso.id}/retry").json()
    assert r["estado"] == "Enviado"
    assert client.post(f"{N}/queue/{aviso.id}/retry").status_code == 400
    assert client.get(f"{N}/queue?carnet=1001").json()[0]["estado"] == "Enviado"


def test_correo_desactivado_deja_todo_en_la_cola(client, datos, db, monkeypatch):
    monkeypatch.setattr(settings, "CORREO_MODO", "desactivado")
    avisos.para_lector(db, "VENCIDO", datos.lector("1001"), {"prestamos": "- X"})
    db.flush()
    r = client.post(f"{N}/queue/send").json()["resultado"]
    assert r["pendientes"] == 1 and "desactivado" in r["nota"]
    assert client.post(f"{N}/test", json={"destinatario": "x@example.com"}).status_code == 400


def test_correo_de_prueba(client, buzon):
    r = client.post(f"{N}/test", json={"destinatario": "yo@example.com"})
    assert r.status_code == 200 and r.json()["modo"] == "archivo"
    assert "Prueba de correo" in buzon()[0]


# --- Recuperar la contraseña ----------------------------------------------------------------

def test_recuperar_la_contrasena(anonimo, datos, db, buzon):
    datos.lector("1001", email="ana@example.com")
    assert anonimo.post("/api/v1/opac/password/forgot", json={"identificador": "1001"}).status_code == 204
    # Un carnet que no existe responde igual y no manda nada.
    assert anonimo.post("/api/v1/opac/password/forgot", json={"identificador": "NADIE"}).status_code == 204
    [eml] = buzon()
    token = _enlace(eml)
    assert db.query(models.TokenClave).one().token_hash != token  # solo se guarda el hash

    assert anonimo.get(f"/api/v1/opac/password/reset?token={token}").json() == {"nombre": "Ana"}
    corta = anonimo.post("/api/v1/opac/password/reset", json={"token": token, "nueva": "corta"})
    assert corta.status_code == 400
    ok = anonimo.post("/api/v1/opac/password/reset", json={"token": token, "nueva": "clave-nueva-1"})
    assert ok.status_code == 204
    assert anonimo.post("/api/v1/opac/login",
                        json={"username": "1001", "password": "clave-nueva-1"}).status_code == 200
    # El enlace se gasta.
    otra = anonimo.post("/api/v1/opac/password/reset", json={"token": token, "nueva": "otra-clave-2"})
    assert otra.status_code == 400 and "no es válido" in otra.json()["detail"]
    # El aviso de recuperación no aparece en la cuenta del lector.
    assert anonimo.get("/api/v1/opac/account/notices").json() == []


def test_un_enlace_nuevo_anula_el_anterior_y_hay_tope(anonimo, datos, buzon):
    datos.lector("1001")
    for _ in range(5):
        anonimo.post("/api/v1/opac/password/forgot", json={"identificador": "1001"})
    correos = buzon()
    assert len(correos) == 3  # tope por hora
    viejo, nuevo = _enlace(correos[0]), _enlace(correos[-1])
    tokens = {_enlace(c) for c in correos}
    assert len(tokens) == 3
    assert anonimo.get(f"/api/v1/opac/password/reset?token={viejo}").status_code == 400
    assert anonimo.get(f"/api/v1/opac/password/reset?token={nuevo}").status_code == 200
    assert anonimo.get("/api/v1/opac/password/reset?token=inventado-123").status_code == 400


def test_enlace_vencido(anonimo, datos, db, buzon):
    datos.lector("1001")
    anonimo.post("/api/v1/opac/password/forgot", json={"identificador": "1001"})
    token = _enlace(buzon()[0])
    fila = db.query(models.TokenClave).one()
    fila.expira = fila.expira - timedelta(hours=2)
    db.flush()
    assert anonimo.post("/api/v1/opac/password/reset",
                        json={"token": token, "nueva": "clave-nueva-1"}).status_code == 400


# --- Seriadas -------------------------------------------------------------------------------

def test_reclamo_por_correo_al_proveedor(client, db, buzon):
    p = client.post("/api/v1/acquisitions/suppliers",
                    json={"nombre": "Suscripciones Andinas", "email": "reclamos@andinas.example"}).json()
    hace_40 = (hoy() - timedelta(days=40)).isoformat()
    client.post("/api/v1/serials/subscriptions", json={
        "titulo": "Agronomía Tropical", "issn": "0002-192X", "frecuencia_unidad": "mes",
        "numeracion": "Núm. {Y}", "primer_fasciculo": hace_40, "dias_gracia": 10,
        "proveedor_id": p["id"]})

    r = client.post(f"/api/v1/serials/suppliers/{p['id']}/claim").json()
    assert (r["reclamados"], r["destinatario"]) == (1, "reclamos@andinas.example")
    [aviso] = _cola(db, codigo="RECLAMO_SERIADA")
    assert "Agronomía Tropical (ISSN 0002-192X): Núm. 1" in aviso.cuerpo
    assert client.get("/api/v1/serials/issues/late").json()[0]["reclamos"] == 1

    # Automático: apagado no hace nada; encendido no insiste antes de N días.
    assert client.post(f"{N}/tasks/reclamos_seriadas/run").json()["resultado"]["reclamados"] == 0
    client.put(f"{N}/settings", json={"reclamos_automaticos": True, "dias_entre_reclamos": 15})
    assert client.post(f"{N}/tasks/reclamos_seriadas/run").json()["resultado"]["reclamados"] == 0

    sin_correo = client.post("/api/v1/acquisitions/suppliers", json={"nombre": "Sin correo"}).json()
    assert client.post(f"/api/v1/serials/suppliers/{sin_correo['id']}/claim").status_code == 400


# --- OPAC: mis avisos ----------------------------------------------------------------------------

def test_el_lector_ve_sus_avisos(datos, db):
    from app.database import get_db as _get_db
    lector = datos.lector("1001")
    otro = datos.lector("1002")
    avisos.para_lector(db, "VENCIDO", lector, {"prestamos": "- X"})
    avisos.para_lector(db, "VENCIDO", otro, {"prestamos": "- Y"})
    db.flush()
    app.dependency_overrides[_get_db] = lambda: db
    try:
        with TestClient(app) as c:
            c.post("/api/v1/opac/login", json={"username": "1001", "password": "1001"})
            mios = c.get("/api/v1/opac/account/notices").json()
    finally:
        app.dependency_overrides.clear()
    assert [m["tipo"] for m in mios] == ["Préstamo vencido"] and "- X" in mios[0]["cuerpo"]
