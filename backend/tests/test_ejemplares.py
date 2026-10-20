"""M9: editar y eliminar ejemplares."""

from app import models

URL = "/api/v1/catalog/items"


def _url(libro, item):
    return f"{URL}/{libro.id}/ejemplares/{item.id}"


def test_corregir_codigo_signatura_copia_y_nota(client, datos, db):
    libro = datos.titulo()
    item = datos.ejemplar(libro, "B-01")
    datos.ejemplar(libro, "B-02")

    r = client.patch(_url(libro, item), json={
        "codigo_barras": " B-001 ", "signatura_topografica": "863 G16",
        "numero_copia": "c.1", "nota": "Dedicado por el autor"})

    assert r.status_code == 200, r.text
    fila = next(e for e in r.json() if e["id"] == str(item.id))
    assert (fila["barcode"], fila["location"], fila["copy"], fila["note"]) == (
        "B-001", "863 G16", "c.1", "Dedicado por el autor")
    repetido = client.patch(_url(libro, item), json={"codigo_barras": "B-02"})
    assert repetido.status_code == 409 and "B-02" in repetido.json()["detail"]

    # El código es opcional: vaciarlo lo quita.
    assert client.patch(_url(libro, item), json={"codigo_barras": ""}).status_code == 200
    db.refresh(item)
    assert item.codigo_barras is None


def test_eliminar_ejemplar_cargado_por_error(client, datos, db):
    libro = datos.titulo()
    error = datos.ejemplar(libro, "TIPEO")
    otro_ejemplar = datos.ejemplar(libro, "OTRO")

    assert client.delete(_url(libro, error)).status_code == 204
    assert db.query(models.Item).filter_by(codigo_barras="TIPEO").first() is None
    otro = datos.titulo("Otro", isbn=None)
    assert client.delete(f"{URL}/{otro.id}/ejemplares/{otro_ejemplar.id}").status_code == 404


def test_editar_exige_permiso_de_catalogo(como, datos):
    libro = datos.titulo()
    item = datos.ejemplar(libro)
    sin_permiso = como([])
    assert sin_permiso.patch(_url(libro, item), json={"signatura_topografica": "X"}).status_code == 403
    assert sin_permiso.delete(_url(libro, item)).status_code == 403
