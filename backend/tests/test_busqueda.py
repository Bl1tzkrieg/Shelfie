"""Búsqueda pública (Tarea 6): por palabras, por campo, por cota y por ISBN; sin sesión."""

import pytest

URL = "/api/v1/buscar"


def alta(cliente, titulo, cota, ejemplares=1, **extra):
    ficha = {"cota": cota, "titulo": titulo, **extra}
    r = cliente.post("/api/v1/books", json={"ficha": ficha, "ejemplares": ejemplares,
                                            "forzar": True})
    assert r.status_code == 201, r.text
    return r.json()


@pytest.fixture()
def libros(client):
    return {
        "harper": alta(client, "Bioquímica de Harper", "616.39  h37", ejemplares=2,
                       autor="Murray, Robert", subtitulo="Edición ilustrada", edicion="29.ª ed.",
                       editorial="McGraw-Hill", ano=2012, isbn=["978-0-07-176576-3"],
                       materias=["Bioquímica"]),
        "general": alta(client, "Bioquímica general", "574.192 B5", autor="Lehninger, Albert",
                        editorial="Limusa", materias=["Química"]),
        "suelo": alta(client, "Ciencia del suelo", "631.4 B7", autor="Brady, Nyle"),
        "fisio": alta(client, "Fisiología", "612 F4", autor="Harper, Harold"),
    }


def _titulos(r):
    assert r.status_code == 200, r.text
    return [x["titulo"] for x in r.json()["resultados"]]


def test_todas_las_palabras(anonimo, libros):
    r = anonimo.get(URL, params={"q": "bioquimica harper"})
    titulos = _titulos(r)
    assert "Bioquímica de Harper" in titulos
    assert titulos == ["Bioquímica de Harper"]
    # Una palabra que no está en ninguno descarta todo.
    assert anonimo.get(URL, params={"q": "bioquimica zzz"}).json()["total"] == 0


def test_sin_acentos_y_prefijo(anonimo, libros):
    assert "Bioquímica de Harper" in _titulos(anonimo.get(URL, params={"q": "bioqui"}))
    assert _titulos(anonimo.get(URL, params={"q": "CIENCIA suel"})) == ["Ciencia del suelo"]


def test_por_cada_campo(anonimo, libros):
    # Harper está en el título de uno y es autor de otro.
    assert _titulos(anonimo.get(URL, params={"q": "harper", "campo": "titulo"})) == [
        "Bioquímica de Harper"]
    assert _titulos(anonimo.get(URL, params={"q": "harper", "campo": "autor"})) == ["Fisiología"]
    assert _titulos(anonimo.get(URL, params={"q": "quimica", "campo": "materia"})) == [
        "Bioquímica general"]
    assert _titulos(anonimo.get(URL, params={"q": "limusa", "campo": "editorial"})) == [
        "Bioquímica general"]
    # Un título sin esa palabra no aparece cuando se busca solo en el título.
    assert anonimo.get(URL, params={"q": "brady", "campo": "titulo"}).json()["total"] == 0


def test_busca_cota_con_espacios_y_minusculas(anonimo, libros):
    assert _titulos(anonimo.get(URL, params={"q": "616.39  h"})) == ["Bioquímica de Harper"]
    assert _titulos(anonimo.get(URL, params={"q": "616.39  h", "campo": "cota"})) == [
        "Bioquímica de Harper"]
    # Solo la clase, como se escribe al principio.
    assert _titulos(anonimo.get(URL, params={"q": "616.39"})) == ["Bioquímica de Harper"]
    assert anonimo.get(URL, params={"q": "616.4", "campo": "cota"}).json()["total"] == 0


def test_cota_de_un_ejemplar_y_comodines(anonimo, client, libros):
    alta(client, "Con ejemplar aparte", "100 Z1")
    libro = libros["suelo"]
    r = client.post(f"/api/v1/books/{libro['id']}/copies", json={"cota": "777 Q9"})
    assert r.status_code == 201
    assert _titulos(anonimo.get(URL, params={"q": "777", "campo": "cota"})) == ["Ciencia del suelo"]
    # % y _ se toman literalmente.
    assert anonimo.get(URL, params={"q": "6%", "campo": "cota"}).json()["total"] == 0
    assert anonimo.get(URL, params={"q": "_16", "campo": "cota"}).json()["total"] == 0


def test_isbn_con_guiones(anonimo, libros):
    for q in ("9780071765763", "978-0-07-176576-3", "978 0 07 176576 3"):
        assert _titulos(anonimo.get(URL, params={"q": q})) == ["Bioquímica de Harper"]
        assert _titulos(anonimo.get(URL, params={"q": q, "campo": "isbn"})) == [
            "Bioquímica de Harper"]
    assert anonimo.get(URL, params={"q": "abc", "campo": "isbn"}).json()["total"] == 0


@pytest.mark.parametrize("q", ["de la", "¿?", "-", "", "   "])
def test_busqueda_sin_terminos_utiles(anonimo, libros, q):
    for campo in ("todo", "titulo", "autor", "cota", "isbn"):
        r = anonimo.get(URL, params={"q": q, "campo": campo})
        assert r.status_code == 200, (campo, r.text)
        assert r.json()["total"] == 0 and r.json()["resultados"] == []


def test_es_publica(anonimo, libros):
    assert anonimo.get(URL, params={"q": "suelo"}).status_code == 200
    assert anonimo.get(f"{URL}/{libros['suelo']['id']}").status_code == 200


def test_resultado_con_sus_campos(anonimo, libros):
    r = anonimo.get(URL, params={"q": "harper", "campo": "titulo"}).json()
    assert (r["total"], r["pagina"]) == (1, 1)
    assert r["resultados"] == [{
        "id": libros["harper"]["id"], "cota": "616.39 H37", "titulo": "Bioquímica de Harper",
        "subtitulo": "Edición ilustrada", "autor": "Murray, Robert", "edicion": "29.ª ed.",
        "editorial": "McGraw-Hill", "ano": 2012, "ejemplares": 2}]


def test_orden_por_relevancia_y_luego_estante(anonimo, client):
    alta(client, "Anatomía", "612 B")
    alta(client, "Anatomía", "92 B")
    alta(client, "Anatomía", "612 A")
    alta(client, "Atlas de anatomía", "611 C")
    r = anonimo.get(URL, params={"q": "anatomia"}).json()["resultados"]
    # Dentro de cada empate de relevancia, el orden del estante (92 antes que 612).
    cotas = [x["cota"] for x in r]
    assert cotas.index("92 B") < cotas.index("612 A") < cotas.index("612 B")
    solo = anonimo.get(URL, params={"q": "anatomia", "campo": "cota"}).json()
    assert solo["total"] == 0
    todos = anonimo.get(URL, params={"q": "6", "campo": "cota"}).json()["resultados"]
    assert [x["cota"] for x in todos] == ["611 C", "612 A", "612 B"]


def test_paginas_de_veinte(anonimo, client):
    for n in range(25):
        alta(client, f"Tratado {n:02d}", f"{100 + n} T")
    p1 = anonimo.get(URL, params={"q": "tratado"}).json()
    p2 = anonimo.get(URL, params={"q": "tratado", "pagina": 2}).json()
    assert (p1["total"], len(p1["resultados"]), len(p2["resultados"])) == (25, 20, 5)
    assert p2["pagina"] == 2
    assert anonimo.get(URL, params={"q": "tratado", "pagina": 0}).status_code == 422


def test_campo_invalido(anonimo, libros):
    r = anonimo.get(URL, params={"q": "x", "campo": "editor"})
    assert r.status_code == 400


def test_ficha_publica_sin_codigos(anonimo, client, libros):
    client.post(f"/api/v1/books/{libros['harper']['id']}/copies",
                json={"codigo_barras": "SECRETO-1", "nota": "Lomo dañado"})
    r = anonimo.get(f"{URL}/{libros['harper']['id']}")
    assert r.status_code == 200
    assert "codigo_barras" not in r.text and "SECRETO-1" not in r.text
    cuerpo = r.json()
    assert set(cuerpo) == {"ficha", "ejemplares"}
    assert cuerpo["ficha"]["titulo"] == "Bioquímica de Harper"
    assert cuerpo["ejemplares"][0] == {"cota": "616.39 H37", "numero_copia": "c.1", "nota": None}
    assert len(cuerpo["ejemplares"]) == 3
    assert "marc" not in r.text.lower()
    assert anonimo.get(f"{URL}/999999").status_code == 404
