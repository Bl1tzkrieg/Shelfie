"""Ficha simple ↔ MARC 21."""

import pytest
from pydantic import ValidationError

from app.schemas import FichaLibro
from app.services import ficha, marc


def _completa() -> FichaLibro:
    return FichaLibro(
        cota="616.39 H37", titulo="El hambre", subtitulo="una historia", mencion="por Juan Pérez",
        autor="Pérez, Juan", otros_autores=["Gómez, Ana", "Rojas, Luis"], edicion="2.ª ed.",
        lugar="Caracas", editorial="Monte Ávila", ano=2019, paginas="320 p.",
        ilustraciones="il.", dimensiones="24 cm", isbn=["9789800000001", "9789800000002"],
        materias=["Nutrición", "Hambre"], descripcion="Resumen del libro.", notas="Incluye bibliografía.")


def _tags(registro: dict) -> list:
    return [next(iter(c)) for c in registro["fields"]]


def test_ida_y_vuelta():
    f = _completa()
    registro = ficha.a_marc(f, None)
    assert ficha.desde_marc(registro) == f
    assert _tags(registro) == sorted(_tags(registro))
    assert marc.ano_de(registro) == 2019
    assert [c for c in registro["fields"] if "008" in c][0]["008"][7:11] == "2019"


def test_conserva_campos_ajenos():
    ajenos = [{"082": {"ind1": "0", "ind2": "4", "subfields": [{"a": "616.39"}]}},
              {"856": {"ind1": "4", "ind2": " ", "subfields": [{"u": "http://x.org"}]}},
              {"952": {"ind1": " ", "ind2": " ", "subfields": [{"a": "B"}, {"p": "001"}]}}]
    base = {"leader": "00000nam a22000007i 4500", "fields": [
        ajenos[0], {"245": {"ind1": "0", "ind2": "0", "subfields": [{"a": "Viejo"}]}},
        ajenos[1], ajenos[2]]}
    resultado = ficha.a_marc(_completa(), base)
    for campo in ajenos:
        assert campo in resultado["fields"]
    assert [c for c in resultado["fields"] if "952" in c] == [ajenos[2]]
    assert len(marc.campos(resultado, "245")) == 1
    assert _tags(resultado).index("856") < _tags(resultado).index("952")
    assert base["fields"][1]["245"]["subfields"] == [{"a": "Viejo"}]  # no muta la entrada


def test_articulo_inicial():
    f = FichaLibro(cota="863 G3", titulo="El túnel", autor="Sabato, Ernesto")
    campo = marc.campos(ficha.a_marc(f, None), "245")[0]
    assert (campo["ind1"], campo["ind2"]) == ("1", "3")
    sin_autor = marc.campos(ficha.a_marc(FichaLibro(cota="1", titulo="Casa"), None), "245")[0]
    assert (sin_autor["ind1"], sin_autor["ind2"]) == ("0", "0")


def test_a_inicial_no_es_articulo():
    campo = marc.campos(ficha.a_marc(FichaLibro(cota="1", titulo="A orillas del río"), None), "245")[0]
    assert campo["ind2"] == "0"
    campo = marc.campos(ficha.a_marc(FichaLibro(cota="1", titulo="The Road"), None), "245")[0]
    assert campo["ind2"] == "4"


def test_edita_260_en_su_lugar():
    base = {"leader": "00000nam a22000007i 4500", "fields": [
        {"008": "200101s1990    ve            000 0 spa d"},
        {"245": {"ind1": "0", "ind2": "0", "subfields": [{"a": "Viejo"}]}},
        {"260": {"ind1": " ", "ind2": " ", "subfields": [
            {"a": "Valencia :"}, {"b": "Vadell,"}, {"c": "1990"}]}}]}
    previa = ficha.desde_marc(base)
    assert (previa.lugar, previa.editorial, previa.ano) == ("Valencia", "Vadell", 1990)
    nueva = previa.model_copy(update={"editorial": "Monte Ávila", "ano": 1991})
    registro = ficha.a_marc(nueva, base)
    assert marc.campos(registro, "264") == []
    (campo,) = marc.campos(registro, "260")
    assert campo["subfields"] == [{"a": "Valencia :"}, {"b": "Monte Ávila"}, {"c": "1991"}]
    assert ficha.desde_marc(registro).editorial == "Monte Ávila"


def test_260_y_264_juntos_escribe_264():
    base = {"leader": "x", "fields": [
        {"260": {"ind1": " ", "ind2": " ", "subfields": [{"a": "A"}]}},
        {"264": {"ind1": " ", "ind2": "1", "subfields": [{"a": "B"}]}}]}
    registro = ficha.a_marc(FichaLibro(cota="1 A", titulo="T", lugar="C"), base)
    assert marc.campos(registro, "260")[0]["subfields"] == [{"a": "A"}]  # solo se toca el que se leyó
    assert marc.campos(registro, "264")[0]["subfields"] == [{"a": "C"}]


def test_cota_se_normaliza():
    registro = ficha.a_marc(FichaLibro(cota=" 616.39  h37 ", titulo="T"), None)
    (campo,) = marc.campos(registro, "092")
    assert marc.subcampos(campo, "a") == ["616.39"]
    assert marc.subcampos(campo, "b") == ["H37"]
    assert ficha.desde_marc(registro).cota == "616.39 H37"


def test_vacios_no_generan_campos():
    registro = ficha.a_marc(FichaLibro(cota="1 A", titulo="T", edicion="  ", materias=[]), None)
    assert not {"250", "650", "264", "260", "300", "020", "100", "700"} & set(_tags(registro))


def test_008_se_conserva_salvo_el_ano():
    base = {"leader": "x", "fields": [{"008": "200101s1990    ve            000 0 eng d"}]}
    r = ficha.a_marc(FichaLibro(cota="1", titulo="T", ano=2005), base)
    assert marc.campos(r, "008") == ["200101s2005    ve            000 0 eng d"]
    r = ficha.a_marc(FichaLibro(cota="1", titulo="T"), base)
    assert marc.campos(r, "008") == ["200101s        ve            000 0 eng d"]


def test_validacion_de_la_ficha():
    with pytest.raises(ValidationError):
        FichaLibro(cota="  ", titulo="T")
    with pytest.raises(ValidationError):
        FichaLibro(cota="1", titulo="")
    f = FichaLibro(cota="1", titulo=" T ", autor="  ", isbn=[" 1 ", ""])
    assert (f.titulo, f.autor, f.isbn) == ("T", None, ["1"])


def test_registro_sin_cota_se_puede_leer():
    r = ficha.desde_marc({"leader": "x", "fields": [
        {"245": {"ind1": "0", "ind2": "0", "subfields": [{"a": "Importado /"}]}}]})
    assert r.cota == "" and r.titulo == "Importado"


def _koha() -> dict:
    def c(tag, ind, *subs):
        return {tag: {"ind1": ind[0], "ind2": ind[1], "subfields": [{k: v} for k, v in subs]}}
    return {"leader": "00000nam a22000007i 4500", "fields": [
        {"008": "200101s1929    ve            000 0 spa d"},
        c("020", "  ", ("a", "9789800000001 :"), ("q", "(rústica)")),
        c("020", "  ", ("z", "9789800000999")),
        c("082", "04", ("a", "863")),
        c("100", "1 ", ("a", "Gallegos, Rómulo,"), ("d", "1884-1969.")),
        c("245", "10", ("a", "Doña Bárbara /"), ("n", "Primera parte"), ("p", "El lobo"),
          ("c", "Rómulo Gallegos.")),
        c("264", " 1", ("a", "Caracas :"), ("b", "Monte Ávila,"), ("c", "1929.")),
        c("264", " 4", ("c", "©1929")),
        c("500", "  ", ("a", "Primera nota.")),
        c("500", "  ", ("a", "Segunda nota.")),
        c("650", " 0", ("a", "Novela venezolana"), ("y", "Siglo XX"), ("2", "lcsh")),
        c("650", " 0", ("a", "Llanos"), ("z", "Venezuela")),
        c("700", "1 ", ("a", "Pérez, Ana,"), ("e", "ilustradora.")),
        c("952", "  ", ("a", "B"), ("p", "001"))]}


def _sin_092(registro: dict) -> list:
    return [c for c in registro["fields"] if "092" not in c]


def test_editar_solo_la_cota_de_un_registro_importado_no_pierde_nada():
    original = _koha()
    previa = ficha.desde_marc(original)
    assert (previa.autor, previa.otros_autores, previa.lugar) == (
        "Gallegos, Rómulo", ["Pérez, Ana"], "Caracas")
    resultado = ficha.a_marc(previa.model_copy(update={"cota": "863 g3"}), original)
    assert _sin_092(resultado) == original["fields"]
    assert marc.campos(resultado, "092")[0]["subfields"] == [{"a": "863"}, {"b": "G3"}]


def test_quitar_una_materia_conserva_las_otras_con_subdivisiones():
    original = _koha()
    previa = ficha.desde_marc(original)
    resultado = ficha.a_marc(previa.model_copy(update={
        "cota": "1 A", "materias": ["Llanos"]}), original)
    assert marc.campos(resultado, "650") == [marc.campos(original, "650")[1]]
    nuevo = ficha.a_marc(previa.model_copy(update={
        "cota": "1 A", "materias": ["Novela venezolana", "Llanos", "Selva"]}), original)
    assert marc.campos(nuevo, "650")[:2] == marc.campos(original, "650")
    assert marc.campos(nuevo, "650")[2] == {
        "ind1": " ", "ind2": "4", "subfields": [{"a": "Selva"}]}


def test_cambiar_solo_el_titulo_conserva_n_p_y_el_indicador_con_110():
    original = _koha()
    original["fields"] = [c for c in original["fields"] if "100" not in c]
    original["fields"].insert(3, {"110": {"ind1": "2", "ind2": " ",
                                           "subfields": [{"a": "Editorial X."}]}})
    previa = ficha.desde_marc(original)
    resultado = ficha.a_marc(previa.model_copy(update={"cota": "1 A", "titulo": "La barbara"}),
                             original)
    campo = marc.campos(resultado, "245")[0]
    assert (campo["ind1"], campo["ind2"]) == ("1", "3")
    assert campo["subfields"] == [{"a": "La barbara"}, {"n": "Primera parte"},
                                  {"p": "El lobo"}, {"c": "Rómulo Gallegos."}]
    assert marc.campos(resultado, "110") == marc.campos(original, "110")


def test_cambiar_el_autor_edita_el_a_y_quita_el_d():
    original = _koha()
    previa = ficha.desde_marc(original)
    resultado = ficha.a_marc(previa.model_copy(update={"cota": "1 A", "autor": "Otro, Autor"}),
                             original)
    assert marc.campos(resultado, "100")[0] == {
        "ind1": "1", "ind2": " ", "subfields": [{"a": "Otro, Autor"}]}


def test_la_publicacion_solo_toca_el_264_de_publicacion():
    original = _koha()
    previa = ficha.desde_marc(original)
    resultado = ficha.a_marc(previa.model_copy(update={"cota": "1 A", "editorial": "Otra"}),
                             original)
    p264 = marc.campos(resultado, "264")
    assert p264[0]["subfields"] == [{"a": "Caracas :"}, {"b": "Otra"}, {"c": "1929."}]
    assert p264[1] == marc.campos(original, "264")[1]


def test_un_264_de_copyright_solo_no_es_la_publicacion():
    base = {"leader": "x", "fields": [
        {"264": {"ind1": " ", "ind2": "4", "subfields": [{"c": "©2001"}]}}]}
    previa = ficha.desde_marc(base)
    assert (previa.lugar, previa.editorial) == (None, None)
    resultado = ficha.a_marc(previa.model_copy(update={"cota": "1", "titulo": "T", "lugar": "Lima"}),
                             base)
    assert marc.campos(resultado, "264")[0] == base["fields"][0]["264"]
    assert marc.campos(resultado, "264")[1]["ind2"] == "1"


def test_limpieza_uniforme_de_la_puntuacion_al_leer():
    f = ficha.desde_marc(_koha())
    assert (f.autor, f.otros_autores, f.titulo, f.editorial) == (
        "Gallegos, Rómulo", ["Pérez, Ana"], "Doña Bárbara", "Monte Ávila")
    assert f.isbn == ["9789800000001"]
    assert f.notas == "Primera nota."


def test_desde_marc_normaliza_la_cota():
    base = {"leader": "x", "fields": [
        {"092": {"ind1": " ", "ind2": " ", "subfields": [{"a": "616.39"}, {"b": "h37"}]}},
        {"245": {"ind1": "0", "ind2": "0", "subfields": [{"a": "T"}]}}]}
    assert ficha.desde_marc(base).cota == "616.39 H37"
    resultado = ficha.a_marc(ficha.desde_marc(base), base)
    assert resultado["fields"] == base["fields"]  # sin cambios: el 092 original no se toca


def _con_092(*subs) -> dict:
    return {"leader": "x", "fields": [
        {"092": {"ind1": " ", "ind2": " ", "subfields": [{k: v} for k, v in subs]}},
        {"245": {"ind1": "0", "ind2": "0", "subfields": [{"a": "T"}]}}]}


def test_cota_completa_en_092_a_se_reescribe_como_unidad():
    base = _con_092(("a", "863 G3"), ("9", "local"))
    previa = ficha.desde_marc(base)
    assert previa.cota == "863 G3"
    r = ficha.a_marc(previa.model_copy(update={"cota": "863 G4"}), base)
    assert marc.campos(r, "092")[0]["subfields"] == [{"a": "863"}, {"b": "G4"}, {"9": "local"}]
    assert ficha.desde_marc(r).cota == "863 G4"
    r = ficha.a_marc(previa.model_copy(update={"cota": "900 G3"}), base)
    assert ficha.desde_marc(r).cota == "900 G3"
    r = ficha.a_marc(previa.model_copy(update={"cota": "900"}), _con_092(("a", "863"), ("b", "G3")))
    assert marc.campos(r, "092")[0]["subfields"] == [{"a": "900"}]  # sin $b viejo


def test_el_autor_se_lee_y_edita_en_el_primer_1xx():
    base = {"leader": "x", "fields": [
        {"110": {"ind1": "2", "ind2": " ", "subfields": [{"a": "Editorial X."}, {"b": "Sede"}]}},
        {"245": {"ind1": "1", "ind2": "0", "subfields": [{"a": "T"}]}}]}
    previa = ficha.desde_marc(base)
    assert previa.autor == "Editorial X."
    r = ficha.a_marc(previa.model_copy(update={"cota": "1", "autor": "Editorial Y"}), base)
    assert marc.campos(r, "100") == []
    assert marc.campos(r, "110")[0]["subfields"] == [{"a": "Editorial Y"}, {"b": "Sede"}]
    r = ficha.a_marc(previa.model_copy(update={"cota": "1", "autor": None}), base)
    assert marc.campos(r, "110") == marc.campos(base, "110")  # no se borra en silencio
    r = ficha.a_marc(FichaLibro(cota="1", titulo="T", autor="Nuevo, Autor"),
                     {"leader": "x", "fields": [base["fields"][1]]})
    assert marc.campos(r, "100")[0] == {"ind1": "1", "ind2": " ",
                                        "subfields": [{"a": "Nuevo, Autor"}]}


def test_cambiar_el_autor_100_quita_d_y_q_y_conserva_e():
    base = {"leader": "x", "fields": [
        {"100": {"ind1": "1", "ind2": " ", "subfields": [
            {"a": "Viejo, A."}, {"q": "(Antonio)"}, {"d": "1900-1980"}, {"e": "autor"}]}},
        {"245": {"ind1": "1", "ind2": "0", "subfields": [{"a": "T"}]}}]}
    previa = ficha.desde_marc(base)
    r = ficha.a_marc(previa.model_copy(update={"cota": "1", "autor": "Nuevo, B."}), base)
    assert marc.campos(r, "100")[0]["subfields"] == [{"a": "Nuevo, B."}, {"e": "autor"}]
    sin_cambio = ficha.a_marc(previa.model_copy(update={"cota": "1"}), base)
    assert marc.campos(sin_cambio, "100") == marc.campos(base, "100")  # $d y $q intactos


def test_editar_sin_cambios_con_inicial_en_el_autor_deja_el_marc_identico():
    original = _koha()
    for campo in original["fields"]:
        if "100" in campo:
            campo["100"]["subfields"] = [{"a": "Murray, Robert K."}]
    previa = ficha.desde_marc(original)
    assert previa.autor == "Murray, Robert K."
    assert marc.derivar(original)["autor"] == "Murray, Robert K."
    assert ficha.a_marc(previa, original) == original
