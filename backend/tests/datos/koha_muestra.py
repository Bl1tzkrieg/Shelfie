"""Archivo de muestra al estilo de una exportación de Koha (ISO 2709, UTF-8).

Tres registros con ejemplares en 952 ($a y $b = biblioteca, $o cota, $p código, $t copia,
$y tipo de ítem) y el 999 con el biblionumber de Koha:

1. «Doña Bárbara»: con 092, 260 (catalogación vieja) y dos ejemplares; el segundo sin código.
2. «Química general»: sin 092 pero con 082; su ejemplar no trae $o.
3. «Cuentos completos»: con 092, 264 y un ejemplar.
"""

from pymarc import Field, Indicators, Record, Subfield

BIBLIOTECA = "UCV"


def _campo(tag, ind1=" ", ind2=" ", **subcampos):
    return Field(tag=tag, indicators=Indicators(ind1, ind2),
                 subfields=[Subfield(c, v) for c, v in subcampos.items()])


def _ejemplar(*, o=None, p=None, t=None, y="BK"):
    subs = [("a", BIBLIOTECA), ("b", BIBLIOTECA)]
    subs += [(c, v) for c, v in (("o", o), ("p", p), ("t", t)) if v]
    subs += [("y", y), ("1", "0")]
    return Field(tag="952", indicators=Indicators(" ", " "),
                 subfields=[Subfield(c, v) for c, v in subs])


def _registro(biblionumber, campos, ejemplares):
    r = Record(force_utf8=True)
    r.leader = "00000nam a2200000 a 4500"
    r.add_field(Field(tag="001", data=str(biblionumber)))
    r.add_field(Field(tag="003", data="KOHA"))
    r.add_field(Field(tag="008", data="850101s1985    ve            000 1 spa d"))
    for campo in campos:
        r.add_field(campo)
    r.add_field(_campo("942", c="BK"))
    for e in ejemplares:
        r.add_field(e)
    r.add_field(_campo("999", c=str(biblionumber), d=str(biblionumber)))
    return r


def registros():
    return [
        _registro(101, [
            _campo("020", a="980-01-0012-3"),
            _campo("092", a="863", b="G16"),
            _campo("100", "1", a="Gallegos, Rómulo,", d="1884-1969."),
            _campo("245", "1", "0", a="Doña Bárbara /", c="Rómulo Gallegos."),
            _campo("260", a="Caracas :", b="Monte Ávila,", c="1985."),
            _campo("650", " ", "4", a="Novela venezolana."),
            _campo("650", " ", "4", a="Llanos (Venezuela)"),
        ], [_ejemplar(o="863 G16", p="KOHA-1", t="c.1"),
            _ejemplar(o="863 G16", t="c.2")]),
        _registro(102, [
            _campo("020", a="9789701054949"),
            _campo("082", "0", "4", a="540", b="C43", **{"2": "23"}),
            _campo("100", "1", a="Chang, Raymond."),
            _campo("245", "1", "0", a="Química general /", c="Raymond Chang."),
            _campo("264", " ", "1", a="México :", b="McGraw-Hill,", c="2010."),
            _campo("650", " ", "4", a="Química."),
        ], [_ejemplar(p="KOHA-3", y="LIB")]),
        _registro(103, [
            _campo("092", a="868", b="Q6"),
            _campo("100", "1", a="Quiroga, Horacio."),
            _campo("245", "1", "0", a="Cuentos completos"),
            _campo("264", " ", "1", a="Buenos Aires :", b="Losada,", c="2004."),
            _campo("650", " ", "4", a="Cuentos uruguayos."),
        ], [_ejemplar(o="868 Q6", p="KOHA-4", t="c.1")]),
    ]


def iso2709() -> bytes:
    return b"".join(r.as_marc() for r in registros())
