"""Registros MARC21: forma canónica, validación contra la plantilla y datos derivados.

El registro MARC es la fuente. Título, autor, materia, año e ISBN
de `registros_bibliograficos` se derivan de él cada vez que se guarda, para que
la búsqueda, las listas y la circulación no tengan que leer MARC.

Forma canónica (MARC-in-JSON, la misma de pymarc `as_dict()`):

    {"leader": "00000nam a22000007i 4500",
     "fields": [{"008": "261007s2020    ve            000 0 spa d"},
                {"245": {"ind1": "1", "ind2": "0",
                         "subfields": [{"a": "Cien años de soledad /"}, {"c": "…"}]}}]}
"""

import io
import json
import re
from datetime import date
from typing import Dict, Iterable, List, Optional, Tuple

import pymarc

from app.core import marc_plantillas
from app.core.errores import ErroresDeValidacion, ReglaIncumplida
from app.core.marc_plantillas import Plantilla

LONGITUD_LIDER = 24
LONGITUD_008 = 40
_TAG = re.compile(r"^\d{3}$")
_CODIGO = re.compile(r"^[a-z0-9]$")
_INDICADOR = re.compile(r"^[ 0-9a-z]$")
_ANO = re.compile(r"(1[0-9]{3}|20[0-9]{2})")
# Puntuación ISBD que cierra un subcampo ("Cien años de soledad /").
_PUNTUACION_FINAL = re.compile(r"[\s/:;,=.]+$")
_ENLACE_FINAL = re.compile(r"[\s/:;,=]+$")
# Abreviaturas que terminan en punto y no se pierden al limpiar («Jr.», «ed.»).
_ABREVIATURAS = {"jr", "sr", "sra", "dr", "dra", "lic", "ing", "ed", "eds", "p", "pp", "il", "vol",
                 "no", "núm", "comp", "coord", "trad", "etc", "ltda", "cía", "cia", "inc", "co",
                 "hnos", "mons", "prof", "gral"}


def _error(msg: str, *loc) -> dict:
    return {"loc": [str(x) for x in loc], "msg": msg}


# --- Forma canónica ----------------------------------------------------------------

def normalizar(marc: dict, plantilla: Optional[Plantilla] = None) -> dict:
    """Limpia un registro recibido: recorta valores, quita subcampos y campos vacíos,
    completa indicadores y líder, y ordena por etiqueta. Lanza 422 si la estructura
    no es MARC-in-JSON."""
    errores: List[dict] = []
    if not isinstance(marc, dict):
        raise ErroresDeValidacion([_error("El registro MARC debe ser un objeto JSON")])

    plantilla = plantilla or marc_plantillas.obtener(None)
    lider = str(marc.get("leader") or plantilla.lider)
    lider = (lider + " " * LONGITUD_LIDER)[:LONGITUD_LIDER]

    campos: List[Tuple[str, object]] = []
    campos_crudos = marc.get("fields") or []
    if not isinstance(campos_crudos, list):
        errores.append(_error("«fields» debe ser una lista de campos", "fields"))
        campos_crudos = []
    for i, campo in enumerate(campos_crudos):
        if not isinstance(campo, dict) or len(campo) != 1:
            errores.append(_error(f"El campo #{i + 1} no tiene la forma {{etiqueta: valor}}", i))
            continue
        tag, valor = next(iter(campo.items()))
        tag = str(tag).strip()
        if not _TAG.match(tag):
            errores.append(_error(f"«{tag}» no es una etiqueta MARC (tres dígitos)", tag))
            continue
        if tag < "010":
            texto = valor if isinstance(valor, str) else ""
            if texto.strip():
                campos.append((tag, texto.rstrip("\n")))
            continue
        if not isinstance(valor, dict):
            errores.append(_error(f"El campo {tag} debe tener indicadores y subcampos", tag))
            continue
        subcampos = []
        crudos = valor.get("subfields") or []
        if not isinstance(crudos, list):
            errores.append(_error(f"Los subcampos de {tag} deben ser una lista", tag))
            continue
        for sub in crudos:
            if not isinstance(sub, dict) or len(sub) != 1:
                errores.append(_error(f"Subcampo mal formado en {tag}", tag))
                continue
            codigo, texto = next(iter(sub.items()))
            codigo = str(codigo).strip().lower()
            texto = "" if texto is None else str(texto).strip()
            if not texto:
                continue
            if not _CODIGO.match(codigo):
                errores.append(_error(f"«{codigo}» no es un código de subcampo válido en {tag}",
                                      tag, codigo))
                continue
            subcampos.append({codigo: texto})
        if not subcampos:
            continue
        indicadores = []
        for nombre in ("ind1", "ind2"):
            ind = str(valor.get(nombre) if valor.get(nombre) is not None else " ")
            ind = (ind or " ")[:1].lower()
            if not _INDICADOR.match(ind):
                errores.append(_error(f"Indicador «{ind}» no válido en {tag}", tag, nombre))
                ind = " "
            indicadores.append(ind)
        campos.append((tag, {"ind1": indicadores[0], "ind2": indicadores[1],
                             "subfields": subcampos}))

    if errores:
        raise ErroresDeValidacion(errores)
    campos.sort(key=lambda c: c[0])  # estable: conserva el orden dentro de cada etiqueta
    return {"leader": lider, "fields": [{tag: valor} for tag, valor in campos]}


def campos(marc: dict, tag: str) -> List[object]:
    return [c[tag] for c in marc.get("fields", []) if tag in c]


def subcampos(campo: object, codigo: str) -> List[str]:
    if not isinstance(campo, dict):
        return []
    return [s[codigo] for s in campo.get("subfields", []) if codigo in s]


def primero(marc: dict, tag: str, codigo: str) -> Optional[str]:
    for campo in campos(marc, tag):
        valores = subcampos(campo, codigo)
        if valores:
            return valores[0]
    return None


def _limpio(texto: Optional[str]) -> Optional[str]:
    if not texto:
        return None
    texto = _ENLACE_FINAL.sub("", texto.strip())
    if texto.endswith(".") and not _cierra_abreviatura(texto):
        texto = _PUNTUACION_FINAL.sub("", texto)
    return texto or None


def _cierra_abreviatura(texto: str) -> bool:
    """El punto final es parte de la palabra: una inicial («K.»), una sigla («S.A.») o una
    abreviatura conocida («Jr.», «ed.»)."""
    palabra = texto.split()[-1]
    sin_punto = palabra.rstrip(".")
    return (len(sin_punto) == 1 or "." in sin_punto
            or sin_punto.lower() in _ABREVIATURAS)


# --- Validación --------------------------------------------------------------------

def validar(marc: dict, plantilla: Plantilla) -> List[dict]:
    """Errores del registro según su plantilla. Los campos que la plantilla no
    define se aceptan (vienen, por ejemplo, de una importación)."""
    errores: List[dict] = []
    presentes: Dict[str, int] = {}
    for c in marc["fields"]:
        tag = next(iter(c))
        presentes[tag] = presentes.get(tag, 0) + 1

    for definicion in plantilla.campos:
        cantidad = presentes.get(definicion.tag, 0)
        if definicion.obligatorio and cantidad == 0:
            errores.append(_error(f"Falta el campo {definicion.tag} ({definicion.nombre})",
                                  definicion.tag))
        if not definicion.repetible and cantidad > 1:
            errores.append(_error(f"El campo {definicion.tag} ({definicion.nombre}) no se repite",
                                  definicion.tag))
        if definicion.es_de_control or cantidad == 0:
            continue
        for campo in campos(marc, definicion.tag):
            for sub in definicion.subcampos:
                n = len(subcampos(campo, sub.codigo))
                if sub.obligatorio and n == 0:
                    errores.append(_error(
                        f"Falta ${sub.codigo} ({sub.nombre}) en {definicion.tag}",
                        definicion.tag, sub.codigo))
                if not sub.repetible and n > 1:
                    errores.append(_error(
                        f"${sub.codigo} ({sub.nombre}) no se repite en {definicion.tag}",
                        definicion.tag, sub.codigo))

    if not primero(marc, "245", "a"):
        if not any(e["loc"][:2] == ["245", "a"] or e["loc"] == ["245"] for e in errores):
            errores.append(_error("Falta el título (245 $a)", "245", "a"))
    for valor in campos(marc, "008"):
        if len(valor) != LONGITUD_008:
            errores.append(_error(f"El 008 debe tener {LONGITUD_008} posiciones "
                                  f"(tiene {len(valor)})", "008"))
    return errores


def preparar(marc: dict, codigo_plantilla: Optional[str]) -> Tuple[dict, Plantilla]:
    """Normaliza y valida; lanza 422 con todos los errores juntos."""
    plantilla = marc_plantillas.obtener(codigo_plantilla)
    canonico = normalizar(marc, plantilla)
    errores = validar(canonico, plantilla)
    if errores:
        raise ErroresDeValidacion(errores)
    return canonico, plantilla


# --- Datos derivados --------------------------------------------------------------

def normalizar_isbn(texto: Optional[str]) -> Optional[str]:
    """"978-0-307-47472-8 (rústica)" → "978-0-307-47472-8"; "9780307474728(pbk.)" → "9780307474728".

    Se corta en el primer carácter que no sea dígito, X o guion (los calificadores van
    pegados en muchos registros). Si no empieza por un dígito se deja como vino.
    """
    if not texto:
        return None
    candidato = texto.strip().split(" ")[0].strip(" :;.,")
    corte = re.match(r"[0-9][0-9Xx-]*", candidato)
    if corte:
        candidato = corte.group(0).rstrip("-")
    return candidato[:20] or None


def ano_de(marc: dict) -> Optional[int]:
    candidatos = []
    for campo in campos(marc, "264"):
        if isinstance(campo, dict) and campo.get("ind2") == "1":
            candidatos += subcampos(campo, "c")
    for campo in campos(marc, "260"):
        candidatos += subcampos(campo, "c")
    for campo in campos(marc, "264"):
        candidatos += subcampos(campo, "c")
    for texto in candidatos:
        m = _ANO.search(texto)
        if m:
            return int(m.group(1))
    for f008 in campos(marc, "008"):
        if isinstance(f008, str) and len(f008) >= 11 and f008[7:11].isdigit():
            return int(f008[7:11])
    return None


def derivar(marc: dict) -> dict:
    """Columnas de `registros_bibliograficos` que salen del MARC."""
    titulo = _limpio(primero(marc, "245", "a")) or "Sin título"
    resto = _limpio(primero(marc, "245", "b"))
    if resto:
        titulo = f"{titulo}: {resto}"
    partes = [p for c in campos(marc, "245") for code in ("n", "p")
              for p in (_limpio(x) for x in subcampos(c, code)) if p]
    if partes:
        titulo = f"{titulo}. {'. '.join(partes)}"

    autor = None
    for tag in ("100", "110", "111", "700", "710"):
        autor = _limpio(primero(marc, tag, "a"))
        if autor:
            break

    materia = _limpio(primero(marc, "650", "a")) or _limpio(primero(marc, "653", "a"))
    return {
        "titulo": titulo,
        "autor": autor,
        "materia": materia[:100] if materia else None,
        "ano_publicacion": ano_de(marc),
        "isbn": normalizar_isbn(primero(marc, "020", "a")),
        # Todos los puntos de acceso repetidos, para la búsqueda y los duplicados.
        "materias": _unidos(_todos_los_a(marc, ("650", "653"), _limpio), " | "),
        "autores": _unidos(_todos_los_a(marc, ("100", "110", "111", "700", "710"), _limpio),
                           " | "),
        "isbns": _unidos(_todos_los_a(marc, ("020",), normalizar_isbn), " "),
    }


def _todos_los_a(marc: dict, tags: Tuple[str, ...], limpiar) -> List[str]:
    """El $a de cada campo con esas etiquetas (en el orden del registro), sin repetir."""
    valores: List[str] = []
    for campo in marc.get("fields", []):
        tag = next(iter(campo))
        if tag not in tags:
            continue
        for crudo in subcampos(campo[tag], "a")[:1]:
            valor = limpiar(crudo)
            if valor and valor not in valores:
                valores.append(valor)
    return valores


def _unidos(valores: List[str], separador: str) -> Optional[str]:
    return separador.join(valores) or None


# --- Construcción -----------------------------------------------------------------

def campo_008(ano: Optional[int] = None, idioma: str = "spa", pais: str = "ve ",
              creado: Optional[date] = None) -> str:
    """008 básico para libros: fecha de creación, año, país, idioma, fuente "d"."""
    creado = creado or date.today()
    if ano is not None and not 0 <= ano <= 9999:
        raise ReglaIncumplida(f"El año {ano} no cabe en el 008 (cuatro dígitos)")
    fecha1 = f"{ano:04d}" if ano else "    "
    valor = (f"{creado:%y%m%d}" + "s" + fecha1 + "    " + pais[:3].ljust(3)
             + " " * 17 + idioma[:3].ljust(3) + " " + "d")
    if len(valor) != LONGITUD_008:  # no debería pasar: los datos de entrada ya se acotaron
        raise ReglaIncumplida("No se pudo armar el campo 008 con esos datos")
    return valor


def desde_columnas(titulo: str, autor: Optional[str] = None, isbn: Optional[str] = None,
                   ano: Optional[int] = None, materia: Optional[str] = None,
                   plantilla: Optional[Plantilla] = None) -> dict:
    """Registro MARC mínimo para el alta rápida (formulario de pocos campos)."""
    plantilla = plantilla or marc_plantillas.obtener(None)
    fields: List[dict] = [{"008": campo_008(ano)}]
    if isbn:
        fields.append({"020": {"ind1": " ", "ind2": " ", "subfields": [{"a": isbn}]}})
    if autor:
        fields.append({"100": {"ind1": "1", "ind2": " ", "subfields": [{"a": autor}]}})
    fields.append({"245": {"ind1": "1" if autor else "0", "ind2": "0",
                           "subfields": [{"a": titulo}]}})
    if ano:
        fields.append({"264": {"ind1": " ", "ind2": "1", "subfields": [{"c": str(ano)}]}})
    if materia:
        fields.append({"650": {"ind1": " ", "ind2": "4", "subfields": [{"a": materia}]}})
    return {"leader": plantilla.lider, "fields": fields}


# --- Vistas -----------------------------------------------------------------------

def texto_legible(marc: dict) -> str:
    """Formato "mnemónico" de MarcEdit: =245  10$aCien años de soledad /$cG. García."""
    lineas = [f"=LDR  {marc.get('leader', '')}"]
    for c in marc.get("fields", []):
        tag, valor = next(iter(c.items()))
        if isinstance(valor, str):
            lineas.append(f"={tag}  " + valor.replace(" ", "\\"))
        else:
            ind = ((valor.get("ind1") or " ") + (valor.get("ind2") or " ")).replace(" ", "\\")
            subs = "".join(f"${k}{v}" for s in valor.get("subfields", []) for k, v in s.items())
            lineas.append(f"={tag}  {ind}{subs}")
    return "\n".join(lineas)


# --- pymarc -----------------------------------------------------------------------

def a_pymarc(marc: dict) -> pymarc.Record:
    return pymarc.parse_json_to_array(io.StringIO(json.dumps([marc])))[0]


def desde_pymarc(registro: pymarc.Record) -> dict:
    return registro.as_dict()


def iterar_campos(marc: dict) -> Iterable[Tuple[str, object]]:
    for c in marc.get("fields", []):
        yield next(iter(c.items()))
