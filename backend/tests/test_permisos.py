"""Quién puede hacer qué: sin sesión, personal y los dos perfiles (administrador y catalogador)."""

import pytest

# Todas las rutas de intranet: sin sesión deben responder 401.
RUTAS_INTRANET = [
    ("GET", "/api/v1/catalog/items"),
    ("POST", "/api/v1/catalog/items"),
    ("GET", "/api/v1/catalog/search"),
    ("POST", "/api/v1/catalog/records"),
    ("GET", "/api/v1/settings"),
    ("PUT", "/api/v1/settings"),
    ("GET", "/api/v1/staff"),
    ("PUT", "/api/v1/staff/1001"),
    ("GET", "/api/v1/logs"),
    ("PUT", "/api/v1/logs/settings"),
]


@pytest.mark.parametrize("metodo,ruta", RUTAS_INTRANET)
def test_intranet_exige_sesion(anonimo, metodo, ruta):
    assert anonimo.request(metodo, ruta, json={}).status_code == 401


def test_raiz_es_publica(anonimo):
    assert anonimo.get("/").status_code == 200


def test_personal_sin_permisos_consulta_pero_no_modifica(como, datos):
    consulta = como([])
    assert consulta.get("/api/v1/catalog/items").status_code == 200
    assert consulta.get("/api/v1/staff").status_code == 200

    r = consulta.post("/api/v1/catalog/items", json={"titulo": "T", "codigo_barras": "B"})
    assert r.status_code == 403
    assert "catalogo" in r.json()["detail"]


@pytest.mark.parametrize("permiso,metodo,ruta,cuerpo", [
    ("catalogo", "POST", "/api/v1/catalog/items", {"titulo": "T", "codigo_barras": "B"}),
    ("catalogo", "POST", "/api/v1/catalog/records", {"plantilla": "BKS", "marc": {}}),
    ("superbibliotecario", "PUT", "/api/v1/settings", {}),
    ("superbibliotecario", "GET", "/api/v1/logs", None),
    ("superbibliotecario", "PUT", "/api/v1/logs/settings", {}),
])
def test_cada_ruta_exige_su_permiso(como, permiso, metodo, ruta, cuerpo):
    sin_permiso = como(["catalogo"] if permiso != "catalogo" else [])
    con_permiso = como([permiso])

    assert sin_permiso.request(metodo, ruta, json=cuerpo).status_code == 403
    # Con el permiso pasa la barrera (puede fallar después por datos: 400/404, nunca 401/403).
    assert con_permiso.request(metodo, ruta, json=cuerpo).status_code not in (401, 403)


def test_rutas_de_admin_rechazan_catalogador(como):
    catalogador = como(["catalogo"])
    assert catalogador.put("/api/v1/settings", json={}).status_code == 403
    assert catalogador.get("/api/v1/logs").status_code == 403


def test_superbibliotecario_accede_a_todo(client):
    for ruta in ("/api/v1/catalog/items", "/api/v1/settings", "/api/v1/staff", "/api/v1/logs"):
        assert client.get(ruta).status_code == 200


def test_escritura_desde_origen_ajeno_es_rechazada(como):
    cliente = como(["superbibliotecario"])
    ajeno = cliente.put("/api/v1/settings", json={}, headers={"Origin": "https://malicioso.example"})
    propio = cliente.put("/api/v1/settings", json={}, headers={"Origin": "http://localhost:3000"})
    lectura = cliente.get("/api/v1/settings", headers={"Origin": "https://malicioso.example"})

    assert ajeno.status_code == 403
    assert propio.status_code == 200
    assert lectura.status_code == 200  # las lecturas no cambian nada


def test_login_desde_origen_ajeno_es_rechazado(anonimo, datos):
    datos.personal("1001", ["catalogo"])
    r = anonimo.post("/api/v1/auth/login", json={"username": "1001", "password": "1001"},
                     headers={"Origin": "https://malicioso.example"})
    assert r.status_code == 403


# --- Gestión de permisos -------------------------------------------------------

def test_catalogo_de_permisos_y_perfiles(client):
    c = client.get("/api/v1/staff/permissions").json()
    assert {p["codigo"] for p in c["permisos"]} == {"catalogo", "superbibliotecario"}
    perfiles = {p["codigo"]: p["permisos"] for p in c["perfiles"]}
    assert perfiles == {"administrador": ["superbibliotecario"], "catalogador": ["catalogo"]}


def test_superbibliotecario_asigna_permisos(client, datos, anonimo):
    datos.lector("2001")
    r = client.put("/api/v1/staff/2001",
                   json={"es_personal": True, "permisos": ["superbibliotecario", "catalogo", "catalogo"]})
    assert r.status_code == 200, r.text
    assert r.json()["permisos"] == ["catalogo", "superbibliotecario"]  # normalizados

    assert anonimo.post("/api/v1/auth/login",
                        json={"username": "2001", "password": "2001"}).status_code == 200
    assert {p["nro_carnet"] for p in client.get("/api/v1/staff").json()} == {"ADMIN", "2001"}


def test_quitar_acceso_vacia_los_permisos(client, datos):
    datos.personal("2001", ["catalogo"])
    r = client.put("/api/v1/staff/2001", json={"es_personal": False, "permisos": ["catalogo"]})
    assert r.json()["es_personal"] is False
    assert r.json()["permisos"] == []


@pytest.mark.parametrize("permiso", ["volar", "circulacion", "configuracion", "registro"])
def test_permiso_desconocido_es_rechazado(client, datos, permiso):
    datos.lector("2001")
    r = client.put("/api/v1/staff/2001", json={"es_personal": True, "permisos": [permiso]})
    assert r.status_code == 400


def test_solo_superbibliotecario_gestiona_permisos(como, datos):
    datos.lector("2001")
    catalogador = como(["catalogo"])
    r = catalogador.put("/api/v1/staff/2001", json={"es_personal": True, "permisos": ["catalogo"]})
    assert r.status_code == 403


def test_nadie_se_quita_a_si_mismo_el_superbibliotecario(client):
    r = client.put("/api/v1/staff/ADMIN", json={"es_personal": True, "permisos": ["catalogo"]})
    assert r.status_code == 400
    assert "propio" in r.json()["detail"]
