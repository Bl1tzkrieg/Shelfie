
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


def test_catalogo_agrupa_por_titulo(client, datos):
    libro = datos.titulo(cota="863 G16")
    datos.ejemplar(libro, "A")
    datos.ejemplar(libro)

    [fila] = client.get("/api/v1/catalog/items").json()

    assert (fila["copies"], fila["available"]) == (2, 2)  # sin circulación, todos en el estante
    assert fila["location"] == "863 G16"
    assert fila["type"] == "Libros"
    assert fila["category"] == "Literatura"
    assert fila["year"] == 1967


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


def test_alta_rechaza_barcode_duplicado_y_acepta_sin_codigo(client, datos, db):
    client.post("/api/v1/catalog/items", json=NUEVO)
    assert client.post("/api/v1/catalog/items", json=NUEVO).status_code == 409
    for vacio in (None, "  "):
        r = client.post("/api/v1/catalog/items", json={**NUEVO, "codigo_barras": vacio})
        assert r.status_code == 201, r.text
    assert db.query(models.Item).filter(models.Item.codigo_barras.is_(None)).count() == 2


def test_titulo_inexistente_da_404(client, datos):
    assert client.get("/api/v1/catalog/items/999999").status_code == 404
    assert client.get("/api/v1/catalog/items/999999/ejemplares").status_code == 404
