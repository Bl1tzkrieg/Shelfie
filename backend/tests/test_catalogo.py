
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


def test_titulo_inexistente_da_404(client, datos):
    assert client.get("/api/v1/catalog/items/999999").status_code == 404
    assert client.get("/api/v1/catalog/items/999999/ejemplares").status_code == 404
