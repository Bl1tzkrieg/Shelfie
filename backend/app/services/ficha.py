"""Ficha simple del libro ↔ MARC 21 (MARC-in-JSON).

El formulario reemplaza solo los campos de `CAMPOS_DEL_FORMULARIO`; el resto del
registro (cabecera, 008 salvo las posiciones 07-10, 040, 082, 856, 952…) se conserva
tal cual. Los valores se guardan sin puntuación ISBD final: `marc.derivar` ya la
tolera y la ida y vuelta queda exacta.
"""

import copy
import re
from typing import List, Optional, Tuple

from pydantic import ValidationError

from app.core import marc_plantillas
from app.core.signaturas import normalizar_cota
from app.schemas import FichaLibro
from app.services import marc

CAMPOS_DEL_FORMULARIO = {"020", "092", "100", "245", "250", "260", "264", "300",
                         "500", "520", "650", "700"}

_ARTICULOS = ("el ", "la ", "los ", "las ", "lo ", "un ", "una ", "the ", "a ", "an ")
# Puntuación ISBD de enlace que sobra en el formulario (" /", " :", ","). El punto se respeta
# porque cierra abreviaturas ("Jr.", "ed.").
_ENLACE_FINAL = re.compile(r"\s*[/:;,=]+\s*$")

Campo = Tuple[str, object]


def _campo(tag: str, subcampos: List[Tuple[str, str]], ind1: str = " ", ind2: str = " ") -> Campo:
    return tag, {"ind1": ind1, "ind2": ind2, "subfields": [{c: v} for c, v in subcampos]}


def _con_valor(*pares: Tuple[str, Optional[str]]) -> List[Tuple[str, str]]:
    return [(c, v) for c, v in pares if v]


def _indicador_articulo(titulo: str) -> str:
    minuscula = titulo.lower()
    for articulo in _ARTICULOS:
        if minuscula.startswith(articulo):
            return str(len(articulo))
    return "0"


def _generados(ficha: FichaLibro, con_260: bool) -> List[Campo]:
    """Campos del formulario, ya en orden numérico de etiqueta."""
    cota = normalizar_cota(ficha.cota) or ""
    clase, _, libreria = cota.partition(" ")
    generados: List[Campo] = [
        _campo("092", _con_valor(("a", clase), ("b", libreria or None)))]
    generados += [_campo("020", [("a", i)]) for i in ficha.isbn]
    if ficha.autor:
        generados.append(_campo("100", [("a", ficha.autor)], ind1="1"))
    generados.append(_campo(
        "245", _con_valor(("a", ficha.titulo), ("b", ficha.subtitulo), ("c", ficha.mencion)),
        ind1="1" if ficha.autor else "0", ind2=_indicador_articulo(ficha.titulo)))
    if ficha.edicion:
        generados.append(_campo("250", [("a", ficha.edicion)]))
    publicacion = _con_valor(("a", ficha.lugar), ("b", ficha.editorial),
                             ("c", str(ficha.ano) if ficha.ano is not None else None))
    if publicacion:
        generados.append(_campo("260", publicacion) if con_260
                         else _campo("264", publicacion, ind2="1"))
    fisica = _con_valor(("a", ficha.paginas), ("b", ficha.ilustraciones),
                        ("c", ficha.dimensiones))
    if fisica:
        generados.append(_campo("300", fisica))
    if ficha.notas:
        generados.append(_campo("500", [("a", ficha.notas)]))
    if ficha.descripcion:
        generados.append(_campo("520", [("a", ficha.descripcion)]))
    generados += [_campo("650", [("a", m)], ind2="4") for m in ficha.materias]
    generados += [_campo("700", [("a", a)], ind1="1") for a in ficha.otros_autores]
    return generados


def _actualizar_008(campos: List[dict], ano: Optional[int]) -> Optional[Campo]:
    """Cambia solo las posiciones 07-10 del 008 existente; si no hay, devuelve uno nuevo."""
    for campo in campos:
        valor = campo.get("008")
        if isinstance(valor, str) and len(valor) == marc.LONGITUD_008:
            campo["008"] = valor[:7] + (f"{ano:04d}" if ano is not None else "    ") + valor[11:]
            return None
    campos[:] = [c for c in campos if "008" not in c]  # un 008 de largo inválido se rehace
    return "008", marc.campo_008(ano)


def a_marc(ficha: FichaLibro, marc_actual: Optional[dict] = None) -> dict:
    """MARC con los campos del formulario reemplazados; lo demás queda como estaba."""
    if marc_actual is None:
        marc_actual = {"leader": marc_plantillas.obtener(None).lider, "fields": []}
    registro = copy.deepcopy(marc_actual)
    campos: List[dict] = registro.setdefault("fields", [])
    registro.setdefault("leader", marc_plantillas.obtener(None).lider)

    con_260 = bool(marc.campos(registro, "260")) and not marc.campos(registro, "264")
    campos[:] = [c for c in campos if next(iter(c)) not in CAMPOS_DEL_FORMULARIO]

    generados = _generados(ficha, con_260)
    nuevo_008 = _actualizar_008(campos, ficha.ano)
    if nuevo_008:
        generados.insert(0, nuevo_008)
    for tag, valor in generados:
        posicion = next((i for i, c in enumerate(campos) if next(iter(c)) > tag), len(campos))
        campos.insert(posicion, {tag: valor})
    return registro


def _texto(valor: Optional[str]) -> Optional[str]:
    return (_ENLACE_FINAL.sub("", valor).strip() or None) if valor else None


def _publicacion(registro: dict) -> Optional[object]:
    """264 de publicación (2.º indicador 1); si no hay, el 260; y, por último, cualquier 264."""
    candidatos = marc.campos(registro, "264")
    for campo in candidatos:
        if isinstance(campo, dict) and campo.get("ind2") == "1":
            return campo
    anteriores = marc.campos(registro, "260")
    if anteriores:
        return anteriores[0]
    return candidatos[0] if candidatos else None


def desde_marc(registro: dict) -> FichaLibro:
    """Ficha para el formulario a partir de un registro MARC (de cualquier origen)."""
    publicacion = _publicacion(registro)

    def sub(tag: str, codigo: str) -> Optional[str]:
        return marc.primero(registro, tag, codigo)

    def todos(tag: str, codigo: str = "a") -> List[str]:
        return [v for c in marc.campos(registro, tag) for v in marc.subcampos(c, codigo)]

    clase, libreria = sub("092", "a"), sub("092", "b")
    cota = " ".join(p for p in (clase, libreria) if p)
    datos = dict(
        cota=cota,
        titulo=_texto(sub("245", "a")) or "",
        subtitulo=_texto(sub("245", "b")),
        mencion=_texto(sub("245", "c")),
        autor=sub("100", "a"),
        otros_autores=todos("700"),
        edicion=sub("250", "a"),
        lugar=_texto((marc.subcampos(publicacion, "a") or [None])[0]),
        editorial=_texto((marc.subcampos(publicacion, "b") or [None])[0]),
        ano=marc.ano_de(registro),
        paginas=sub("300", "a"),
        ilustraciones=sub("300", "b"),
        dimensiones=sub("300", "c"),
        isbn=todos("020"),
        materias=todos("650"),
        descripcion=sub("520", "a"),
        notas=sub("500", "a"),
    )
    try:
        return FichaLibro(**datos)
    except ValidationError:
        # Registro importado sin 092 o sin 245 $a: se muestra igual (cota vacía) para poder completarlo.
        return FichaLibro.model_construct(**datos)
