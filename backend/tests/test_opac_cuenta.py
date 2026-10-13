"""OPAC: sesión del lector, su cuenta (préstamos, reservas, multas, historial,
sugerencias, listas) y la ficha pública con disponibilidad por sede."""

from decimal import Decimal

import jwt
import pytest
from fastapi.testclient import TestClient

from app import models
from app.config import settings
from app.database import get_db
from app.main import app
from app.security import COOKIE_OPAC, COOKIE_SESION
from app.services import cuentas

OPAC = "/api/v1/opac"
CUENTA = f"{OPAC}/account"


@pytest.fixture(autouse=True)
def calendario_abierto(datos):
    datos.sin_dias_cerrados()


@pytest.fixture()
def entrar(db, datos):
    """Fábrica de clientes con sesión del OPAC: entrar("1001") crea el lector si no existe."""
    app.dependency_overrides[get_db] = lambda: db
    abiertos = []

    def _entrar(carnet="1001", **extra):
        if not db.query(models.Usuario).filter_by(nro_carnet=carnet).first():
            datos.lector(carnet, **extra)
        cliente = TestClient(app)
        abiertos.append(cliente)
        r = cliente.post(f"{OPAC}/login", json={"username": carnet, "password": carnet})
        assert r.status_code == 200, r.text
        return cliente

    yield _entrar
    for c in abiertos:
        c.close()
    app.dependency_overrides.clear()


# --- Sesión ------------------------------------------------------------------------------

def test_login_del_lector_con_cookie_propia(anonimo, datos):
    datos.lector("1001", nombre="Ana")
    datos.lector("1002", activo=False)

    r = anonimo.post(f"{OPAC}/login", json={"username": "1001", "password": "1001"})
    assert r.status_code == 200
    assert (r.json()["nombre"], r.json()["prestamos"]) == ("Ana", 0)
    assert COOKIE_OPAC in anonimo.cookies and COOKIE_SESION not in anonimo.cookies
    # La sesión del OPAC no abre la intranet.
    assert anonimo.get("/api/v1/auth/me").status_code == 401
    assert anonimo.get("/api/v1/circulation/loans").status_code == 401
    assert anonimo.get(CUENTA).status_code == 200

    assert anonimo.post(f"{OPAC}/logout").status_code == 204
    assert anonimo.get(CUENTA).status_code == 401

    mala = anonimo.post(f"{OPAC}/login", json={"username": "1001", "password": "otra"})
    assert mala.status_code == 401 and "incorrectos" in mala.json()["detail"]
    suspendido = anonimo.post(f"{OPAC}/login", json={"username": "1002", "password": "1002"})
    assert suspendido.status_code == 403


def test_un_token_no_sirve_del_otro_lado(anonimo, client, datos):
    lector = datos.lector("1001")
    from app.security import crear_token_acceso
    # Token del OPAC puesto como sesión de la intranet, y al revés.
    anonimo.cookies.set(COOKIE_SESION, crear_token_acceso(lector, "opac"))
    assert anonimo.get("/api/v1/auth/me").status_code == 401
    anonimo.cookies.clear()
    anonimo.cookies.set(COOKIE_OPAC, crear_token_acceso(lector))
    assert anonimo.get(CUENTA).status_code == 401
    # La sesión del personal tampoco abre el OPAC.
    assert client.get(CUENTA).status_code == 401
    token = jwt.decode(crear_token_acceso(lector, "opac"), settings.SECRET_KEY,
                       algorithms=["HS256"], audience="opac")
    assert token["carnet"] == "1001"


@pytest.mark.parametrize("metodo,ruta", [
    ("GET", CUENTA), ("GET", f"{CUENTA}/loans"), ("POST", f"{CUENTA}/loans/1/renew"),
    ("GET", f"{CUENTA}/holds"), ("POST", f"{CUENTA}/holds"), ("DELETE", f"{CUENTA}/holds/1"),
    ("GET", f"{CUENTA}/charges"), ("GET", f"{CUENTA}/history"),
    ("POST", f"{CUENTA}/suggestions"), ("GET", f"{CUENTA}/lists"),
    ("POST", f"{CUENTA}/password"),
])
def test_la_cuenta_exige_sesion_del_opac(anonimo, metodo, ruta):
    assert anonimo.request(metodo, ruta, json={}).status_code == 401


def test_cambiar_la_contrasena_desde_el_opac(entrar, anonimo):
    lector = entrar("1001")
    r = lector.post(f"{CUENTA}/password", json={"actual": "1001", "nueva": "mi-clave-nueva"})
    assert r.status_code == 204
    assert lector.get(CUENTA).status_code == 200
    assert anonimo.post(f"{OPAC}/login",
                        json={"username": "1001", "password": "mi-clave-nueva"}).status_code == 200


# --- Préstamos ---------------------------------------------------------------------------

def test_prestamos_y_renovacion(entrar, datos, db):
    ana = datos.lector("1001")
    novela = datos.titulo()
    prestamo = datos.prestamo(datos.ejemplar(novela, "A"), ana, dias_desde=2, dias_hasta=7)
    otro = datos.prestamo(datos.ejemplar(datos.titulo("Otro", None), "B"),
                          datos.lector("1002"))
    lector = entrar("1001")

    [p] = lector.get(f"{CUENTA}/loans").json()
    assert (p["titulo"], p["vencido"], p["renovable"], p["renovaciones"]) == \
        ("Cien años de soledad", False, True, 0)
    assert lector.get(CUENTA).json()["prestamos"] == 1

    r = lector.post(f"{CUENTA}/loans/{prestamo.id}/renew")
    assert r.status_code == 200 and r.json()["mensaje"].startswith("Renovado hasta el")
    assert lector.get(f"{CUENTA}/loans").json()[0]["renovaciones"] == 1
    # El préstamo de otro no existe para este lector.
    assert lector.post(f"{CUENTA}/loans/{otro.id}/renew").status_code == 404


def test_no_renovable_dice_por_que(entrar, datos, db):
    ana = datos.lector("1001")
    novela = datos.titulo()
    prestamo = datos.prestamo(datos.ejemplar(novela, "A"), ana)
    lector = entrar("1001")
    db.add(models.Reserva(biblio_id=novela.id, usuario_id=datos.lector("1002").id,
                          prioridad=1, estado="Pendiente"))
    db.flush()

    [p] = lector.get(f"{CUENTA}/loans").json()
    assert (p["renovable"], p["motivo"]) == (False, "Otro lector lo reservó: hay que devolverlo")
    r = lector.post(f"{CUENTA}/loans/{prestamo.id}/renew")
    assert r.status_code == 400 and "reservó" in r.json()["detail"]

    regla = datos.regla_de(datos.est)
    regla.max_renovaciones = 0
    db.flush()
    assert lector.get(f"{CUENTA}/loans").json()[0]["motivo"] == "Este material no se renueva"


def test_renovar_todos(entrar, datos, db):
    ana = datos.lector("1001")
    a = datos.titulo("A", None)
    b = datos.titulo("B", None)
    datos.prestamo(datos.ejemplar(a, "A1"), ana)
    datos.prestamo(datos.ejemplar(b, "B1"), ana)
    db.add(models.Reserva(biblio_id=b.id, usuario_id=datos.lector("1002").id, prioridad=1,
                          estado="Pendiente"))
    db.flush()

    r = entrar("1001").post(f"{CUENTA}/loans/renew-all").json()
    assert r["renovados"] == ["A"]
    assert [x["titulo"] for x in r["no_renovados"]] == ["B"]


def test_deuda_bloquea_renovar_y_reservar(entrar, datos, db):
    ana = datos.lector("1001")
    novela = datos.titulo()
    datos.ejemplar(novela, "A")
    datos.prestamo(datos.ejemplar(datos.titulo("Otro", None), "B"), ana)
    cuentas.registrar(db, ana, "MULTA_ATRASO", Decimal("9.00"))
    lector = entrar("1001")

    resumen = lector.get(CUENTA).json()
    assert (resumen["saldo"], resumen["bloqueado"]) == (9.0, True)
    assert "deuda" in lector.get(f"{CUENTA}/loans").json()[0]["motivo"]
    r = lector.post(f"{CUENTA}/holds", json={"biblio_id": novela.id})
    assert r.status_code == 400 and "deuda" in r.json()["detail"]

    multas = lector.get(f"{CUENTA}/charges").json()
    assert [(m["tipo"], m["monto"]) for m in multas["movimientos"]] == [("MULTA_ATRASO", 9.0)]


def test_historial(entrar, datos):
    ana = datos.lector("1001")
    datos.prestamo(datos.ejemplar(datos.titulo("Leído", None), "A"), ana, devuelto=True)
    datos.prestamo(datos.ejemplar(datos.titulo("Prestado", None), "B"), ana)
    datos.prestamo(datos.ejemplar(datos.titulo("Ajeno", None), "C"), datos.lector("1002"),
                   devuelto=True)

    historial = entrar("1001").get(f"{CUENTA}/history").json()
    assert [h["titulo"] for h in historial] == ["Leído"]


# --- Reservas ----------------------------------------------------------------------------

def test_reservar_suspender_cambiar_sede_y_cancelar(entrar, datos, db):
    norte = datos.sede("NOR", "Sede Norte")
    sur = datos.sede("SUR", "Sede Sur")
    datos.sede("DEP", "Depósito", punto_retiro=False)
    novela = datos.titulo()
    datos.prestamo(datos.ejemplar(novela, "A", sede=norte), datos.lector("1002"))
    lector = entrar("1001")

    r = lector.post(f"{CUENTA}/holds", json={"biblio_id": novela.id,
                                             "biblioteca_retiro_id": norte.id})
    assert r.status_code == 201, r.text
    assert r.json()["mensaje"] == "Reservado. Estás en el turno 1; lo retirarás en Sede Norte."
    [h] = lector.get(f"{CUENTA}/holds").json()
    assert (h["title"], h["status"], h["pickupBranch"]) == \
        ("Cien años de soledad", "Pendiente", "Sede Norte")
    assert "userName" not in h and "itemBarcode" not in h

    otra = lector.post(f"{CUENTA}/holds", json={"biblio_id": novela.id})
    assert otra.status_code == 400

    id_ = h["id"]
    cambiada = lector.patch(f"{CUENTA}/holds/{id_}",
                            json={"biblioteca_retiro_id": sur.id, "suspendida": True}).json()
    assert (cambiada["pickupBranch"], cambiada["suspended"]) == ("Sede Sur", True)
    # No se puede tocar la prioridad ni las notas del personal.
    lector.patch(f"{CUENTA}/holds/{id_}", json={"prioridad": 5, "notas": "x"})
    reserva = db.get(models.Reserva, int(id_))
    assert (reserva.prioridad, reserva.notas) == (1, None)

    # Las sedes donde se puede retirar, para elegir.
    nombres = [s["nombre"] for s in lector.get(f"{OPAC}/branches").json()]
    assert {"Sede Norte", "Sede Sur"} <= set(nombres) and "Depósito" not in nombres

    ajena = entrar("1003")
    assert ajena.delete(f"{CUENTA}/holds/{id_}").status_code == 404
    assert lector.delete(f"{CUENTA}/holds/{id_}").status_code == 204
    assert lector.get(f"{CUENTA}/holds").json() == []


def test_no_se_reserva_lo_que_no_se_presta(entrar, datos):
    referencia = datos.tipo_item("REF", "Referencia", prestable=False)
    diccionario = datos.titulo("Diccionario", None)
    datos.ejemplar(diccionario, "D", tipo=referencia)
    sin_ejemplares = datos.titulo("Sin ejemplares", None)
    lector = entrar("1001")

    for biblio in (diccionario, sin_ejemplares):
        r = lector.post(f"{CUENTA}/holds", json={"biblio_id": biblio.id})
        assert r.status_code == 400 and "no tiene ejemplares" in r.json()["detail"]
    assert lector.post(f"{CUENTA}/holds", json={"biblio_id": 999999}).status_code == 404


def test_reserva_lista_para_retirar_en_el_resumen(entrar, datos, client):
    novela = datos.titulo()
    datos.ejemplar(novela, "A")
    lector = entrar("1001")
    lector.post(f"{CUENTA}/holds", json={"biblio_id": novela.id})
    # El personal la saca del estante y la aparta.
    assert client.post("/api/v1/circulation/checkin", json={"codigo_barras": "A"}).status_code == 200

    resumen = lector.get(CUENTA).json()
    assert (resumen["reservas"], resumen["para_retirar"]) == (1, 1)
    [h] = lector.get(f"{CUENTA}/holds").json()
    assert h["status"] == "EnEspera" and h["pickupBy"]


# --- Sugerencias -------------------------------------------------------------------------

def test_sugerencias_desde_el_opac(entrar, client):
    lector = entrar("1001")
    r = lector.post(f"{CUENTA}/suggestions",
                    json={"titulo": "Rayuela", "autor": "Julio Cortázar",
                          "nro_carnet": "OTRO"})
    assert r.status_code == 201 and r.json()["estado"] == "Pendiente"

    # El personal la ve a nombre del lector y la rechaza con un motivo que él lee.
    [s] = client.get("/api/v1/acquisitions/suggestions").json()
    assert s["carnet"] == "1001"
    client.post(f"/api/v1/acquisitions/suggestions/{s['id']}/reject",
                json={"motivo": "Ya está pedido"})
    [mia] = lector.get(f"{CUENTA}/suggestions").json()
    assert (mia["estado"], mia["motivo"]) == ("Rechazada", "Ya está pedido")

    for i in range(5):
        lector.post(f"{CUENTA}/suggestions", json={"titulo": f"Libro {i}"})
    r = lector.post(f"{CUENTA}/suggestions", json={"titulo": "Uno más"})
    assert r.status_code == 400 and "sin responder" in r.json()["detail"]
    assert entrar("1002").get(f"{CUENTA}/suggestions").json() == []


# --- Listas ------------------------------------------------------------------------------

def test_listas_privadas_y_publicas(entrar, anonimo, datos):
    novela = datos.titulo()
    suelos = datos.titulo("Ciencia del Suelo", None)
    datos.ejemplar(novela, "A")
    lector = entrar("1001", nombre="Ana", apellido="Privado")

    lista = lector.post(f"{CUENTA}/lists", json={"nombre": "Para la tesis"}).json()
    assert (lista["nombre"], lista["publica"], lista["cantidad"]) == ("Para la tesis", False, 0)
    repetida = lector.post(f"{CUENTA}/lists", json={"nombre": "para la TESIS"})
    assert repetida.status_code == 400

    base = f"{CUENTA}/lists/{lista['id']}/titles"
    assert lector.post(base, json={"biblio_id": novela.id}).json()["cantidad"] == 1
    assert lector.post(base, json={"biblio_id": novela.id}).json()["cantidad"] == 1
    lector.post(base, json={"biblio_id": suelos.id})
    [con] = lector.get(f"{CUENTA}/lists?biblio_id={suelos.id}").json()
    assert (con["cantidad"], con["contiene"]) == (2, True)

    # Privada: nadie más la ve.
    assert anonimo.get(f"{OPAC}/lists/{lista['id']}").status_code == 404
    otra = entrar("1002")
    assert otra.get(f"{OPAC}/lists/{lista['id']}").status_code == 404
    assert otra.post(base, json={"biblio_id": novela.id}).status_code == 404
    propia = lector.get(f"{OPAC}/lists/{lista['id']}").json()
    assert propia["propia"] is True and len(propia["titulos"]) == 2

    lector.patch(f"{CUENTA}/lists/{lista['id']}", json={"publica": True})
    publica = anonimo.get(f"{OPAC}/lists/{lista['id']}")
    assert publica.status_code == 200
    assert publica.json()["propia"] is False and publica.json()["autor"] == "Ana"
    assert "Privado" not in publica.text and "1001" not in publica.text
    assert [t["titulo"] for t in publica.json()["titulos"]] == \
        ["Ciencia del Suelo", "Cien años de soledad"]

    assert lector.delete(f"{base}/{suelos.id}").status_code == 204
    assert lector.delete(f"{CUENTA}/lists/{lista['id']}").status_code == 204
    assert lector.get(f"{CUENTA}/lists").json() == []


# --- Ficha y búsqueda públicas ------------------------------------------------------------

def test_ficha_con_disponibilidad_por_sede(anonimo, datos, db):
    norte = datos.sede("NOR", "Sede Norte")
    sur = datos.sede("SUR", "Sede Sur")
    novela = datos.titulo()
    novela.marc_json = {"leader": "", "fields": [
        {"245": {"ind1": "1", "ind2": "0", "subfields": [
            {"a": "Cien años de soledad /"}, {"c": "Gabriel García Márquez."}]}},
        {"264": {"ind1": " ", "ind2": "1", "subfields": [
            {"a": "Buenos Aires :"}, {"b": "Sudamericana,"}, {"c": "1967."}]}},
        {"300": {"ind1": " ", "ind2": " ", "subfields": [{"a": "471 p. ;"}, {"c": "21 cm."}]}},
        {"520": {"ind1": " ", "ind2": " ", "subfields": [{"a": "La historia de los Buendía."}]}},
        {"650": {"ind1": " ", "ind2": "4", "subfields": [{"a": "Novela colombiana."}]}},
    ]}
    datos.prestamo(datos.ejemplar(novela, "A", sede=norte), datos.lector("1001", apellido="Privado"))
    datos.ejemplar(novela, "B", sede=norte)
    datos.ejemplar(novela, "C", sede=sur, estado="Perdido")
    db.flush()

    ficha = anonimo.get(f"{OPAC}/record/{novela.id}").json()
    assert (ficha["editorial"], ficha["lugar"], ficha["descripcion_fisica"]) == \
        ("Sudamericana", "Buenos Aires", "471 p. ; 21 cm.")
    assert ficha["resumen"] == "La historia de los Buendía"
    assert ficha["materias"] == ["Novela colombiana"]
    assert ficha["por_sede"] == [
        {"sede_id": norte.id, "sede": "Sede Norte", "ejemplares": 2, "disponibles": 1},
        {"sede_id": sur.id, "sede": "Sede Sur", "ejemplares": 1, "disponibles": 0}]
    estados = {e["codigo_barras"]: e["estado"] for e in ficha["ejemplares_detalle"]}
    assert estados["A"].startswith("Prestado, vence el ")
    assert (estados["B"], estados["C"]) == ("Disponible", "No disponible")
    assert ficha["reservable"] is True and ficha["reservas"] == 0
    assert "Privado" not in str(ficha)


def test_datos_publicos_de_la_biblioteca(anonimo):
    r = anonimo.get(f"{OPAC}/library").json()
    assert r["nombre"] and isinstance(r["sedes"], list)


def test_busqueda_publica_con_facetas(anonimo, datos):
    novela = datos.titulo()
    datos.prestamo(datos.ejemplar(novela, "A"), datos.lector())
    suelos = datos.titulo("Ciencia del Suelo", "9782222222222", autor="Nyle Brady",
                          ano=2008, materia="Suelos")
    datos.ejemplar(suelos, "B")

    r = anonimo.get(f"{OPAC}/search?materia=Suelos").json()
    assert [x["titulo"] for x in r["resultados"]] == ["Ciencia del Suelo"]
    assert anonimo.get(f"{OPAC}/search?disponible=no").json()["total"] == 1
    assert anonimo.get(f"{OPAC}/search?decada=2000").json()["total"] == 1
    assert anonimo.get(f"{OPAC}/search?tipo=LIB").json()["total"] == 2
    assert r["facetas"]["materias"] == [{"valor": "Suelos", "cantidad": 1}]


def test_renovar_un_vencido_pide_aceptar_el_cargo(entrar, datos, db):
    ana = datos.lector("1001")
    regla = datos.regla_de(datos.est)
    regla.multa_por_dia, regla.dias_gracia, regla.multa_maxima = 1.5, 0, None
    vencido = datos.prestamo(datos.ejemplar(datos.titulo("Vencido", None), "V"), ana,
                             dias_desde=20, dias_hasta=7)  # 13 días de atraso
    datos.prestamo(datos.ejemplar(datos.titulo("Al día", None), "D"), ana)
    lector = entrar("1001")

    filas = {p["titulo"]: p for p in lector.get(f"{CUENTA}/loans").json()}
    assert (filas["Vencido"]["cargo_al_renovar"], filas["Vencido"]["bloquearia"]) == (19.5, True)
    assert (filas["Al día"]["cargo_al_renovar"], filas["Al día"]["bloquearia"]) == (0.0, False)

    # Sin aceptar el cargo no se renueva ni se cobra nada.
    r = lector.post(f"{CUENTA}/loans/{vencido.id}/renew")
    assert r.status_code == 400 and "Bs. 19,50" in r.json()["detail"]
    assert lector.get(CUENTA).json()["saldo"] == 0

    # "Renovar todo" no toca el vencido.
    todo = lector.post(f"{CUENTA}/loans/renew-all").json()
    assert todo["renovados"] == ["Al día"]
    assert todo["no_renovados"][0]["motivo"].startswith("Está vencido")

    r = lector.post(f"{CUENTA}/loans/{vencido.id}/renew", json={"aceptar_cargo": True})
    assert r.status_code == 200 and "Bs. 19,50" in r.json()["mensaje"]
    assert lector.get(CUENTA).json()["saldo"] == 19.5
