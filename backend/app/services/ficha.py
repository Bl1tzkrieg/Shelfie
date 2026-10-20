"""Ficha simple del libro ↔ MARC 21 (MARC-in-JSON).

Regla clave: el formulario cambia solo lo que el usuario cambió. `a_marc` compara la ficha
con `desde_marc(marc_actual)` y trabaja por grupo (092, 020, 100, 245, 250, publicación, 300,
500, 520, 650, 700):

- lo que no cambió queda byte a byte como estaba (indicadores, subcampos ajenos, puntuación);
- en los grupos de valor único se edita la primera aparición, solo los subcampos que el
  formulario controla;
- los grupos repetibles (020, 650, 700) se concilian por `$a`;
- todo lo demás (cabecera, 008 salvo 07-10, 040, 082, 856, 952…) no se toca.

Los valores nuevos se guardan planos, sin puntuación ISBD; `marc.derivar` la tolera.
"""

import copy
import re
from typing import Dict, List, Optional, Tuple

from pydantic import ValidationError

from app.core import marc_plantillas
from app.core.signaturas import normalizar_cota
from app.schemas import FichaLibro
from app.services import marc

CAMPOS_DEL_FORMULARIO = {"020", "092", "100", "245", "250", "260", "264", "300",
                         "500", "520", "650", "700"}

_ARTICULOS = ("el ", "la ", "los ", "las ", "lo ", "un ", "una ", "the ", "an ")
# Puntuación ISBD de enlace que sobra en el formulario (" /", " :", ","). El punto se respeta
# porque cierra abreviaturas ("Jr.", "ed.").
_ENLACE_FINAL = re.compile(r"\s*[/:;,=]+\s*$")
_ORDEN_SUBCAMPOS = {"245": "abnpc", "092": "ab"}
_UNICOS = ("092", "100", "245", "250", "pub", "300", "500", "520")
_UNOS_1XX = ("100", "110", "111", "130")

Valores = Dict[str, Optional[str]]


# --- Lectura -----------------------------------------------------------------------

def _texto(valor: Optional[str]) -> Optional[str]:
    return (_ENLACE_FINAL.sub("", valor).strip() or None) if valor else None


def _primer_campo(registro: dict, tag: str) -> Optional[object]:
    campos = marc.campos(registro, tag)
    return campos[0] if campos else None


def _publicacion(registro: dict) -> Optional[object]:
    """El campo de publicación: 264 con 2.º indicador 1 o, si no hay, el 260. Un 264 de
    copyright, producción o distribución nunca cuenta como publicación."""
    for campo in marc.campos(registro, "264"):
        if isinstance(campo, dict) and campo.get("ind2") == "1":
            return campo
    anteriores = marc.campos(registro, "260")
    return anteriores[0] if anteriores else None


def _campo_de(registro: dict, grupo: str) -> Optional[object]:
    return _publicacion(registro) if grupo == "pub" else _primer_campo(registro, grupo)


def _sub(campo: Optional[object], codigo: str) -> Optional[str]:
    valores = marc.subcampos(campo, codigo)
    return _texto(valores[0]) if valores else None


def _todos(registro: dict, tag: str) -> List[str]:
    limpios = (_texto(v) for c in marc.campos(registro, tag) for v in marc.subcampos(c, "a"))
    return [v for v in limpios if v]


def desde_marc(registro: dict) -> FichaLibro:
    """Ficha para el formulario a partir de un registro MARC (de cualquier origen)."""
    def sub(grupo: str, codigo: str) -> Optional[str]:
        return _sub(_campo_de(registro, grupo), codigo)

    cota = normalizar_cota(" ".join(p for p in (sub("092", "a"), sub("092", "b")) if p)) or ""
    datos = dict(
        cota=cota,
        titulo=sub("245", "a") or "",
        subtitulo=sub("245", "b"),
        mencion=sub("245", "c"),
        autor=sub("100", "a"),
        otros_autores=_todos(registro, "700"),
        edicion=sub("250", "a"),
        lugar=sub("pub", "a"),
        editorial=sub("pub", "b"),
        ano=marc.ano_de(registro),
        paginas=sub("300", "a"),
        ilustraciones=sub("300", "b"),
        dimensiones=sub("300", "c"),
        isbn=_todos(registro, "020"),
        materias=_todos(registro, "650"),
        descripcion=sub("520", "a"),
        notas=sub("500", "a"),
    )
    try:
        return FichaLibro(**datos)
    except ValidationError:
        # Registro importado sin 092 o sin 245 $a: se muestra igual (cota vacía) para poder completarlo.
        return FichaLibro.model_construct(**datos)


# --- Escritura ---------------------------------------------------------------------

def _valores_unicos(ficha: FichaLibro) -> Dict[str, Valores]:
    cota = normalizar_cota(ficha.cota) or ""
    clase, _, libreria = cota.partition(" ")
    return {
        "092": {"a": clase or None, "b": libreria or None},
        "100": {"a": ficha.autor},
        "245": {"a": ficha.titulo or None, "b": ficha.subtitulo, "c": ficha.mencion},
        "250": {"a": ficha.edicion},
        "pub": {"a": ficha.lugar, "b": ficha.editorial,
                "c": str(ficha.ano) if ficha.ano is not None else None},
        "300": {"a": ficha.paginas, "b": ficha.ilustraciones, "c": ficha.dimensiones},
        "500": {"a": ficha.notas},
        "520": {"a": ficha.descripcion},
    }


def _insertar(campos: List[dict], tag: str, valor: object) -> None:
    """Inserta antes del primer campo de etiqueta mayor; el resto conserva su orden."""
    posicion = next((i for i, c in enumerate(campos) if next(iter(c)) > tag), len(campos))
    campos.insert(posicion, {tag: valor})


def _campo_nuevo(subcampos: List[Tuple[str, str]], ind1: str = " ", ind2: str = " ") -> dict:
    return {"ind1": ind1, "ind2": ind2, "subfields": [{c: v} for c, v in subcampos]}


def _poner_subcampo(subcampos: List[dict], codigo: str, valor: Optional[str], orden: str) -> None:
    """Cambia, quita o agrega un subcampo; los demás no se mueven."""
    for i, s in enumerate(subcampos):
        if codigo in s:
            if valor is None:
                del subcampos[i]
            elif _texto(s[codigo]) != valor:
                s[codigo] = valor
            return
    if valor is None:
        return
    rango = orden.index(codigo)
    posicion = 0
    for i, s in enumerate(subcampos):
        otro = next(iter(s))
        if otro in orden and orden.index(otro) <= rango:
            posicion = i + 1
    subcampos.insert(posicion, {codigo: valor})


def _quitar(campos: List[dict], valor: object) -> None:
    campos[:] = [c for c in campos if next(iter(c.values())) is not valor]


def _editar_unico(campos: List[dict], registro: dict, grupo: str,
                  cambios: Valores, nuevos: Valores) -> None:
    campo = _campo_de(registro, grupo)
    orden = _ORDEN_SUBCAMPOS.get(grupo, "abc")
    if campo is not None:
        for codigo, valor in cambios.items():
            _poner_subcampo(campo["subfields"], codigo, valor, orden)
        if not campo["subfields"]:
            _quitar(campos, campo)
        return
    subcampos = [(c, v) for c, v in nuevos.items() if v]
    if not subcampos:
        return
    if grupo == "pub":
        _insertar(campos, "264", _campo_nuevo(subcampos, ind2="1"))
    else:
        ind1 = "1" if grupo == "100" else " "
        _insertar(campos, grupo, _campo_nuevo(subcampos, ind1=ind1))


def _conciliar(campos: List[dict], registro: dict, tag: str, deseados: List[str],
               ind1: str, ind2: str) -> None:
    """Deja los campos cuyo $a sigue en la lista, quita los que ya no están y agrega los nuevos.
    Un campo sin $a (por ejemplo un 020 solo con $z) nunca se toca."""
    pendientes = list(deseados)
    for campo in marc.campos(registro, tag):
        valores = marc.subcampos(campo, "a")
        if not valores:
            continue
        actual = _texto(valores[0])
        if actual in pendientes:
            pendientes.remove(actual)
        else:
            _quitar(campos, campo)
    for valor in pendientes:
        _insertar(campos, tag, _campo_nuevo([("a", valor)], ind1=ind1, ind2=ind2))


def _tiene_1xx(campos: List[dict]) -> bool:
    return any(next(iter(c)) in _UNOS_1XX for c in campos)


def _ajustar_008(campos: List[dict], ano: Optional[int], crear: bool) -> None:
    anio = f"{ano:04d}" if ano is not None else "    "
    for campo in campos:
        valor = campo.get("008")
        if isinstance(valor, str) and len(valor) == marc.LONGITUD_008:
            campo["008"] = valor[:7] + anio + valor[11:]
            return
    if crear or any("008" in c for c in campos):
        campos[:] = [c for c in campos if "008" not in c]  # uno de largo inválido se rehace
        _insertar(campos, "008", marc.campo_008(ano))


def a_marc(ficha: FichaLibro, marc_actual: Optional[dict] = None) -> dict:
    """MARC con los cambios del formulario aplicados; lo que no cambió queda como estaba."""
    nuevo = marc_actual is None
    if nuevo:
        marc_actual = {"leader": marc_plantillas.obtener(None).lider, "fields": []}
    registro = copy.deepcopy(marc_actual)
    registro.setdefault("leader", marc_plantillas.obtener(None).lider)
    campos: List[dict] = registro.setdefault("fields", [])

    previa = desde_marc(registro)
    ahora, antes = _valores_unicos(ficha), _valores_unicos(previa)
    cambios = {g: {c: v for c, v in ahora[g].items() if v != antes[g][c]} for g in _UNICOS}

    for tag in ("092", "020", "100", "245", "250", "pub", "300", "500", "520", "650", "700"):
        if tag == "020" and ficha.isbn != previa.isbn:
            _conciliar(campos, registro, "020", ficha.isbn, " ", " ")
        elif tag == "650" and ficha.materias != previa.materias:
            _conciliar(campos, registro, "650", ficha.materias, " ", "4")
        elif tag == "700" and ficha.otros_autores != previa.otros_autores:
            _conciliar(campos, registro, "700", ficha.otros_autores, "1", " ")
        elif tag in _UNICOS and cambios[tag]:
            _editar_unico(campos, registro, tag, cambios[tag], ahora[tag])

    campo245 = _primer_campo(registro, "245")
    if campo245 is not None and (cambios["245"] or cambios["100"]):
        campo245["ind1"] = "1" if _tiene_1xx(campos) else "0"
        if "a" in cambios["245"]:
            campo245["ind2"] = _indicador_articulo(ficha.titulo)

    if nuevo or ficha.ano != previa.ano:
        _ajustar_008(campos, ficha.ano, crear=nuevo)
    return registro


def _indicador_articulo(titulo: str) -> str:
    minuscula = titulo.lower()
    for articulo in _ARTICULOS:
        if minuscula.startswith(articulo):
            return str(len(articulo))
    return "0"
