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
    assert campo["subfields"] == [{"a": "Valencia"}, {"b": "Monte Ávila"}, {"c": "1991"}]
    assert ficha.desde_marc(registro).editorial == "Monte Ávila"


def test_260_y_264_juntos_escribe_264():
    base = {"leader": "x", "fields": [
        {"260": {"ind1": " ", "ind2": " ", "subfields": [{"a": "A"}]}},
        {"264": {"ind1": " ", "ind2": "1", "subfields": [{"a": "B"}]}}]}
    registro = ficha.a_marc(FichaLibro(cota="1 A", titulo="T", lugar="C"), base)
    assert marc.campos(registro, "260") == []
    assert marc.campos(registro, "264")[0]["ind2"] == "1"


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
