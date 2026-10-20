"""Libros (Tarea 5): alta con ejemplares, duplicados, edición, lista por cota y baja."""

from app import models

URL = "/api/v1/books"


def ficha(**cambios):
    base = {"cota": "863 G2", "titulo": "Cien años de soledad",
            "autor": "García Márquez, Gabriel", "isbn": ["9780307474728"], "ano": 1967}
    return {**base, **cambios}


def alta(cliente, ejemplares=1, forzar=False, **cambios):
    r = cliente.post(URL, json={"ficha": ficha(**cambios), "ejemplares": ejemplares,
                                "forzar": forzar})
    assert r.status_code == 201, r.text
    return r.json()


def _acciones(db, **filtro):
    db.expire_all()
    return db.query(models.RegistroAccion).filter_by(**filtro).order_by(
        models.RegistroAccion.id).all()


# --- Alta y duplicados ---------------------------------------------------------------

def test_crear_con_tres_ejemplares(client, db):
    libro = alta(client, ejemplares=3, cota="863  g2")

    assert libro["ficha"]["cota"] == "863 G2"
    assert libro["ficha"]["titulo"] == "Cien años de soledad"
    assert [(e["cota"], e["numero_copia"], e["codigo_barras"]) for e in libro["ejemplares"]] == [
        ("863 G2", "c.1", None), ("863 G2", "c.2", None), ("863 G2", "c.3", None)]
    biblio = db.get(models.RegistroBibliografico, libro["id"])
    # aplicar_marc deriva la cota (092) y la editorial además de título, autor, año e ISBN.
    assert (biblio.cota, biblio.titulo, biblio.isbn) == ("863 G2", "Cien años de soledad",
                                                         "9780307474728")
    assert set(libro) == {"id", "ficha", "ejemplares", "creado_en", "actualizado_en"}


def test_nota_para_todos_los_ejemplares(client):
    libro = alta(client, ejemplares=2, nota_ejemplares=None)
    r = client.post(URL, json={"ficha": ficha(titulo="Otro", isbn=[]), "ejemplares": 2,
                               "nota_ejemplares": "Donación"})
    assert r.status_code == 201
    assert [e["nota"] for e in r.json()["ejemplares"]] == ["Donación", "Donación"]
    assert [e["nota"] for e in libro["ejemplares"]] == [None, None]


def test_aviso_de_duplicado_y_forzar(client):
    primero = alta(client)

    r = client.post(URL, json={"ficha": ficha(titulo="Otra edición", isbn=["978-0-307-47472-8"]),
                               "ejemplares": 1})
    assert r.status_code == 409, r.text
    detalle = r.json()["detail"]
    assert detalle["codigo"] == "POSIBLE_DUPLICADO"
    assert detalle["coincidencias"] == [{"id": primero["id"], "titulo": "Cien años de soledad",
                                         "autor": "García Márquez, Gabriel", "cota": "863 G2"}]

    r = client.post(URL, json={"ficha": ficha(titulo="Otra edición", isbn=["978-0-307-47472-8"]),
                               "ejemplares": 1, "forzar": True})
    assert r.status_code == 201, r.text


def test_duplicado_por_titulo_y_autor_sin_acentos_ni_mayusculas(client, db):
    alta(client, isbn=[])
    r = client.post(URL, json={"ficha": ficha(titulo="CIEN AÑOS DE SOLEDAD", isbn=[],
                                              autor="Garcia Marquez, Gabriel", cota="863 G2a")})
    assert r.status_code == 409
    # Otro autor con el mismo título no es duplicado.
    r = client.post(URL, json={"ficha": ficha(isbn=[], autor="Otro, Autor")})
    assert r.status_code == 201


def test_posibles_duplicados_excluye_el_propio(client, db):
    from app.schemas import FichaLibro
    from app.services import libros
    libro = alta(client)
    f = FichaLibro(**ficha())
    assert [c["id"] for c in libros.posibles_duplicados(db, f)] == [libro["id"]]
    assert libros.posibles_duplicados(db, f, propio_id=libro["id"]) == []


def test_ficha_invalida_da_422(client):
    r = client.post(URL, json={"ficha": ficha(cota="  "), "ejemplares": 1})
    assert r.status_code == 422
    r = client.post(URL, json={"ficha": ficha(ano=10000), "ejemplares": 1})
    assert r.status_code == 422


# --- Ver y editar ---------------------------------------------------------------------

def test_obtener(client):
    libro = alta(client, ejemplares=2, editorial="Sudamericana", lugar="Buenos Aires")
    r = client.get(f"{URL}/{libro['id']}")
    assert r.status_code == 200
    vista = r.json()
    assert vista["ficha"]["editorial"] == "Sudamericana"
    assert set(vista["ejemplares"][0]) == {"id", "cota", "codigo_barras", "numero_copia", "nota"}
    assert client.get(f"{URL}/999999").status_code == 404


def test_editar_cambia_cota_de_ejemplares_que_la_heredaban(client, db):
    libro = alta(client, ejemplares=2)
    propio = client.post(f"{URL}/{libro['id']}/copies", json={"cota": "863 G2 ej. ref"}).json()
    id_propio = next(e["id"] for e in propio["ejemplares"] if e["cota"] == "863 G2 EJ. REF")

    r = client.put(f"{URL}/{libro['id']}", json=ficha(cota="863 g2c", editorial="Sudamericana"))

    assert r.status_code == 200, r.text
    vista = r.json()
    assert vista["ficha"]["cota"] == "863 G2C"
    cotas = {e["id"]: e["cota"] for e in vista["ejemplares"]}
    assert cotas.pop(id_propio) == "863 G2 EJ. REF"
    assert set(cotas.values()) == {"863 G2C"}
    biblio = db.get(models.RegistroBibliografico, libro["id"])
    db.refresh(biblio)
    assert (biblio.cota, biblio.editorial) == ("863 G2C", "Sudamericana")


def test_editar_conserva_el_marc_importado(client, db):
    libro = alta(client)
    biblio = db.get(models.RegistroBibliografico, libro["id"])
    marc = dict(biblio.marc_json)
    marc["fields"] = marc["fields"] + [{"856": {"ind1": "4", "ind2": "0",
                                                "subfields": [{"u": "http://x.example"}]}}]
    biblio.marc_json = marc
    db.commit()

    client.put(f"{URL}/{libro['id']}", json=ficha(titulo="Cien años de soledad (2.ª)"))

    db.refresh(biblio)
    assert any("856" in c for c in biblio.marc_json["fields"])
    assert biblio.titulo == "Cien años de soledad (2.ª)"


def test_lee_un_registro_importado_sin_cota_ni_titulo(client, datos):
    importado = datos.titulo("Sin datos", isbn=None)
    r = client.get(f"{URL}/{importado.id}")
    assert r.status_code == 200
    assert r.json()["ficha"]["cota"] == ""


# --- Lista ---------------------------------------------------------------------------

def test_lista_sin_cota_al_final(client, datos):
    datos.titulo("Importado sin cota", isbn=None)
    alta(client, cota="863 G2")

    r = client.get(URL)
    assert r.status_code == 200
    filas = r.json()["resultados"]
    assert [f["cota"] for f in filas] == ["863 G2", None]
    assert filas[0]["ejemplares"] == 1 and filas[1]["ejemplares"] == 0


def test_lista_ordena_como_el_estante(client):
    for cota, isbn in (("863 G2", "1"), ("92 B", "2"), ("630 R6", "3")):
        alta(client, cota=cota, isbn=[isbn], titulo=f"Libro {cota}")

    filas = client.get(URL).json()["resultados"]
    assert [f["cota"] for f in filas] == ["92 B", "630 R6", "863 G2"]


def test_lista_filtra_y_pagina(client):
    alta(client)
    alta(client, cota="630 R6", isbn=["2"], titulo="Árboles frutales", autor="Rojas, Ana")

    assert [f["titulo"] for f in client.get(URL, params={"q": "arboles"}).json()["resultados"]] \
        == ["Árboles frutales"]
    assert client.get(URL, params={"q": "630 r"}).json()["total"] == 1
    assert client.get(URL, params={"q": "garcia"}).json()["total"] == 1
    assert client.get(URL, params={"q": "100%"}).json()["total"] == 0
    pagina = client.get(URL, params={"pagina": 2, "por_pagina": 1}).json()
    assert (pagina["total"], pagina["paginas"], pagina["pagina"]) == (2, 2, 2)
    assert [f["cota"] for f in pagina["resultados"]] == ["863 G2"]


# --- Ejemplares ----------------------------------------------------------------------

def test_agregar_ejemplar_toma_la_cota_y_la_copia_siguiente(client):
    libro = alta(client, ejemplares=2)
    r = client.post(f"{URL}/{libro['id']}/copies", json={"codigo_barras": " B-9 "})
    assert r.status_code == 201, r.text
    nuevo = r.json()["ejemplares"][-1]
    assert (nuevo["cota"], nuevo["numero_copia"], nuevo["codigo_barras"]) == ("863 G2", "c.3", "B-9")
    assert client.post(f"{URL}/{libro['id']}/copies",
                       json={"codigo_barras": "B-9"}).status_code == 409


def test_ejemplares_en_orden_natural_de_copia(client):
    libro = alta(client, ejemplares=0)
    for copia in ("c.10", "c.2", "c.1"):
        client.post(f"{URL}/{libro['id']}/copies", json={"numero_copia": copia})
    vista = client.get(f"{URL}/{libro['id']}").json()
    assert [e["numero_copia"] for e in vista["ejemplares"]] == ["c.1", "c.2", "c.10"]
    r = client.post(f"{URL}/{libro['id']}/copies", json={})
    assert r.json()["ejemplares"][-1]["numero_copia"] == "c.11"


def test_editar_y_eliminar_ejemplar(client, db):
    libro = alta(client, ejemplares=2)
    [uno, dos] = libro["ejemplares"]
    client.post(f"{URL}/{libro['id']}/copies", json={"codigo_barras": "B-02"})
    ruta = f"{URL}/{libro['id']}/copies/{uno['id']}"

    r = client.patch(ruta, json={"codigo_barras": " B-001 ", "cota": "863  g2 ref",
                                 "numero_copia": "c.9", "nota": "Dedicado por el autor"})
    assert r.status_code == 200, r.text
    fila = next(e for e in r.json()["ejemplares"] if e["id"] == uno["id"])
    assert (fila["codigo_barras"], fila["cota"], fila["numero_copia"], fila["nota"]) == (
        "B-001", "863 G2 REF", "c.9", "Dedicado por el autor")
    repetido = client.patch(ruta, json={"codigo_barras": "B-02"})
    assert repetido.status_code == 409 and "B-02" in repetido.json()["detail"]
    assert client.patch(ruta, json={"codigo_barras": ""}).status_code == 200
    assert db.get(models.Item, uno["id"]).codigo_barras is None

    assert client.delete(ruta).status_code == 204
    assert db.get(models.Item, uno["id"]) is None
    otro = alta(client, titulo="Otro", isbn=[], autor="X")
    assert client.delete(f"{URL}/{otro['id']}/copies/{dos['id']}").status_code == 404


# --- Baja, permisos y registro --------------------------------------------------------

def test_borrar_pide_catalogador(anonimo, como, db):
    admin = como(["superbibliotecario"])
    catalogador = como(["catalogo"])
    uno = alta(admin, ejemplares=2)
    dos = alta(catalogador, titulo="Otro", isbn=[], autor="X")

    assert anonimo.delete(f"{URL}/{uno['id']}").status_code == 401
    assert como([]).delete(f"{URL}/{uno['id']}").status_code == 403
    assert admin.delete(f"{URL}/{uno['id']}").status_code == 204
    assert catalogador.delete(f"{URL}/{dos['id']}").status_code == 204
    assert db.get(models.RegistroBibliografico, uno["id"]) is None
    assert db.query(models.Item).count() == 0
    assert admin.delete(f"{URL}/{uno['id']}").status_code == 404


def test_todas_las_rutas_piden_catalogador(anonimo, como):
    sin_permiso = como([])
    for metodo, ruta in (("GET", URL), ("POST", URL), ("GET", f"{URL}/1"), ("PUT", f"{URL}/1"),
                         ("POST", f"{URL}/1/copies"), ("PATCH", f"{URL}/1/copies/1"),
                         ("DELETE", f"{URL}/1/copies/1")):
        assert anonimo.request(metodo, ruta, json={}).status_code == 401, ruta
        assert sin_permiso.request(metodo, ruta, json={}).status_code == 403, ruta


def test_registra_acciones(client, db):
    libro = alta(client, ejemplares=2)
    client.put(f"{URL}/{libro['id']}", json=ficha(cota="863 G2b"))
    agregado = client.post(f"{URL}/{libro['id']}/copies", json={"codigo_barras": "R-1"}).json()
    item_id = agregado["ejemplares"][-1]["id"]
    client.patch(f"{URL}/{libro['id']}/copies/{item_id}", json={"nota": "Roto"})
    client.delete(f"{URL}/{libro['id']}/copies/{item_id}")
    client.delete(f"{URL}/{libro['id']}")

    acciones = _acciones(db, modulo="catalogo")
    assert [a.accion for a in acciones] == ["alta", "edicion", "ejemplar", "ejemplar",
                                            "ejemplar", "baja"]
    alta_, edicion, nuevo, editado, eliminado, baja = acciones
    assert "Cien años de soledad" in alta_.descripcion and "2 ejemplares" in alta_.descripcion
    assert edicion.datos["cambios"]["cota"] == ["863 G2", "863 G2B"]
    assert "marc_anterior" in edicion.datos
    assert editado.datos["cambios"]["nota"] == [None, "Roto"]
    assert "Eliminó el ejemplar R-1" in eliminado.descripcion
    assert baja.datos["marc"] and len(baja.datos["ejemplares"]) == 2
    assert baja.objeto_tipo == "registro" and baja.objeto_id == libro["id"]


# --- Revisión final -----------------------------------------------------------------

def test_duplicado_por_el_segundo_isbn(client):
    alta(client, isbn=["9780307474728", "9788497592208"])
    r = client.post(URL, json={"ficha": ficha(titulo="Otro título", autor="Otro, Autor",
                                              isbn=["978-84-9759-220-8"])})
    assert r.status_code == 409
    assert r.json()["detail"]["codigo"] == "POSIBLE_DUPLICADO"


def test_editor_marc_cambia_la_cota_de_los_ejemplares_que_la_heredaban(client, db):
    libro = alta(client, ejemplares=2)
    propio = client.post(f"{URL}/{libro['id']}/copies", json={"cota": "863 G2 ref"}).json()
    id_propio = next(e["id"] for e in propio["ejemplares"] if e["cota"] == "863 G2 REF")
    marc = client.get(f"/api/v1/catalog/items/{libro['id']}/marc").json()
    for campo in marc["marc"]["fields"]:
        if "092" in campo:
            campo["092"]["subfields"] = [{"a": "999"}, {"b": "Z9"}]

    r = client.put(f"/api/v1/catalog/items/{libro['id']}/marc",
                   json={"marc": marc["marc"], "plantilla": marc["plantilla"]})

    assert r.status_code == 200, r.text
    vista = client.get(f"{URL}/{libro['id']}").json()
    assert vista["ficha"]["cota"] == "999 Z9"
    cotas = {e["id"]: e["cota"] for e in vista["ejemplares"]}
    assert cotas.pop(id_propio) == "863 G2 REF"
    assert set(cotas.values()) == {"999 Z9"}
    [edicion] = [a for a in _acciones(db, modulo="catalogo", accion="edicion")]
    assert sorted(edicion.datos["ejemplares_con_la_cota_nueva"]) == sorted(cotas)


def test_cota_de_mas_de_100_caracteres_da_422(client):
    r = client.post(URL, json={"ficha": ficha(cota="1" * 101), "ejemplares": 1, "forzar": True})
    assert r.status_code == 422, r.text
    libro = alta(client)
    assert client.put(f"{URL}/{libro['id']}", json=ficha(cota="A " * 51)).status_code == 422
    assert client.post(f"{URL}/{libro['id']}/copies", json={"cota": "1" * 101}).status_code == 422
    assert alta(client, forzar=True, cota="1" * 100)["ficha"]["cota"] == "1" * 100


def test_descripcion_y_notas_con_tope_en_bytes(client):
    for campo in ("descripcion", "notas"):
        r = client.post(URL, json={"ficha": ficha(**{campo: "x" * 12000}), "forzar": True})
        assert r.status_code == 422, r.text
        assert "9000" in r.text
        # 4600 letras con tilde son 9200 bytes en UTF-8: no caben.
        r = client.post(URL, json={"ficha": ficha(**{campo: "á" * 4600}), "forzar": True})
        assert r.status_code == 422, r.text
    libro = alta(client, forzar=True, descripcion="x" * 9000, notas="é" * 4500)
    assert len(libro["ficha"]["descripcion"]) == 9000
    assert client.put(f"{URL}/{libro['id']}", json=ficha(descripcion="x" * 9001)).status_code == 422
