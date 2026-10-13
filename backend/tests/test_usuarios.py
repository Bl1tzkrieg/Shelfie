from app import models

NUEVO = {
    "nro_carnet": "3001",
    "nombre": "Carla",
    "apellido": "Rojas",
    "email": "carla@example.com",
    "departamento": "Zootecnia",
}


def test_crear_usuario_con_valores_por_defecto(client, anonimo, datos):
    r = client.post("/api/v1/users", json=NUEVO)

    assert r.status_code == 201, r.text
    cuerpo = r.json()
    assert cuerpo["categoria"]["codigo"] == "EST"
    assert cuerpo["activo"] is True
    assert cuerpo["prestamos_activos_count"] == 0
    assert cuerpo["es_personal"] is False
    # Username derivado del carnet y contraseña inicial = carnet: las credenciales son
    # válidas (403 y no 401) pero un lector no entra a la intranet.
    login = anonimo.post("/api/v1/auth/login", json={"username": "u3001", "password": "3001"})
    assert login.status_code == 403
    malo = anonimo.post("/api/v1/auth/login", json={"username": "u3001", "password": "x"})
    assert malo.status_code == 401


def test_crear_usuario_rechaza_duplicados_y_categoria_invalida(client, datos):
    client.post("/api/v1/users", json=NUEVO)
    assert client.post("/api/v1/users", json=NUEVO).status_code == 400
    assert client.post("/api/v1/users",
                       json={**NUEVO, "nro_carnet": "3002"}).status_code == 400  # email
    r = client.post("/api/v1/users", json={**NUEVO, "nro_carnet": "3003",
                                            "email": "x@example.com", "categoria_codigo": "ZZ"})
    assert r.status_code == 400


def test_email_invalido_da_422(client, datos):
    assert client.post("/api/v1/users", json={**NUEVO, "email": "no-es-email"}).status_code == 422


def test_editar_usuario(client, datos):
    datos.lector("1001")
    r = client.put("/api/v1/users/1001",
                   json={"nombre": "Ana María", "departamento": "Suelos", "categoria_codigo": "DOC"})
    assert r.status_code == 200
    assert r.json()["nombre"] == "Ana María"
    assert r.json()["departamento"] == "Suelos"
    assert r.json()["categoria"]["codigo"] == "DOC"
    assert client.put("/api/v1/users/NO", json={}).status_code == 404


def test_editar_rechaza_email_ajeno(client, datos):
    datos.lector("1001")
    datos.lector("1002")
    r = client.put("/api/v1/users/1001", json={"email": "1002@example.com"})
    assert r.status_code == 400


def test_suspender_exige_no_tener_prestamos(client, datos):
    lector = datos.lector("1001")
    prestamo = datos.prestamo(datos.ejemplar(datos.titulo()), lector)

    r = client.patch("/api/v1/users/1001/status", json={"activo": False})
    assert r.status_code == 400

    prestamo.fecha_devolucion = prestamo.fecha_vencimiento
    r = client.patch("/api/v1/users/1001/status", json={"activo": False})
    assert r.status_code == 200
    assert r.json()["activo"] is False
    assert client.patch("/api/v1/users/1001/status", json={"activo": True}).json()["activo"]


def test_ficha_e_historial_del_lector(client, datos):
    lector = datos.lector("1001")
    libro = datos.titulo()
    datos.prestamo(datos.ejemplar(libro, "A"), lector, dias_desde=1)
    datos.prestamo(datos.ejemplar(libro, "B"), lector, dias_desde=40, devuelto=True)

    ficha = client.get("/api/v1/users/1001").json()
    assert ficha["prestamos_activos_count"] == 1
    assert ficha["total_prestamos_count"] == 2

    historial = client.get("/api/v1/users/1001/loans").json()
    assert [h["bookCode"] for h in historial] == ["A", "B"]  # más reciente primero
    assert client.get("/api/v1/users/NO/loans").status_code == 404


def test_listado_y_categorias(client, datos):
    datos.lector("1001")
    datos.lector("1002")
    carnets = [u["nro_carnet"] for u in client.get("/api/v1/users").json()]
    assert carnets == ["ADMIN", "1001", "1002"]
    assert [c["codigo"] for c in client.get("/api/v1/categories").json()] == ["ADM", "DOC", "EST"]


def test_exportar_padron(client, datos):
    datos.lector("1001")
    r = client.get("/api/v1/users-export")
    assert r.status_code == 200
    assert r.text.startswith("﻿nro_carnet,nombre")
    assert "1001" in r.text


def test_importar_informa_filas_omitidas(client, datos, db):
    datos.lector("1001")
    filas = [
        {**NUEVO},
        {**NUEVO, "nro_carnet": "1001", "email": "otro@example.com"},  # carnet repetido
        {**NUEVO, "nro_carnet": "3005", "email": "z@example.com", "categoria_codigo": "ZZ"},
    ]

    r = client.post("/api/v1/users-import", json=filas).json()

    assert r["creados"] == 1
    assert r["total"] == 3
    assert [o["fila"] for o in r["omitidos"]] == [2, 3]
    assert db.query(models.Usuario).filter_by(nro_carnet="3001").count() == 1
