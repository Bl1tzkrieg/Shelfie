"""Importar y exportar MARC21 (ISO 2709 y MARCXML), con ejemplares en 952 como Koha."""

import io

import pymarc
from pymarc import Field, Indicators, Record, Subfield

from app import models

URL = "/api/v1/catalog"


def _libro(titulo, isbn=None, autor=None, ejemplares=(), con_008=False, lider_tipo="am"):
    r = Record(force_utf8=True)
    r.leader = r.leader[:6] + lider_tipo + r.leader[8:]
    if con_008:
        r.add_field(Field(tag="008", data="200101s2019    ve            000 0 spa d"))
    if isbn:
        r.add_field(Field(tag="020", indicators=Indicators(" ", " "),
                          subfields=[Subfield("a", isbn)]))
    if autor:
        r.add_field(Field(tag="100", indicators=Indicators("1", " "),
                          subfields=[Subfield("a", autor)]))
    if titulo:
        r.add_field(Field(tag="245", indicators=Indicators("1", "0"),
                          subfields=[Subfield("a", titulo)]))
    r.add_field(Field(tag="999", indicators=Indicators(" ", " "),
                      subfields=[Subfield("c", "4711")]))  # biblionumber de otro Koha
    for subs in ejemplares:
        r.add_field(Field(tag="952", indicators=Indicators(" ", " "),
                          subfields=[Subfield(k, v) for k, v in subs]))
    return r


def _alta(client, titulo, codigo, isbn=None, autor=None, cota="000 X"):
    """Un libro con un ejemplar, cargado por /books."""
    r = client.post("/api/v1/books", json={
        "ficha": {"cota": cota, "titulo": titulo, "autor": autor, "isbn": [isbn] if isbn else []},
        "ejemplares": 0})
    assert r.status_code == 201, r.text
    biblio_id = r.json()["id"]
    r = client.post(f"/api/v1/books/{biblio_id}/copies", json={"codigo_barras": codigo})
    assert r.status_code == 201, r.text
    return biblio_id


def _mrc(*registros):
    return b"".join(r.as_marc() for r in registros)


def _importar(client, contenido, modo="aplicar", **params):
    return client.post(f"{URL}/import", params={"modo": modo, **params}, content=contenido,
                       headers={"Content-Type": "application/octet-stream"})


def test_vista_previa_no_escribe_y_aplicar_importa_con_ejemplares(client, datos, db):
    archivo = _mrc(
        _libro("Doña Bárbara", "978-980-00-0012-3", "Gallegos, Rómulo",
               ejemplares=[[("p", "IMP-1"), ("y", "LIB"), ("o", "863 G16"), ("t", "c.1"),
                            ("z", "Firmado")],
                           [("p", "IMP-2"), ("y", "XYZ"), ("1", "1")]]),
        _libro("Revista Agronomía Tropical", lider_tipo="as",
               ejemplares=[[("p", "IMP-3"), ("y", "REV")]]),
    )

    vista = _importar(client, archivo, modo="vista").json()
    assert (vista["aplicado"], vista["total"], vista["nuevos"], vista["ejemplares"]) == (
        False, 2, 2, 3)
    assert db.query(models.RegistroBibliografico).count() == 0

    r = _importar(client, archivo).json()
    assert (r["nuevos"], r["con_errores"], r["ejemplares"]) == (2, 0, 3)
    barbara, revista = r["registros"]
    assert barbara["plantilla"] == "BKS" and revista["plantilla"] == "SER"

    biblio = db.get(models.RegistroBibliografico, barbara["registro_id"])
    assert (biblio.titulo, biblio.autor, biblio.isbn) == (
        "Doña Bárbara", "Gallegos, Rómulo", "978-980-00-0012-3")
    tags = [list(c)[0] for c in biblio.marc_json["fields"]]
    assert "008" in tags and "952" not in tags and "999" not in tags
    items = {i.codigo_barras: i for i in db.query(models.Item).all()}
    assert (items["IMP-1"].signatura_topografica, items["IMP-1"].numero_copia,
            items["IMP-1"].nota) == ("863 G16", "c.1", "Firmado")
    # Lo importado aparece en la búsqueda.
    assert client.get("/api/v1/buscar", params={"q": "barbara"}).json()["total"] == 1


def test_duplicados_por_isbn(client, datos, db):
    _alta(client, "Canaima", "CAN-1", isbn="9789800000013")
    archivo = _mrc(_libro("Canaima (otra edición)", "978-980-00-0001-3",
                          ejemplares=[[("p", "CAN-2")]]))

    omitir = _importar(client, archivo).json()
    assert (omitir["omitidos"], omitir["nuevos"]) == (1, 0)

    reemplazar = _importar(client, archivo, duplicados="reemplazar").json()
    assert reemplazar["reemplazados"] == 1
    [biblio] = db.query(models.RegistroBibliografico).all()
    assert biblio.titulo == "Canaima (otra edición)"
    assert sorted(i.codigo_barras for i in db.query(models.Item)) == ["CAN-1", "CAN-2"]

    agregar = _importar(client, _mrc(_libro("Canaima", "9789800000013")),
                        duplicados="agregar").json()
    assert agregar["nuevos"] == 1
    assert db.query(models.RegistroBibliografico).count() == 2


def test_isbn_repetido_dentro_del_archivo_y_registro_sin_titulo(client, datos):
    archivo = _mrc(_libro("Uno", "9789800000099"), _libro("Uno bis", "978-980-00-0009-9"),
                   _libro(None, "9789800000100"))
    r = _importar(client, archivo).json()
    acciones = [x["accion"] for x in r["registros"]]
    assert acciones == ["nuevo", "omitir", "error"]
    assert "245" in r["registros"][2]["mensajes"][0]


def test_codigo_de_barras_existente_se_omite(client, datos):
    datos.ejemplar(datos.titulo(), "YA-EXISTE")
    # Con ISBN propio no es el mismo registro; su código, de otro libro, se omite.
    r = _importar(client, _mrc(_libro("Nuevo", "9789800000777",
                                      ejemplares=[[("p", "YA-EXISTE")]]))).json()
    assert r["nuevos"] == 1 and r["ejemplares"] == 0
    assert any("YA-EXISTE" in m for m in r["registros"][0]["mensajes"])


def test_marcxml_y_archivos_invalidos(client, datos):
    xml = io.BytesIO()
    escritor = pymarc.XMLWriter(xml)
    escritor.write(_libro("Árboles de Venezuela", "9789800000003", con_008=True))
    escritor.close(close_fh=False)
    r = _importar(client, xml.getvalue()).json()
    assert (r["formato"], r["nuevos"]) == ("marcxml", 1)

    assert _importar(client, b"").status_code == 400
    assert _importar(client, b"<no-es-marc").status_code == 400
    assert _importar(client, b"esto no es un archivo marc" * 10).status_code == 400


def test_exportar_marc_con_ejemplares_y_volver_a_leerlo(client, datos):
    cien = _alta(client, "Cien años de soledad", "CIEN-1", isbn="9780307474728",
                 autor="García Márquez, Gabriel", cota="863 G2")
    _alta(client, "Ciencia del suelo", "SUE-1")

    r = client.get(f"{URL}/export", params={"formato": "marc"})
    assert r.status_code == 200
    assert "attachment" in r.headers["content-disposition"]
    assert r.content[9:10] == b"a"  # líder/09: UTF-8
    leidos = list(pymarc.MARCReader(io.BytesIO(r.content), to_unicode=True))
    assert [x["245"]["a"] for x in leidos] == ["Cien años de soledad", "Ciencia del suelo"]
    primero = leidos[0]
    assert primero["001"].data.isdigit()
    assert primero["952"]["p"] == "CIEN-1" and primero["952"]["o"] == "863 G2"

    solo = client.get(f"{URL}/export", params={"formato": "marcxml", "ids": str(cien)})
    registros = pymarc.parse_xml_to_array(io.BytesIO(solo.content))
    assert [x["245"]["a"] for x in registros] == ["Cien años de soledad"]

    # Lo exportado se puede volver a importar: con "omitir", el que tiene ISBN se detecta por
    # ISBN y el que no, por sus códigos.
    vuelta = _importar(client, r.content, modo="vista").json()
    assert vuelta["omitidos"] == 2 and vuelta["nuevos"] == 0


def test_exportar_exige_permiso_de_catalogo(como):
    assert como([]).get(f"{URL}/export").status_code == 403
    assert como([]).get(f"{URL}/export.csv").status_code == 403


def test_importar_exige_permiso_de_catalogo(como):
    assert _importar(como([]), _mrc(_libro("X"))).status_code == 403


def _utf8_sin_marcar(r):
    """Como exportan muchos sistemas: texto UTF-8 pero el líder/09 en blanco."""
    crudo = r.as_marc()
    return crudo[:9] + b" " + crudo[10:]


def test_utf8_sin_marcar_en_el_lider_se_detecta(client, datos, db):
    """M7: en «auto», si los bytes son UTF-8 válido se leen como UTF-8."""
    archivo = _utf8_sin_marcar(_libro("Año de García Márquez"))
    assert archivo[9:10] == b" "

    vista = _importar(client, archivo, modo="vista").json()
    assert vista["registros"][0]["titulo"].startswith("Año de García Márquez")
    marc8 = _importar(client, archivo, modo="vista", codificacion="marc8").json()
    assert not marc8["registros"][0]["titulo"].startswith("Año")
    assert _importar(client, archivo, modo="vista", codificacion="ebcdic").status_code == 422


def test_latin1_a_pedido(client, datos):
    r = _libro("Canción")
    r.leader = r.leader[:9] + " " + r.leader[10:]
    r.force_utf8 = r.to_unicode = False  # así pymarc escribe en ISO 8859-1
    archivo = r.as_marc()
    assert "Canción".encode("latin-1") in archivo

    vista = _importar(client, archivo, modo="vista", codificacion="latin1").json()
    assert vista["registros"][0]["titulo"].startswith("Canción")


def test_marcxml_con_bom(client, datos):
    """B9: la marca de orden de bytes no impide reconocer el MARCXML."""
    salida = io.BytesIO()
    escritor = pymarc.XMLWriter(salida)
    escritor.write(_libro("Con BOM"))
    escritor.close(close_fh=False)
    r = _importar(client, b"\xef\xbb\xbf" + salida.getvalue(), modo="vista")
    assert r.status_code == 200 and r.json()["formato"] == "marcxml"


def test_exportar_iso2709_avisa_si_un_campo_no_cabe(client, datos, db):
    """M8: un campo de más de 9999 bytes no cabe en ISO 2709; MARCXML sí."""
    _alta(client, "Resumen largo", "L-1")
    biblio = db.query(models.RegistroBibliografico).one()
    marc = dict(biblio.marc_json)
    marc["fields"] = marc["fields"] + [{"520": {"ind1": " ", "ind2": " ",
                                                "subfields": [{"a": "x" * 10050}]}}]
    biblio.marc_json = marc
    db.commit()

    r = client.get(f"{URL}/export", params={"formato": "marc"})
    assert r.status_code == 400 and "MARCXML" in r.json()["detail"] and "520" in r.json()["detail"]
    assert client.get(f"{URL}/export", params={"formato": "marcxml"}).status_code == 200


# --- Compatibilidad con Koha ---------------------------------------------------------

FUERA_DE_LA_COMPARACION = {"001", "003", "005", "952", "999"}


def _clave_bibliografica(r):
    """Por registro: todos los campos (etiqueta, indicadores y subcampos, o el dato de un
    campo de control) salvo 001, 003, 005, 952 y 999, y los 952 $o, $p y $t."""
    campos = []
    for c in r.get_fields():
        if c.tag in FUERA_DE_LA_COMPARACION:
            continue
        if c.is_control_field():
            campos.append((c.tag, c.data))
        else:
            campos.append((c.tag, tuple(c.indicators),
                           tuple((s.code, s.value) for s in c.subfields)))
    ejemplares = tuple(sorted((c.get("o") or "", c.get("p") or "", c.get("t") or "")
                              for c in r.get_fields("952")))
    return (tuple(sorted(campos, key=repr)), ejemplares)


def test_ida_y_vuelta_koha(client, datos):
    from tests.datos import koha_muestra
    original = koha_muestra.iso2709()
    r = _importar(client, original).json()
    assert (r["nuevos"], r["con_errores"], r["ejemplares"]) == (3, 0, 4), r

    exportado = client.get(f"{URL}/export", params={"formato": "marc"})
    assert exportado.status_code == 200
    antes = sorted(_clave_bibliografica(x)
                   for x in pymarc.MARCReader(io.BytesIO(original), to_unicode=True))
    despues = sorted(_clave_bibliografica(x)
                     for x in pymarc.MARCReader(io.BytesIO(exportado.content), to_unicode=True))
    assert despues == antes


def test_952_sin_codigo_se_importa(client, datos, db):
    archivo = _mrc(_libro("Sin código", ejemplares=[[("a", "UCV"), ("o", "001 S5"), ("t", "c.1")],
                                                    [("o", "001 S5"), ("t", "c.2")]]))
    r = _importar(client, archivo).json()
    assert r["ejemplares"] == 2, r
    items = db.query(models.Item).order_by(models.Item.id).all()
    assert [(i.codigo_barras, i.signatura_topografica, i.numero_copia) for i in items] == [
        (None, "001 S5", "c.1"), (None, "001 S5", "c.2")]
    biblio = db.query(models.RegistroBibliografico).one()
    # La cota del registro sale del primer 952 $o; el MARC no gana un 092.
    assert biblio.cota == "001 S5"
    assert not any("092" in c for c in biblio.marc_json["fields"])


def test_cota_desde_082(client, datos, db):
    from tests.datos import koha_muestra
    _importar(client, koha_muestra.iso2709())
    quimica = db.query(models.RegistroBibliografico).filter_by(titulo="Química general").one()
    assert quimica.cota == "540 C43"  # 082 $a + $b
    assert not any("092" in c for c in quimica.marc_json["fields"])
    # Si hay 092, manda el 092; y los 952 y 999 de Koha no quedan en el MARC guardado.
    barbara = db.query(models.RegistroBibliografico).filter(
        models.RegistroBibliografico.titulo.like("Doña%")).one()
    assert barbara.cota == "863 G16"
    tags = {next(iter(c)) for c in barbara.marc_json["fields"]}
    assert "952" not in tags and "999" not in tags

    sin_092 = _mrc(_libro("Con 050", ejemplares=[]))
    registro = pymarc.MARCReader(io.BytesIO(sin_092), to_unicode=True).__next__()
    registro.add_field(Field(tag="050", indicators=Indicators(" ", "4"),
                             subfields=[Subfield("a", "QA76.73"), Subfield("b", "P98")]))
    _importar(client, registro.as_marc())
    assert db.query(models.RegistroBibliografico).filter_by(
        titulo="Con 050").one().cota == "QA76.73 P98"


def test_importa_sin_cota(client, datos, db):
    r = _importar(client, _mrc(_libro("Sin nada"))).json()
    assert (r["nuevos"], r["con_errores"]) == (1, 0), r
    biblio = db.query(models.RegistroBibliografico).one()
    assert biblio.cota is None
    assert not any("092" in c for c in biblio.marc_json["fields"])


def test_export_usa_codigo_de_biblioteca(client, datos):
    assert client.put("/api/v1/settings", json={
        "biblioteca": {"codigo": "UCV", "tipo_item_koha": "lib"}}).status_code == 200
    biblio = _alta(client, "Canaima", "CAN-1", cota="863 G16")
    r = client.post(f"/api/v1/books/{biblio}/copies", json={"nota": "Donación"})
    assert r.status_code == 201, r.text

    [leido] = pymarc.MARCReader(io.BytesIO(client.get(f"{URL}/export").content), to_unicode=True)
    uno, dos = leido.get_fields("952")
    assert [(s.code, s.value) for s in uno.subfields] == [
        ("a", "UCV"), ("b", "UCV"), ("o", "863 G16"), ("p", "CAN-1"), ("t", "c.1"), ("y", "LIB")]
    assert [s.code for s in dos.subfields] == ["a", "b", "o", "t", "y", "z"]
    assert dos["z"] == "Donación"
    assert leido["003"].data == "UCV"


def test_reemplazar_no_duplica_codigos(client, datos, db):
    _alta(client, "Canaima", "CAN-1", isbn="9789800000013")
    archivo = _mrc(_libro("Canaima", "9789800000013",
                          ejemplares=[[("p", "CAN-1")], [("p", "CAN-9")]]))
    r = _importar(client, archivo, duplicados="reemplazar")
    assert r.status_code == 200
    cuerpo = r.json()
    assert (cuerpo["reemplazados"], cuerpo["ejemplares"]) == (1, 1)
    assert any("CAN-1 ya existe" in m for m in cuerpo["registros"][0]["mensajes"])
    assert sorted(i.codigo_barras for i in db.query(models.Item)) == ["CAN-1", "CAN-9"]


def test_csv_protegido(client, datos):
    _alta(client, "=HYPERLINK(\"http://x\")", "F-1", cota="900 B2", autor="Bello, Andrés")
    _alta(client, "Atlas", "A-1", cota="12 A8")
    _importar(client, _mrc(_libro("Sin cota")))
    r = client.get(f"{URL}/export.csv")
    assert r.status_code == 200 and r.headers["content-type"].startswith("text/csv")
    import csv
    filas = list(csv.DictReader(io.StringIO(r.content.decode("utf-8-sig"))))
    assert list(filas[0]) == ["cota", "titulo", "autor", "editorial", "ano", "isbn", "materias",
                              "ejemplares"]
    assert [f["cota"] for f in filas] == ["12 A8", "900 B2", ""]
    assert filas[1]["titulo"] == "'=HYPERLINK(\"http://x\")"
    assert filas[1]["ejemplares"] == "1" and filas[2]["ejemplares"] == "0"


def test_csv_materias_unidas(client, datos):
    from tests.datos import koha_muestra
    _importar(client, koha_muestra.iso2709())
    from app.services import intercambio_marc
    filas = intercambio_marc.exportar_csv(datos.db)
    barbara = next(f for f in filas if f["titulo"].startswith("Doña"))
    assert barbara["materias"] == "Novela venezolana. | Llanos (Venezuela)"
    assert (barbara["cota"], barbara["editorial"], barbara["ano"], barbara["ejemplares"]) == (
        "863 G16", "Monte Ávila", 1985, 2)


# --- Reimportar sin duplicar ---------------------------------------------------------

def test_reimportar_koha_con_omitir_no_duplica(client, datos, db):
    from tests.datos import koha_muestra
    _importar(client, koha_muestra.iso2709())
    r = _importar(client, koha_muestra.iso2709()).json()
    assert (r["nuevos"], r["omitidos"]) == (0, 3), r
    assert db.query(models.RegistroBibliografico).count() == 3
    assert db.query(models.Item).count() == 4
    cuentos = next(x for x in r["registros"] if x["titulo"].startswith("Cuentos"))
    assert any("sin ISBN: duplicado detectado por códigos" in m for m in cuentos["mensajes"])


def test_sin_isbn_ni_codigos_se_detecta_por_titulo_autor_y_ano(client, datos, db):
    primero = _libro("Ña Catita", autor="Segura, Manuel", con_008=True)
    _importar(client, _mrc(primero))
    otra = _mrc(_libro("ña catita", autor="SEGURA, MANUEL", con_008=True,
                       ejemplares=[[("o", "862 S4"), ("t", "c.1")]]))
    r = _importar(client, otra).json()
    assert (r["nuevos"], r["omitidos"]) == (0, 1), r
    assert any("sin ISBN: duplicado detectado por título, autor y año" in m
               for m in r["registros"][0]["mensajes"])
    # Otro año no es el mismo libro.
    distinto = _libro("Ña Catita", autor="Segura, Manuel")
    distinto.add_field(Field(tag="008", data="200101s1999    pe            000 0 spa d"))
    assert _importar(client, _mrc(distinto)).json()["nuevos"] == 1


def test_reemplazar_no_repite_ejemplares_sin_codigo(client, datos, db):
    from tests.datos import koha_muestra
    _importar(client, koha_muestra.iso2709())
    r = _importar(client, koha_muestra.iso2709(), duplicados="reemplazar").json()
    assert (r["reemplazados"], r["ejemplares"]) == (3, 0), r
    barbara = next(x for x in r["registros"] if x["titulo"].startswith("Doña"))
    assert any("ejemplar sin código ya existe: omitido" in m for m in barbara["mensajes"])
    assert db.query(models.Item).filter(models.Item.codigo_barras.is_(None)).count() == 1


def test_avisa_lo_que_se_ignora_del_952(client, datos):
    archivo = _mrc(
        _libro("Con datos de Koha", ejemplares=[
            [("p", "K-1"), ("c", "GEN"), ("d", "2020-01-01"), ("g", "25.00"), ("1", "1")],
            [("p", "K-2"), ("8", "REF"), ("9", "77"), ("7", "1"), ("1", "0")]]),
        _libro("Otro", ejemplares=[[("p", "K-3"), ("e", "Donación"), ("y", "BK")]]))
    r = _importar(client, archivo, modo="vista").json()
    assert r["mensajes"] == [
        "Se ignoraron subcampos del 952 que Shelfie no guarda: c, d, e, g, 1, 7, 8, 9"]
    mensajes = " | ".join(r["registros"][0]["mensajes"])
    assert "el ejemplar K-1 figuraba perdido en Koha; en Shelfie queda como uno más" in mensajes
    assert "el ejemplar K-2 figuraba no prestable en Koha; en Shelfie queda como uno más" in mensajes
    assert not any("figuraba" in m for m in r["registros"][1]["mensajes"])

    from tests.datos import koha_muestra  # $1 = 0 en todos: no se pierde nada
    assert _importar(client, koha_muestra.iso2709(), modo="vista").json()["mensajes"] == []


def test_cota_del_952_se_conserva_al_editar(client, db):
    """Sin 092, 082 ni 050, la cota del registro es la del 952 y editar no la pierde."""
    _importar(client, _mrc(_libro("Solo 952", ejemplares=[[("o", "001 S5"), ("p", "S-1")]])))
    biblio = db.query(models.RegistroBibliografico).one()
    antes = biblio.marc_json
    marc = client.get(f"{URL}/items/{biblio.id}/marc").json()
    assert client.put(f"{URL}/items/{biblio.id}/marc",
                      json={"marc": marc["marc"], "plantilla": marc["plantilla"]}).status_code == 200
    db.refresh(biblio)
    assert biblio.cota == "001 S5"

    vista = client.get(f"/api/v1/books/{biblio.id}").json()
    assert vista["ficha"]["cota"] == "001 S5"  # el formulario muestra la cota del registro
    assert client.put(f"/api/v1/books/{biblio.id}", json=vista["ficha"]).status_code == 200
    db.refresh(biblio)
    assert biblio.cota == "001 S5" and biblio.marc_json == antes  # sin cambios, nada cambia


def test_cota_del_952_manda_sobre_el_082_tambien_al_guardar_la_ficha(client, db):
    registro = _libro("Con 952 y 082", ejemplares=[[("o", "001 S5"), ("p", "S-2")]])
    registro.add_field(Field(tag="082", indicators=Indicators("0", "4"),
                             subfields=[Subfield("a", "540")]))
    _importar(client, registro.as_marc())
    biblio = db.query(models.RegistroBibliografico).one()
    assert biblio.cota == "001 S5"

    vista = client.get(f"/api/v1/books/{biblio.id}").json()
    assert vista["ficha"]["cota"] == "001 S5"
    assert client.put(f"/api/v1/books/{biblio.id}", json=vista["ficha"]).status_code == 200
    db.refresh(biblio)
    assert biblio.cota == "001 S5"


def test_duplicado_por_el_segundo_isbn_al_importar(client, datos, db):
    r = client.post("/api/v1/books", json={"ficha": {
        "cota": "1 A", "titulo": "Existente", "isbn": ["9780307474728", "9788497592208"]},
        "ejemplares": 0})
    assert r.status_code == 201, r.text
    r = _importar(client, _mrc(_libro("Entrante", isbn="978-84-9759-220-8")), modo="vista").json()
    assert r["omitidos"] == 1, r


# --- La cota del registro solo cambia si cambia la clasificación ----------------------

def _importado_con_082_y_952(client, db):
    """Como un registro típico de Koha: sin 092, con 082 y la cota en el 952 $o. Dos
    ejemplares heredan la cota del registro y uno tiene la suya."""
    registro = _libro("Química general", ejemplares=[
        [("o", "540 C43 Q"), ("p", "Q-1")], [("o", "540 C43 Q"), ("p", "Q-2")],
        [("o", "REF 540 C43"), ("p", "Q-3")]])
    registro.add_field(Field(tag="082", indicators=Indicators("0", "4"),
                             subfields=[Subfield("a", "540"), Subfield("b", "C43")]))
    _importar(client, registro.as_marc())
    biblio = db.query(models.RegistroBibliografico).one()
    assert biblio.cota == "540 C43 Q"
    return biblio


def _cotas_de_ejemplares(db, biblio):
    db.expire_all()
    return {i.codigo_barras: i.signatura_topografica
            for i in db.query(models.Item).filter(models.Item.biblio_id == biblio.id)}


def _ediciones(db, biblio):
    db.expire_all()
    return db.query(models.RegistroAccion).filter_by(
        modulo="catalogo", accion="edicion", biblio_id=biblio.id).count()


def _guardar_marc(client, biblio, cambiar=None):
    marc = client.get(f"{URL}/items/{biblio.id}/marc").json()
    for campo in marc["marc"]["fields"]:
        tag = next(iter(campo))
        if cambiar and tag in cambiar:
            campo[tag]["subfields"] = cambiar[tag]
    r = client.put(f"{URL}/items/{biblio.id}/marc",
                   json={"marc": marc["marc"], "plantilla": marc["plantilla"]})
    assert r.status_code == 200, r.text


ANTES = {"Q-1": "540 C43 Q", "Q-2": "540 C43 Q", "Q-3": "REF 540 C43"}


def test_editor_marc_sin_cambios_no_mueve_la_cota_del_952(client, db):
    biblio = _importado_con_082_y_952(client, db)

    _guardar_marc(client, biblio)

    db.refresh(biblio)
    assert biblio.cota == "540 C43 Q"
    assert _cotas_de_ejemplares(db, biblio) == ANTES


def test_editor_marc_cambiando_solo_el_245_no_mueve_la_cota(client, db):
    biblio = _importado_con_082_y_952(client, db)

    _guardar_marc(client, biblio, cambiar={"245": [{"a": "Química general (10.ª ed.)"}]})

    db.refresh(biblio)
    assert biblio.titulo == "Química general (10.ª ed.)"
    assert biblio.cota == "540 C43 Q"
    assert _cotas_de_ejemplares(db, biblio) == ANTES


def test_editor_marc_cambiando_el_082_recalcula_la_cota(client, db):
    biblio = _importado_con_082_y_952(client, db)

    _guardar_marc(client, biblio, cambiar={"082": [{"a": "541"}, {"b": "C43"}]})

    db.refresh(biblio)
    assert biblio.cota == "541 C43"
    assert _cotas_de_ejemplares(db, biblio) == {
        "Q-1": "541 C43", "Q-2": "541 C43", "Q-3": "REF 540 C43"}


def test_formulario_sin_cambios_no_toca_el_marc_importado(client, db):
    biblio = _importado_con_082_y_952(client, db)
    antes = biblio.marc_json
    ediciones = _ediciones(db, biblio)

    vista = client.get(f"/api/v1/books/{biblio.id}").json()
    assert vista["ficha"]["cota"] == "540 C43 Q"
    assert client.put(f"/api/v1/books/{biblio.id}", json=vista["ficha"]).status_code == 200

    db.refresh(biblio)
    assert biblio.marc_json == antes
    assert not any("092" in c for c in biblio.marc_json["fields"])
    assert biblio.cota == "540 C43 Q"
    assert _cotas_de_ejemplares(db, biblio) == ANTES
    assert _ediciones(db, biblio) == ediciones


def test_formulario_cambiando_la_cota_escribe_el_092_y_mueve_ejemplares(client, db):
    biblio = _importado_con_082_y_952(client, db)

    vista = client.get(f"/api/v1/books/{biblio.id}").json()
    r = client.put(f"/api/v1/books/{biblio.id}", json={**vista["ficha"], "cota": "540 C43 Q2"})
    assert r.status_code == 200, r.text

    db.refresh(biblio)
    assert biblio.cota == "540 C43 Q2"
    [campo_092] = [c["092"] for c in biblio.marc_json["fields"] if "092" in c]
    assert campo_092["subfields"] == [{"a": "540"}, {"b": "C43 Q2"}]
    assert _cotas_de_ejemplares(db, biblio) == {
        "Q-1": "540 C43 Q2", "Q-2": "540 C43 Q2", "Q-3": "REF 540 C43"}


def test_formulario_con_la_cota_del_082_tambien_la_aplica(client, db):
    biblio = _importado_con_082_y_952(client, db)

    vista = client.get(f"/api/v1/books/{biblio.id}").json()
    r = client.put(f"/api/v1/books/{biblio.id}", json={**vista["ficha"], "cota": "540 C43"})
    assert r.status_code == 200, r.text

    db.refresh(biblio)
    assert biblio.cota == "540 C43"
    assert r.json()["ficha"]["cota"] == "540 C43"
    assert _cotas_de_ejemplares(db, biblio) == {
        "Q-1": "540 C43", "Q-2": "540 C43", "Q-3": "REF 540 C43"}
