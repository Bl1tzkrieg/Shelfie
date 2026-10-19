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
    # Sin otro ejemplar prestable, el título ya no se puede reservar.
    datos.lector("L-1")
    r = client.post("/api/v1/catalog/reservations", json={"biblio_id": libro.id, "nro_carnet": "L-1"})
    assert r.status_code == 400
    # Tampoco se presta.
    assert client.post("/api/v1/circulation/checkout",
                       json={"codigo_barras": "B-001", "nro_carnet": "L-1"}).status_code == 400

    assert client.patch(_url(libro, item), json={"estado": "Disponible"}).status_code == 200
    db.refresh(item)
    assert item.estado == "Disponible"
    assert client.patch(_url(libro, item), json={"estado": "Prestado"}).status_code == 422


def test_estados_de_circulacion_no_se_cambian_a_mano(client, datos, db):
    libro = datos.titulo()
    prestado = datos.ejemplar(libro, "P-1")
    perdido = datos.ejemplar(libro, "P-2", estado="Perdido")
    datos.prestamo(prestado, datos.lector("L-1"))
    prestado.estado = "Prestado"
    db.commit()

    r = client.patch(_url(libro, prestado), json={"estado": "Retirado"})
    assert r.status_code == 400 and "circulación" in r.json()["detail"]
    r = client.patch(_url(libro, perdido), json={"estado": "Disponible"})
    assert r.status_code == 400 and "Devoluciones" in r.json()["detail"]
    # Un perdido sí se puede dar de baja, y corregir sus datos.
    assert client.patch(_url(libro, perdido), json={"estado": "Retirado"}).status_code == 200


def test_eliminar_solo_sin_historial(client, datos, db):
    libro = datos.titulo()
    error = datos.ejemplar(libro, "TIPEO")
    usado = datos.ejemplar(libro, "USADO")
    datos.prestamo(usado, datos.lector("L-1"), devuelto=True)

    r = client.delete(_url(libro, usado))
    assert r.status_code == 400 and "Retirado" in r.json()["detail"]
    assert client.delete(_url(libro, error)).status_code == 204
    assert db.query(models.Item).filter_by(codigo_barras="TIPEO").first() is None
    otro = datos.titulo("Otro", isbn=None)
    assert client.delete(f"{URL}/{otro.id}/ejemplares/{usado.id}").status_code == 404


def test_editar_exige_permiso_de_catalogo(como, datos):
    libro = datos.titulo()
    item = datos.ejemplar(libro)
    circulacion = como(["circulacion"])
    assert circulacion.patch(_url(libro, item), json={"signatura_topografica": "X"}).status_code == 403
    assert circulacion.delete(_url(libro, item)).status_code == 403
