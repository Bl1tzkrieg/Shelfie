"""M9: editar, dar de baja y eliminar ejemplares."""

from app import models

URL = "/api/v1/catalog/items"


def _url(libro, item):
    return f"{URL}/{libro.id}/ejemplares/{item.id}"


def test_corregir_codigo_signatura_tipo_y_sede(client, datos, db):
    sede = datos.sede("NOR", "Sede Norte")
    referencia = datos.tipo_item("REF", "Referencia")
    libro = datos.titulo()
    item = datos.ejemplar(libro, "B-01")
    datos.ejemplar(libro, "B-02")

    r = client.patch(_url(libro, item), json={
        "codigo_barras": " B-001 ", "signatura_topografica": "863 G16",
        "tipo_item_codigo": "REF", "biblioteca_propia_id": sede.id, "precio_reposicion": 30})

    assert r.status_code == 200, r.text
    fila = next(e for e in r.json() if e["id"] == str(item.id))
    assert (fila["barcode"], fila["location"], fila["homeBranch"]) == ("B-001", "863 G16", "Sede Norte")
    db.refresh(item)
    assert item.tipo_item_id == referencia.id
    assert float(item.precio_reposicion) == 30
    repetido = client.patch(_url(libro, item), json={"codigo_barras": "B-02"})
    assert repetido.status_code == 400 and "B-02" in repetido.json()["detail"]
    assert client.patch(_url(libro, item), json={"tipo_item_codigo": "NO"}).status_code == 400
    assert client.patch(_url(libro, item), json={"biblioteca_propia_id": 999}).status_code == 400


def test_dar_de_baja_y_reincorporar(client, datos, db):
    libro = datos.titulo()
    item = datos.ejemplar(libro)

    assert client.patch(_url(libro, item), json={"estado": "Retirado"}).status_code == 200
    db.refresh(item)
    assert item.estado == "Retirado"

    assert client.patch(_url(libro, item), json={"estado": "Disponible"}).status_code == 200
    db.refresh(item)
    assert item.estado == "Disponible"
    assert client.patch(_url(libro, item), json={"estado": "Prestado"}).status_code == 422


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
