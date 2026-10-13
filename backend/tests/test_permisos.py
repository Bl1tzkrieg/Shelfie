"""Quién puede hacer qué: sin sesión, lectores, personal y permisos por módulo."""

import pytest

from app import models

# Todas las rutas de intranet: sin sesión deben responder 401.
RUTAS_INTRANET = [
    ("GET", "/api/v1/catalog/items"),
    ("POST", "/api/v1/catalog/items"),
    ("GET", "/api/v1/catalog/dashboard-stats"),
    ("POST", "/api/v1/catalog/reservations"),
    ("GET", "/api/v1/circulation/loans"),
    ("GET", "/api/v1/circulation/loans/export"),
    ("POST", "/api/v1/circulation/checkout"),
    ("POST", "/api/v1/circulation/checkin"),
    ("POST", "/api/v1/circulation/renew"),
    ("GET", "/api/v1/circulation/holds"),
    ("GET", "/api/v1/circulation/holds/to-pull"),
    ("PATCH", "/api/v1/circulation/holds/1"),
    ("GET", "/api/v1/circulation/transfers"),
    ("POST", "/api/v1/circulation/transfers"),
    ("POST", "/api/v1/circulation/transfers/1/receive"),
    ("GET", "/api/v1/settings/branches"),
    ("POST", "/api/v1/settings/branches"),
    ("GET", "/api/v1/users"),
    ("POST", "/api/v1/users"),
    ("GET", "/api/v1/users-export"),
    ("GET", "/api/v1/categories"),
    ("GET", "/api/v1/settings"),
    ("PUT", "/api/v1/settings"),
    ("GET", "/api/v1/reports/stats"),
    ("GET", "/api/v1/reports/generate?tipo=loans"),
    ("GET", "/api/v1/acquisitions/suppliers"),
    ("GET", "/api/v1/serials/subscriptions"),
    ("GET", "/api/v1/staff"),
    ("PUT", "/api/v1/staff/1001"),
]


@pytest.mark.parametrize("metodo,ruta", RUTAS_INTRANET)
def test_intranet_exige_sesion(anonimo, metodo, ruta):
    assert anonimo.request(metodo, ruta, json={}).status_code == 401


@pytest.mark.parametrize("ruta", [
    "/api/v1/opac/search?q=a", "/api/v1/opac/advanced-search", "/api/v1/opac/subjects", "/",
])
def test_opac_sigue_siendo_publico(anonimo, ruta):
    assert anonimo.get(ruta).status_code == 200


def test_personal_sin_permisos_consulta_pero_no_modifica(como, datos):
    consulta = como([])
    assert consulta.get("/api/v1/circulation/loans").status_code == 200
    assert consulta.get("/api/v1/catalog/items").status_code == 200
    assert consulta.get("/api/v1/users").status_code == 200

    r = consulta.post("/api/v1/circulation/checkout",
                      json={"codigo_barras": "X", "nro_carnet": "Y"})
    assert r.status_code == 403
    assert "circulacion" in r.json()["detail"]


@pytest.mark.parametrize("permiso,metodo,ruta,cuerpo", [
    ("circulacion", "POST", "/api/v1/circulation/checkin", {"codigo_barras": "NO"}),
    ("circulacion", "PATCH", "/api/v1/circulation/holds/999", {"notas": "x"}),
    ("circulacion", "POST", "/api/v1/circulation/transfers", {"codigo_barras": "NO", "hacia_id": 1}),
    ("circulacion", "POST", "/api/v1/circulation/transfers/999/receive", None),
    ("configuracion", "POST", "/api/v1/settings/branches", {"codigo": "X", "nombre": "X"}),
    ("catalogo", "POST", "/api/v1/catalog/items", {"titulo": "T", "codigo_barras": "B"}),
    ("lectores", "PATCH", "/api/v1/users/NADIE/status", {"activo": False}),
    ("configuracion", "PUT", "/api/v1/settings", {}),
    ("reportes", "GET", "/api/v1/reports/stats", None),
    ("adquisiciones", "GET", "/api/v1/acquisitions/orders", None),
    ("adquisiciones", "GET", "/api/v1/acquisitions/budgets", None),
    ("adquisiciones", "POST", "/api/v1/acquisitions/invoices/999/receive", {"linea_id": 1}),
    ("adquisiciones", "POST", "/api/v1/acquisitions/suggestions", {"titulo": "X"}),
    ("seriadas", "GET", "/api/v1/serials/issues/pending", None),
    ("seriadas", "GET", "/api/v1/serials/issues/late", None),
    ("seriadas", "POST", "/api/v1/serials/issues/999/receive", {}),
])
def test_cada_modulo_exige_su_permiso(como, permiso, metodo, ruta, cuerpo):
    sin_permiso = como(["circulacion"] if permiso != "circulacion" else ["catalogo"])
    con_permiso = como([permiso])

    assert sin_permiso.request(metodo, ruta, json=cuerpo).status_code == 403
    # Con el permiso pasa la barrera (puede fallar después por datos: 400/404, nunca 401/403).
    assert con_permiso.request(metodo, ruta, json=cuerpo).status_code not in (401, 403)


def test_superbibliotecario_accede_a_todo(client):
    for ruta in ("/api/v1/reports/stats", "/api/v1/acquisitions/orders",
                 "/api/v1/serials/subscriptions", "/api/v1/staff"):
        assert client.get(ruta).status_code == 200


def test_escritura_desde_origen_ajeno_es_rechazada(como):
    cliente = como(["configuracion"])
    ajeno = cliente.put("/api/v1/settings", json={}, headers={"Origin": "https://malicioso.example"})
    propio = cliente.put("/api/v1/settings", json={}, headers={"Origin": "http://localhost:3000"})
    lectura = cliente.get("/api/v1/settings", headers={"Origin": "https://malicioso.example"})

    assert ajeno.status_code == 403
    assert propio.status_code == 200
    assert lectura.status_code == 200  # las lecturas no cambian nada


def test_login_desde_origen_ajeno_es_rechazado(anonimo, datos):
    datos.personal("1001", ["circulacion"])
    r = anonimo.post("/api/v1/auth/login", json={"username": "1001", "password": "1001"},
                     headers={"Origin": "https://malicioso.example"})
    assert r.status_code == 403


# --- Gestión de permisos -------------------------------------------------------

def test_catalogo_de_permisos_y_perfiles(client):
    c = client.get("/api/v1/staff/permissions").json()
    assert "superbibliotecario" in [p["codigo"] for p in c["permisos"]]
    assert {p["codigo"] for p in c["perfiles"]} == {"administrador", "bibliotecario", "auxiliar"}


def test_superbibliotecario_asigna_permisos(client, datos, anonimo):
    datos.lector("2001")
    r = client.put("/api/v1/staff/2001",
                   json={"es_personal": True, "permisos": ["lectores", "circulacion", "lectores"]})
    assert r.status_code == 200, r.text
    assert r.json()["permisos"] == ["circulacion", "lectores"]  # normalizados

    assert anonimo.post("/api/v1/auth/login",
                        json={"username": "2001", "password": "2001"}).status_code == 200
    assert {p["nro_carnet"] for p in client.get("/api/v1/staff").json()} == {"ADMIN", "2001"}


def test_quitar_acceso_vacia_los_permisos(client, datos):
    datos.personal("2001", ["circulacion"])
    r = client.put("/api/v1/staff/2001", json={"es_personal": False, "permisos": ["circulacion"]})
    assert r.json()["es_personal"] is False
    assert r.json()["permisos"] == []


def test_permiso_desconocido_es_rechazado(client, datos):
    datos.lector("2001")
    r = client.put("/api/v1/staff/2001", json={"es_personal": True, "permisos": ["volar"]})
    assert r.status_code == 400


def test_solo_superbibliotecario_gestiona_permisos(como, datos):
    datos.lector("2001")
    bibliotecario = como(["circulacion", "catalogo", "lectores"])
    r = bibliotecario.put("/api/v1/staff/2001", json={"es_personal": True, "permisos": ["reportes"]})
    assert r.status_code == 403


def test_nadie_se_quita_a_si_mismo_el_superbibliotecario(client):
    r = client.put("/api/v1/staff/ADMIN", json={"es_personal": True, "permisos": ["circulacion"]})
    assert r.status_code == 400
    assert "propio" in r.json()["detail"]


# --- Trazabilidad --------------------------------------------------------------

def test_prestamo_y_devolucion_registran_quien_los_hizo(como, datos, db):
    datos.lector("2001")
    datos.ejemplar(datos.titulo())
    presta = como(["circulacion"], carnet="AUX-1")
    recibe = como(["circulacion"], carnet="AUX-2")

    prestamo_id = presta.post("/api/v1/circulation/checkout",
                              json={"codigo_barras": "B-001", "nro_carnet": "2001"}).json()["id"]
    recibe.post("/api/v1/circulation/checkin", json={"codigo_barras": "B-001"})

    prestamo = db.get(models.Prestamo, prestamo_id)
    db.refresh(prestamo)
    carnet = {u.id: u.nro_carnet for u in db.query(models.Usuario).all()}
    assert carnet[prestamo.personal_prestamo_id] == "AUX-1"
    assert carnet[prestamo.personal_devolucion_id] == "AUX-2"
