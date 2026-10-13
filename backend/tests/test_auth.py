"""Login, sesión por cookie y cierre de sesión."""

from app.security import COOKIE_SESION


def _login(cliente, username, password):
    return cliente.post("/api/v1/auth/login", json={"username": username, "password": password})


def test_login_por_username_o_carnet(anonimo, datos):
    datos.personal("1001", ["circulacion"], username="ana")
    for identificador in ("ana", "1001"):
        r = _login(anonimo, identificador, "1001")
        assert r.status_code == 200, r.text
        assert r.json()["usuario"]["permisos"] == ["circulacion"]


def test_la_sesion_va_en_cookie_httponly_y_no_en_el_cuerpo(anonimo, datos):
    datos.personal("1001", ["circulacion"])
    r = _login(anonimo, "1001", "1001")

    assert "access_token" not in r.json()
    cabecera = r.headers["set-cookie"]
    assert cabecera.startswith(f"{COOKIE_SESION}=")
    assert "HttpOnly" in cabecera
    assert "samesite=lax" in cabecera.lower()


def test_login_no_revela_si_el_usuario_existe(anonimo, datos):
    datos.personal("1001", ["circulacion"])
    malo = _login(anonimo, "1001", "otra")
    inexistente = _login(anonimo, "nadie", "otra")
    assert malo.status_code == inexistente.status_code == 401
    assert malo.json()["detail"] == inexistente.json()["detail"]


def test_lector_y_cuenta_suspendida_no_entran(anonimo, datos):
    datos.lector("2001")
    datos.personal("1001", ["circulacion"], activo=False)
    assert _login(anonimo, "2001", "2001").status_code == 403
    assert _login(anonimo, "1001", "1001").status_code == 403


def test_me_y_logout(anonimo, datos):
    datos.personal("1001", ["catalogo"])
    assert anonimo.get("/api/v1/auth/me").status_code == 401

    _login(anonimo, "1001", "1001")
    me = anonimo.get("/api/v1/auth/me")
    assert me.status_code == 200
    assert me.json()["nro_carnet"] == "1001"

    assert anonimo.post("/api/v1/auth/logout").status_code == 204
    assert anonimo.get("/api/v1/auth/me").status_code == 401


def test_cookie_manipulada_es_rechazada(anonimo, datos):
    anonimo.cookies.set(COOKIE_SESION, "basura")
    assert anonimo.get("/api/v1/auth/me").status_code == 401


def test_suspender_a_alguien_corta_su_sesion(client, como, datos, db):
    auxiliar = como(["circulacion"], carnet="AUX")
    assert auxiliar.get("/api/v1/circulation/loans").status_code == 200

    client.patch("/api/v1/users/AUX/status", json={"activo": False})
    assert auxiliar.get("/api/v1/circulation/loans").status_code == 401


def test_set_password_ya_no_existe(anonimo):
    r = anonimo.post("/api/v1/auth/set-password", json={"username": "x", "password": "y"})
    assert r.status_code in (404, 405)
