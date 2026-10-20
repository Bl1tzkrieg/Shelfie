"""Quién puede hacer qué: sin sesión, personal y los dos perfiles (administrador y catalogador)."""

import pytest

# Todas las rutas de intranet: sin sesión deben responder 401.
RUTAS_INTRANET = [
    ("GET", "/api/v1/books"),
    ("POST", "/api/v1/books"),
    ("POST", "/api/v1/catalog/records"),
    ("PUT", "/api/v1/settings"),
    ("GET", "/api/v1/settings/system-info"),
    ("GET", "/api/v1/staff"),
    ("POST", "/api/v1/staff"),
    ("PUT", "/api/v1/staff/1/role"),
    ("PUT", "/api/v1/staff/1/active"),
    ("POST", "/api/v1/staff/1/password"),
    ("GET", "/api/v1/logs"),
    ("PUT", "/api/v1/logs/settings"),
]


@pytest.mark.parametrize("metodo,ruta", RUTAS_INTRANET)
def test_intranet_exige_sesion(anonimo, metodo, ruta):
    assert anonimo.request(metodo, ruta, json={}).status_code == 401


def test_nombre_de_la_biblioteca_es_publico(anonimo):
    assert anonimo.get("/api/v1/settings").status_code == 200


def test_busqueda_y_ficha_son_publicas(anonimo):
    assert anonimo.get("/api/v1/buscar", params={"q": "x"}).status_code == 200
    assert anonimo.get("/api/v1/buscar/1").status_code == 404


def test_raiz_es_publica(anonimo):
    assert anonimo.get("/").status_code == 200


def test_personal_sin_permisos_consulta_pero_no_modifica(como, datos):
    consulta = como([])
    assert consulta.get("/api/v1/buscar").status_code == 200
    assert consulta.get("/api/v1/staff").status_code == 403

    r = consulta.post("/api/v1/books", json={"ficha": {"cota": "1 X", "titulo": "T"}})
    assert r.status_code == 403
    assert "catalogo" in r.json()["detail"]


@pytest.mark.parametrize("permiso,metodo,ruta,cuerpo", [
    ("catalogo", "GET", "/api/v1/books", None),
    ("catalogo", "POST", "/api/v1/books", {"ficha": {"cota": "1 X", "titulo": "T"}}),
    ("superbibliotecario", "POST", "/api/v1/catalog/records", {"plantilla": "BKS", "marc": {}}),
    ("superbibliotecario", "PUT", "/api/v1/catalog/items/1/marc", {"plantilla": "BKS", "marc": {}}),
    ("superbibliotecario", "GET", "/api/v1/catalog/items/1/marc", None),
    ("superbibliotecario", "PUT", "/api/v1/settings", {}),
    ("superbibliotecario", "GET", "/api/v1/logs", None),
    ("superbibliotecario", "PUT", "/api/v1/logs/settings", {}),
    ("superbibliotecario", "GET", "/api/v1/staff", None),
    ("superbibliotecario", "POST", "/api/v1/staff", {}),
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
    for ruta in ("/api/v1/books", "/api/v1/settings", "/api/v1/staff", "/api/v1/logs"):
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


def test_salir_desde_origen_ajeno_es_rechazado(como):
    cliente = como(["catalogo"])
    r = cliente.post("/api/v1/auth/logout", headers={"Origin": "https://malicioso.example"})
    assert r.status_code == 403
    assert cliente.get("/api/v1/auth/me").status_code == 200  # la sesión sigue abierta
    assert cliente.post("/api/v1/auth/logout",
                        headers={"Origin": "http://localhost:3000"}).status_code == 204


# --- Perfiles ------------------------------------------------------------------

def test_perfiles_administrador_y_catalogador():
    from app.core.permisos import PERFILES, Permiso
    assert {p.value for p in Permiso} == {"catalogo", "superbibliotecario"}
    assert {c: [p.value for p in perfil["permisos"]] for c, perfil in PERFILES.items()} == {
        "administrador": ["superbibliotecario"], "catalogador": ["catalogo"]}


def test_el_editor_marc_es_solo_del_administrador(como, client):
    """§8: /marc es del administrador; el catalogador usa el formulario."""
    catalogador = como(["catalogo"])
    libro = catalogador.post("/api/v1/books", json={"ficha": {"cota": "1 X", "titulo": "T"}})
    assert libro.status_code == 201
    biblio_id = libro.json()["id"]
    marc = client.get(f"/api/v1/catalog/items/{biblio_id}/marc").json()
    cuerpo = {"marc": marc["marc"], "plantilla": marc["plantilla"]}

    assert catalogador.get(f"/api/v1/catalog/items/{biblio_id}/marc").status_code == 403
    assert catalogador.put(f"/api/v1/catalog/items/{biblio_id}/marc", json=cuerpo).status_code == 403
    assert catalogador.post("/api/v1/catalog/records", json=cuerpo).status_code == 403
    assert client.put(f"/api/v1/catalog/items/{biblio_id}/marc", json=cuerpo).status_code == 200
