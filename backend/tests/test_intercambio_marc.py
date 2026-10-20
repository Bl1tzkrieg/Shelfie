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


def _mrc(*registros):
    return b"".join(r.as_marc() for r in registros)


def _importar(client, contenido, modo="aplicar", **params):
    return client.post(f"{URL}/import", params={"modo": modo, **params}, content=contenido,
                       headers={"Content-Type": "application/octet-stream"})


def test_vista_previa_no_escribe_y_aplicar_importa_con_ejemplares(client, datos, db):
    datos.tipo_item("REV", "Revista")
    archivo = _mrc(
        _libro("Doña Bárbara", "978-980-00-0012-3", "Gallegos, Rómulo",
               ejemplares=[[("p", "IMP-1"), ("y", "LIB"), ("o", "863 G16"), ("v", "15,50")],
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
    assert any("XYZ" in m for m in barbara["mensajes"])  # tipo desconocido → LIB

    biblio = db.get(models.RegistroBibliografico, barbara["registro_id"])
    assert (biblio.titulo, biblio.autor, biblio.isbn) == (
        "Doña Bárbara", "Gallegos, Rómulo", "978-980-00-0012-3")
    tags = [list(c)[0] for c in biblio.marc_json["fields"]]
    assert "008" in tags and "952" not in tags and "999" not in tags
    items = {i.codigo_barras: i for i in db.query(models.Item).all()}
    assert float(items["IMP-1"].precio_reposicion) == 15.5
    assert items["IMP-1"].signatura_topografica == "863 G16"
    assert items["IMP-2"].estado == "Perdido"
    # Lo importado aparece en la búsqueda.
    assert client.get(f"{URL}/search", params={"q": "barbara"}).json()["total"] == 1


def test_duplicados_por_isbn(client, datos, db):
    client.post(f"{URL}/items", json={"titulo": "Canaima", "isbn": "9789800000013",
                                      "codigo_barras": "CAN-1"})
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
    r = _importar(client, _mrc(_libro("Nuevo", ejemplares=[[("p", "YA-EXISTE")]]))).json()
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
    datos.tipo_item("REV", "Revista")
    client.post(f"{URL}/items", json={"titulo": "Cien años de soledad", "isbn": "9780307474728",
                                      "autor": "García Márquez, Gabriel",
                                      "codigo_barras": "CIEN-1", "signatura_topografica": "863 G2"})
    client.post(f"{URL}/items", json={"titulo": "Ciencia del suelo", "codigo_barras": "SUE-1",
                                      "tipo_item_codigo": "REV"})

    r = client.get(f"{URL}/export", params={"formato": "marc"})
    assert r.status_code == 200
    assert "attachment" in r.headers["content-disposition"]
    leidos = list(pymarc.MARCReader(io.BytesIO(r.content), to_unicode=True))
    assert [x["245"]["a"] for x in leidos] == ["Cien años de soledad", "Ciencia del suelo"]
    cien = next(x for x in leidos if x["245"]["a"].startswith("Cien años"))
    assert cien["001"].data.isdigit()
    assert cien["952"]["p"] == "CIEN-1" and cien["952"]["o"] == "863 G2"
    assert cien["952"]["y"] == "LIB"

    sin = client.get(f"{URL}/export", params={"formato": "marcxml", "ejemplares": "false",
                                               "q": "soledad"})
    registros = pymarc.parse_xml_to_array(io.BytesIO(sin.content))
    assert len(registros) == 1 and registros[0].get_fields("952") == []

    # Lo exportado se puede volver a importar: con "omitir", el que tiene ISBN se detecta.
    vuelta = _importar(client, r.content, modo="vista").json()
    assert vuelta["omitidos"] == 1 and vuelta["nuevos"] == 1


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
    r = client.post(f"{URL}/items", json={"titulo": "Resumen largo", "codigo_barras": "L-1"})
    biblio = db.query(models.RegistroBibliografico).one()
    marc = dict(biblio.marc_json)
    marc["fields"] = marc["fields"] + [{"520": {"ind1": " ", "ind2": " ",
                                                "subfields": [{"a": "x" * 10050}]}}]
    biblio.marc_json = marc
    db.commit()

    r = client.get(f"{URL}/export", params={"formato": "marc"})
    assert r.status_code == 400 and "MARCXML" in r.json()["detail"] and "520" in r.json()["detail"]
    assert client.get(f"{URL}/export", params={"formato": "marcxml"}).status_code == 200
