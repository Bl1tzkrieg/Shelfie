"""Login, sesión por cookie y cierre de sesión."""

from app.security import COOKIE_SESION


def _login(cliente, username, password):
    return cliente.post("/api/v1/auth/login", json={"username": username, "password": password})


def test_login_por_username_sin_distinguir_mayusculas(anonimo, datos):
    datos.personal("ana", ["catalogo"], password="clave-de-ana")
    for identificador in ("ana", "ANA", " Ana "):
        r = _login(anonimo, identificador, "clave-de-ana")
        assert r.status_code == 200, r.text
        assert r.json()["usuario"]["permisos"] == ["catalogo"]
        assert r.json()["usuario"]["rol"] == "catalogador"


def test_la_sesion_va_en_cookie_httponly_y_no_en_el_cuerpo(anonimo, datos):
    datos.personal("1001", ["catalogo"])
    r = _login(anonimo, "1001", "1001")

    assert "access_token" not in r.json()
    cabecera = r.headers["set-cookie"]
    assert cabecera.startswith(f"{COOKIE_SESION}=")
    assert "HttpOnly" in cabecera
    assert "samesite=lax" in cabecera.lower()


def test_login_no_revela_si_el_usuario_existe(anonimo, datos):
    datos.personal("1001", ["catalogo"])
    malo = _login(anonimo, "1001", "otra")
    inexistente = _login(anonimo, "nadie", "otra")
    assert malo.status_code == inexistente.status_code == 401
    assert malo.json()["detail"] == inexistente.json()["detail"]


def test_cuenta_desactivada_no_entra(anonimo, datos):
    datos.personal("1001", ["catalogo"], activo=False)
    r = _login(anonimo, "1001", "1001")
    # Igual que un usuario inexistente: no revela que la cuenta existe.
    assert r.status_code == 401
    assert r.json()["detail"] == _login(anonimo, "nadie", "x").json()["detail"]


def test_me_y_logout(anonimo, datos):
    datos.personal("1001", ["catalogo"])
    assert anonimo.get("/api/v1/auth/me").status_code == 401

    _login(anonimo, "1001", "1001")
    me = anonimo.get("/api/v1/auth/me")
    assert me.status_code == 200
    assert me.json()["username"] == "1001"

    assert anonimo.post("/api/v1/auth/logout").status_code == 204
    assert anonimo.get("/api/v1/auth/me").status_code == 401


def test_cookie_manipulada_es_rechazada(anonimo, datos):
    anonimo.cookies.set(COOKIE_SESION, "basura")
    assert anonimo.get("/api/v1/auth/me").status_code == 401


def test_set_password_ya_no_existe(anonimo):
    r = anonimo.post("/api/v1/auth/set-password", json={"username": "x", "password": "y"})
    assert r.status_code in (404, 405)
