import pytest

from app import models

NUEVO = {
    "titulo": "Fisiología Vegetal",
    "autor": "Lincoln Taiz",
    "isbn": "9781111111111",
    "ano_publicacion": 2010,
    "materia": "Fitotecnia",
    "codigo_barras": "N-001",
    "signatura_topografica": "QK711.2",
}


def test_catalogo_agrupa_por_titulo_con_disponibilidad(client, datos):
    libro = datos.titulo()
    datos.ejemplar(libro, "A", estado="Prestado")
    datos.ejemplar(libro, "B")

    [fila] = client.get("/api/v1/catalog/items").json()

    assert fila["copies"] == 2
    assert fila["available"] == 1
    assert fila["holds"] == 0
    assert fila["availableBarcode"] == "B"
    assert fila["type"] == "Libro"
    assert fila["category"] == "Literatura"
    assert fila["year"] == 1967


def test_titulo_sin_ejemplares_libres_no_expone_barcode(client, datos):
    datos.ejemplar(datos.titulo(), estado="Prestado")
    [fila] = client.get("/api/v1/catalog/items").json()
    assert fila["available"] == 0
    assert fila["availableBarcode"] is None


def test_alta_de_material_crea_registro_y_ejemplar(client, datos, db):
    r = client.post("/api/v1/catalog/items", json=NUEVO)

    assert r.status_code == 201, r.text
    assert r.json()["copies"] == 1
    biblio = db.query(models.RegistroBibliografico).one()
    etiquetas = [list(f)[0] for f in biblio.marc_json["fields"]]
    # El alta rápida arma un MARC completo con lo que se cargó en el formulario.
    assert etiquetas == ["008", "020", "100", "245", "264", "650"]
    assert (biblio.titulo, biblio.autor, biblio.ano_publicacion, biblio.plantilla) == (
        "Fisiología Vegetal", "Lincoln Taiz", 2010, "BKS")


def test_alta_con_isbn_existente_suma_ejemplar(client, datos, db):
    client.post("/api/v1/catalog/items", json=NUEVO)
    r = client.post("/api/v1/catalog/items", json={**NUEVO, "codigo_barras": "N-002"})

    assert r.json()["copies"] == 2
    assert db.query(models.RegistroBibliografico).count() == 1


def test_alta_rechaza_barcode_duplicado_y_tipo_inexistente(client, datos):
    client.post("/api/v1/catalog/items", json=NUEVO)
    assert client.post("/api/v1/catalog/items", json=NUEVO).status_code == 400
    r = client.post("/api/v1/catalog/items",
                    json={**NUEVO, "codigo_barras": "X", "tipo_item_codigo": "ZZZ"})
    assert r.status_code == 400


def test_ficha_y_ejemplares_de_un_titulo(client, datos):
    lector = datos.lector(nombre="Luis", apellido="Mora")
    libro = datos.titulo()
    datos.prestamo(datos.ejemplar(libro, "A"), lector)
    datos.ejemplar(libro, "B")

    assert client.get(f"/api/v1/catalog/items/{libro.id}").json()["copies"] == 2
    ejemplares = {e["barcode"]: e for e in
                  client.get(f"/api/v1/catalog/items/{libro.id}/ejemplares").json()}
    assert ejemplares["A"]["borrowedBy"] == "Luis Mora"
    assert ejemplares["A"]["dueDate"] is not None
    assert ejemplares["B"]["borrowedBy"] is None


def test_titulo_inexistente_da_404(client, datos):
    assert client.get("/api/v1/catalog/items/999999").status_code == 404
    assert client.get("/api/v1/catalog/items/999999/ejemplares").status_code == 404


# --- Reservas -------------------------------------------------------------------

def _reservar(client, biblio_id, carnet):
    return client.post("/api/v1/catalog/reservations",
                       json={"biblio_id": biblio_id, "nro_carnet": carnet})


def test_reservas_forman_cola_por_prioridad(client, datos):
    datos.lector("1001")
    datos.lector("1002")
    libro = datos.titulo()

    assert _reservar(client, libro.id, "1001").json()["prioridad"] == 1
    assert _reservar(client, libro.id, "1002").json()["prioridad"] == 2

    cola = client.get("/api/v1/catalog/reservations").json()
    assert [(r["userId"], r["priority"]) for r in cola] == [("1001", 1), ("1002", 2)]


def test_reserva_duplicada_o_invalida_es_rechazada(client, datos):
    datos.lector("1001")
    libro = datos.titulo()
    _reservar(client, libro.id, "1001")

    assert _reservar(client, libro.id, "1001").status_code == 400  # ya tiene una activa
    assert _reservar(client, libro.id, "NO-EXISTE").status_code == 404
    assert _reservar(client, 999999, "1001").status_code == 404


def test_cancelar_reserva(client, datos, db):
    datos.lector("1001")
    libro = datos.titulo()
    reserva_id = _reservar(client, libro.id, "1001").json()["reserva_id"]

    assert client.delete(f"/api/v1/catalog/reservations/{reserva_id}").status_code == 200
    assert db.get(models.Reserva, reserva_id).estado == "Cancelada"
    assert db.get(models.Reserva, reserva_id).fecha_cierre is not None
    assert client.delete("/api/v1/catalog/reservations/999999").status_code == 404


def test_prioridad_no_se_repite_tras_cancelar(client, datos):
    for carnet in ("1001", "1002", "1003"):
        datos.lector(carnet)
    libro = datos.titulo()
    primera = _reservar(client, libro.id, "1001").json()["reserva_id"]
    _reservar(client, libro.id, "1002")
    client.delete(f"/api/v1/catalog/reservations/{primera}")
    _reservar(client, libro.id, "1003")

    pendientes = [r["priority"] for r in client.get("/api/v1/catalog/reservations").json()
                  if r["status"] == "Pendiente"]
    assert len(pendientes) == len(set(pendientes))


def test_estadisticas_del_dashboard(client, datos):
    lector = datos.lector()
    datos.lector("1002", activo=False)
    libro = datos.titulo()
    datos.prestamo(datos.ejemplar(libro, "A"), lector)
    datos.prestamo(datos.ejemplar(libro, "B"), lector, dias_desde=30)
    datos.ejemplar(libro, "C")

    # totalUsers cuenta usuarios activos: el lector y el administrador del cliente.
    assert client.get("/api/v1/catalog/dashboard-stats").json() == {
        "totalItems": 3, "totalUsers": 2, "activeLoans": 2, "overdueLoans": 1,
    }
