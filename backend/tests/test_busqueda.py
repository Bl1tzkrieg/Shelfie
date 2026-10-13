"""Búsqueda de texto completo: acentos, raíces, prefijos, facetas y paginación."""

import pytest

URL = "/api/v1/catalog/search"


@pytest.fixture()
def catalogo(datos):
    """Cinco títulos con lo justo para ejercitar cada caso."""
    revista = datos.tipo_item("REV", "Revista")
    t = {}
    t["cien"] = datos.titulo("Cien años de soledad", "978-0-307-47472-8",
                             autor="García Márquez, Gabriel", ano=1967, materia="Literatura")
    t["arboles"] = datos.titulo("Los árboles frutales del trópico", "9789801111111",
                                autor="Pérez, Ana", ano=2015, materia="Agronomía")
    t["suelos"] = datos.titulo("Ciencia del suelo", "9782222222222",
                               autor="Brady, Nyle", ano=2008, materia="Agronomía")
    t["arbol_genealogico"] = datos.titulo("Manual de genealogía", "9783333333333",
                                          autor="Árbol, José", ano=1999, materia="Historia")
    t["revista"] = datos.titulo("Revista agronómica venezolana", "",
                                autor=None, ano=None, materia="Agronomía")
    datos.ejemplar(t["cien"], "CIEN-1")
    datos.ejemplar(t["cien"], "CIEN-2", estado="Prestado")
    datos.ejemplar(t["arboles"], "ARB-1", estado="Prestado")
    datos.ejemplar(t["suelos"], "SUE-1")
    datos.ejemplar(t["arbol_genealogico"], "GEN-1")
    datos.ejemplar(t["revista"], "REV-1", tipo=revista)
    return t


def _titulos(r):
    return [x["title"] for x in r.json()["resultados"]]


def test_sin_acentos_y_por_raiz(client, catalogo):
    # "arbol" (sin tilde, singular) encuentra "árboles" en el título y "Árbol" en el autor.
    r = client.get(URL, params={"q": "arbol"})
    assert set(_titulos(r)) == {"Los árboles frutales del trópico", "Manual de genealogía"}
    # El título pesa más que el autor.
    assert _titulos(r)[0] == "Los árboles frutales del trópico"

    assert _titulos(client.get(URL, params={"q": "garcia marquez"})) == ["Cien años de soledad"]
    assert _titulos(client.get(URL, params={"q": "TROPICO"})) == [
        "Los árboles frutales del trópico"]


def test_la_ultima_palabra_es_prefijo(client, catalogo):
    assert _titulos(client.get(URL, params={"q": "cien añ"})) == ["Cien años de soledad"]
    assert _titulos(client.get(URL, params={"q": "agronom"}))  # materia, como prefijo
    assert client.get(URL, params={"q": "cien zzz"}).json()["total"] == 0


def test_isbn_con_o_sin_guiones_y_codigo_de_barras(client, catalogo):
    assert _titulos(client.get(URL, params={"q": "9780307474728"})) == ["Cien años de soledad"]
    assert _titulos(client.get(URL, params={"q": "978-0-307-47472-8"})) == ["Cien años de soledad"]
    assert _titulos(client.get(URL, params={"q": "sue-1"})) == ["Ciencia del suelo"]


def test_solo_palabras_vacias_o_simbolos_no_filtran(client, catalogo):
    assert client.get(URL, params={"q": "de la"}).json()["total"] == 5
    assert client.get(URL, params={"q": "&|!:*'"}).json()["total"] == 5


def test_facetas_cuentan_sobre_el_resultado(client, catalogo):
    f = client.get(URL, params={"q": "agronomia"}).json()["facetas"]
    assert {x["valor"]: x["cantidad"] for x in f["materias"]} == {"Agronomía": 3}
    assert {x["valor"]: x["cantidad"] for x in f["tipos"]} == {"LIB": 2, "REV": 1}
    assert {x["valor"]: x["cantidad"] for x in f["disponibilidad"]} == {"si": 2, "no": 1}
    assert {x["valor"]: x["cantidad"] for x in f["decadas"]} == {2010: 1, 2000: 1}
    assert f["decadas"][0]["etiqueta"] == "2010–2019"
    # Sin autor ni año no aparecen como valores vacíos.
    assert all(x["valor"] for x in f["autores"])


def test_filtros_de_faceta(client, catalogo):
    def total(**params):
        return client.get(URL, params=params).json()["total"]

    assert total(materia="Agronomía") == 3
    assert total(materia="Agronomía", tipo="REV") == 1
    assert total(disponible="true") == 4
    assert total(disponible="false") == 1          # "árboles": su único ejemplar está prestado
    assert total(ano_desde=2000, ano_hasta=2009) == 1
    assert total(autor="Pérez, Ana") == 1
    assert total(q="arbol", materia="Historia") == 1


def test_paginacion_y_orden(client, catalogo):
    r = client.get(URL, params={"orden": "titulo", "por_pagina": 2, "pagina": 2}).json()
    assert (r["total"], r["paginas"], r["pagina"]) == (5, 3, 2)
    # Cien años… < Ciencia… | Los árboles… < Manual… | Revista…
    assert [x["title"] for x in r["resultados"]] == ["Los árboles frutales del trópico",
                                                      "Manual de genealogía"]
    anos = [x["year"] for x in client.get(URL, params={"orden": "ano_desc"}).json()["resultados"]]
    assert anos == [2015, 2008, 1999, 1967, None]
    assert client.get(URL, params={"orden": "otro"}).status_code == 422


def test_resultados_traen_disponibilidad_del_titulo(client, catalogo):
    cien = client.get(URL, params={"q": "soledad"}).json()["resultados"][0]
    assert (cien["copies"], cien["available"], cien["availableBarcode"]) == (2, 1, "CIEN-1")


def test_se_actualiza_al_editar_el_registro(client, catalogo, db):
    catalogo["suelos"].titulo = "Edafología general"
    db.flush()
    assert _titulos(client.get(URL, params={"q": "edafologia"})) == ["Edafología general"]


def test_requiere_sesion_de_personal(anonimo):
    assert anonimo.get(URL).status_code == 401


# --- OPAC ------------------------------------------------------------------------

def test_opac_total_cuenta_todo_no_solo_la_pagina(client, catalogo):
    r = client.get("/api/v1/opac/search", params={"q": "", "limit": 2}).json()
    assert (r["total"], r["paginas"], len(r["resultados"])) == (5, 3, 2)
    assert client.get("/api/v1/opac/search", params={"q": "arbol"}).json()["total"] == 2


def test_opac_avanzada_por_campo_sin_acentos(client, catalogo):
    def total(**params):
        return client.get("/api/v1/opac/advanced-search", params=params).json()["total"]

    assert total(titulo="arbol") == 1           # el autor "Árbol" no cuenta como título
    assert total(autor="arbol") == 1
    assert total(materia="agronomia", solo_disponibles="true") == 2
    assert total(isbn="0307474728") == 1
