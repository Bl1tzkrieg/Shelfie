"""Registro MARC como fuente: plantillas, validación, derivación y alta completa."""


import pytest

from app import models
from app.services import marc

URL = "/api/v1/catalog"
LIBROS = "/api/v1/books"
NUEVO = {"cota": "571.2 T13", "titulo": "Fisiología Vegetal", "autor": "Taiz, Lincoln",
         "isbn": ["9781111111111"], "ano": 2010, "materias": ["Fitotecnia"]}


def _campo(tag, *subs, ind1=" ", ind2=" "):
    return {tag: {"ind1": ind1, "ind2": ind2, "subfields": [{c: v} for c, v in subs]}}


def _registro(*campos, f008=True):
    fields = ([{"008": marc.campo_008(2020)}] if f008 else []) + list(campos)
    return {"leader": "00000nam a22000007i 4500", "fields": fields}


def _alta(client):
    r = client.post(LIBROS, json={"ficha": NUEVO})
    assert r.status_code == 201, r.text
    return r.json()["id"]


def _locs(r):
    return [tuple(e["loc"]) for e in r.json()["detail"]]


# --- Plantillas --------------------------------------------------------------------

def test_plantillas(client):
    codigos = [p["codigo"] for p in client.get(f"{URL}/frameworks").json()]
    assert codigos == ["BKS", "SER", "TES", "ERE"]
    tes = client.get(f"{URL}/frameworks/TES").json()
    c502 = next(c for c in tes["campos"] if c["tag"] == "502")
    assert c502["obligatorio"] and c502["visible"]
    assert tes["bloques"]["6"] == "Materias"
    assert client.get(f"{URL}/frameworks/XXX").status_code == 404


# --- Lectura y edición -------------------------------------------------------------

def test_el_alta_de_un_libro_deja_un_marc_completo(client, datos):
    biblio_id = _alta(client)
    r = client.get(f"{URL}/items/{biblio_id}/marc").json()
    assert r["plantilla"] == "BKS"
    assert "=092  \\\\$a571.2$bT13" in r["texto"]
    assert "=245  10$aFisiología Vegetal" in r["texto"]
    assert "=264  \\1$c2010" in r["texto"]


def test_editar_el_marc_actualiza_columnas_y_busqueda(client, datos, db):
    biblio_id = _alta(client)
    nuevo = _registro(
        _campo("020", ("a", "978-1-111-11111-1 (rústica)")),
        _campo("100", ("a", "Taiz, Lincoln,"), ("e", "autor."), ind1="1"),
        _campo("245", ("a", "Fisiología vegetal :"), ("b", "texto ilustrado /"),
               ("c", "Lincoln Taiz."), ind1="1", ind2="0"),
        _campo("260", ("a", "Sunderland :"), ("b", "Sinauer,"), ("c", "c2015.")),
        _campo("650", ("a", "Botánica."), ind2="4"),
        _campo("650", ("a", "Fisiología vegetal."), ind2="4"),
        _campo("999", ("z", "dato local que la plantilla no conoce")),
    )
    r = client.put(f"{URL}/items/{biblio_id}/marc", json={"plantilla": "BKS", "marc": nuevo})

    assert r.status_code == 200, r.text
    d = r.json()
    assert d["titulo"] == "Fisiología vegetal: texto ilustrado"
    assert (d["autor"], d["materia"], d["ano_publicacion"], d["isbn"]) == (
        "Taiz, Lincoln", "Botánica", 2015, "978-1-111-11111-1")
    assert any("999" in c for c in d["marc"]["fields"])     # campos ajenos se conservan
    # Editorial desde el 260 (sin la coma ISBD); el MARC nuevo no trae 092: sin cota.
    biblio = db.get(models.RegistroBibliografico, biblio_id)
    assert (biblio.editorial, biblio.cota) == ("Sinauer", None)
    hallados = client.get("/api/v1/buscar", params={"q": "ilustrado"}).json()["resultados"]
    assert [(h["id"], h["titulo"], h["subtitulo"]) for h in hallados] == [
        (biblio_id, "Fisiología vegetal", "texto ilustrado")]


def test_normaliza_campos_vacios_indicadores_y_orden(client, datos):
    biblio_id = _alta(client)
    r = client.put(f"{URL}/items/{biblio_id}/marc", json={"plantilla": "BKS", "marc": {
        "leader": "corto",
        "fields": [
            {"650": {"subfields": [{"a": "Botánica"}, {"x": "   "}]}},
            {"245": {"ind1": "1", "subfields": [{"a": "  Título  "}]}},
            {"500": {"subfields": [{"a": ""}]}},
            {"008": marc.campo_008(2001)},
        ]}}).json()
    assert [list(c)[0] for c in r["marc"]["fields"]] == ["008", "245", "650"]
    assert r["marc"]["fields"][1]["245"] == {"ind1": "1", "ind2": " ",
                                             "subfields": [{"a": "Título"}]}
    assert len(r["marc"]["leader"]) == 24


@pytest.mark.parametrize("plantilla,campos,error", [
    ("BKS", [_campo("100", ("a", "X"))], ("245",)),
    ("BKS", [_campo("245", ("b", "sin $a"))], ("245", "a")),
    ("BKS", [_campo("245", ("a", "T")), _campo("100", ("a", "A")), _campo("100", ("a", "B"))],
     ("100",)),
    ("BKS", [_campo("245", ("a", "T"), ("a", "otra vez"))], ("245", "a")),
    ("TES", [_campo("245", ("a", "Mi tesis"))], ("502",)),
    ("ERE", [_campo("245", ("a", "Sitio")), _campo("856", ("y", "Enlace sin URL"))],
     ("856", "u")),
])
def test_validacion_contra_la_plantilla(client, datos, plantilla, campos, error):
    biblio_id = _alta(client)
    r = client.put(f"{URL}/items/{biblio_id}/marc",
                   json={"plantilla": plantilla, "marc": _registro(*campos)})
    assert r.status_code == 422, r.text
    assert error in _locs(r)


def test_errores_de_estructura_y_008(client, datos):
    biblio_id = _alta(client)
    r = client.put(f"{URL}/items/{biblio_id}/marc", json={"plantilla": "BKS", "marc": {
        "leader": "", "fields": [{"24A": {"subfields": [{"a": "x"}]}},
                                 {"245": {"ind1": "#", "subfields": [{"a": "T"}]}}]}})
    assert r.status_code == 422
    assert {("24A",), ("245", "ind1")} <= set(_locs(r))

    r = client.put(f"{URL}/items/{biblio_id}/marc", json={"plantilla": "BKS", "marc": {
        "leader": "", "fields": [{"008": "muy corto"}, _campo("245", ("a", "T"))]}})
    assert ("008",) in _locs(r)


# --- Alta completa y ejemplares ----------------------------------------------------

def test_crear_registro_y_agregarle_ejemplares(client, datos):
    tesis = _registro(
        _campo("100", ("a", "Rojas, María"), ind1="1"),
        _campo("245", ("a", "Efecto del riego en el cacao"), ind1="1", ind2="0"),
        _campo("502", ("b", "Ingeniería Agronómica"), ("c", "UNAGRO"), ("d", "2024")),
        _campo("700", ("a", "Pérez, Ana"), ("e", "tutora"), ind1="1"),
    )
    r = client.post(f"{URL}/records", json={"plantilla": "TES", "marc": tesis})
    assert r.status_code == 201, r.text
    biblio_id = r.json()["id"]
    assert r.json()["plantilla"] == "TES"
    assert client.get(f"{LIBROS}/{biblio_id}").json()["ejemplares"] == []

    r = client.post(f"{LIBROS}/{biblio_id}/copies",
                    json={"codigo_barras": "TES-001", "cota": "T 630 R6"})
    assert r.status_code == 201, r.text
    assert [e["cota"] for e in r.json()["ejemplares"]] == ["T 630 R6"]
    assert client.post(f"{LIBROS}/{biblio_id}/copies",
                       json={"codigo_barras": "TES-001"}).status_code == 409


def test_isbn_repetido_avisa_y_se_puede_forzar(client, datos):
    _alta(client)
    otro = _registro(_campo("020", ("a", "9781111111111")), _campo("245", ("a", "Otra edición")))
    r = client.post(f"{URL}/records", json={"plantilla": "BKS", "marc": otro})
    assert r.status_code == 400 and "ya está en" in r.json()["detail"]
    r = client.post(f"{URL}/records",
                    json={"plantilla": "BKS", "marc": otro, "permitir_duplicado": True})
    assert r.status_code == 201


def test_editar_exige_permiso_de_catalogo(como, datos):
    sin_permiso = como([])
    r = sin_permiso.post(f"{URL}/records", json={
        "plantilla": "BKS", "marc": _registro(_campo("245", ("a", "T")))})
    assert r.status_code == 403
    assert sin_permiso.get(f"{URL}/frameworks").status_code == 200


# --- Derivación ---------------------------------------------------------------------

def test_ano_desde_260_o_008():
    con_260 = marc.normalizar(_registro(_campo("260", ("c", "[ca. 1998]")), f008=False))
    assert marc.ano_de(con_260) == 1998
    solo_008 = marc.normalizar({"leader": "", "fields": [{"008": marc.campo_008(1975)}]})
    assert marc.ano_de(solo_008) == 1975
