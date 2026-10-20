"""Búsqueda en el catálogo: texto completo con facetas.

El texto se busca en `registros_bibliograficos.busqueda` (tsvector con índice
GIN, migración 0001_lite) con la configuración `shelfie_es`: español, sin acentos y
reducido a la raíz. La última palabra se busca como prefijo, para que funcione
mientras se escribe ("cien añ" ya encuentra "Cien años de soledad").

Además del texto, un ISBN (con o sin guiones) o un código de barras exacto
encuentran su título aunque no estén en el índice.

Las facetas se calculan sobre el conjunto ya filtrado: cada número dice cuántos
títulos quedarían al elegir ese valor.
"""

import re
from dataclasses import dataclass, field
from typing import Dict, List, Optional

from sqlalchemy import and_, exists, false, func, or_, select
from sqlalchemy.orm import Session

from app import models

RB = models.RegistroBibliografico
Item = models.Item
CONFIG = "shelfie_es"
MAX_POR_FACETA = 12
ORDENES = ("relevancia", "titulo", "ano_desc", "ano_asc")

_PALABRA = re.compile(r"\w+", re.UNICODE)
_ISBN = re.compile(r"^[0-9][0-9\- ]{8,16}[0-9Xx]$")


@dataclass
class Filtros:
    """Lo que el usuario eligió. Todo es opcional."""
    q: str = ""
    # Búsqueda por campo (búsqueda avanzada), con las mismas reglas que `q`.
    campos: Dict[str, str] = field(default_factory=dict)
    # Facetas: valores exactos tal como los devuelve la propia búsqueda.
    materia: Optional[str] = None
    autor: Optional[str] = None
    disponible: Optional[bool] = None   # True: con algún ejemplar; False: sin ninguno
    ano_desde: Optional[int] = None
    ano_hasta: Optional[int] = None


def _consulta_de_texto(texto: str):
    """tsquery con todas las palabras (AND) y la última como prefijo, o None si no hay."""
    palabras = _PALABRA.findall(texto or "")
    if not palabras:
        return None
    terminos = palabras[:-1] + [f"{palabras[-1]}:*"]
    return func.to_tsquery(CONFIG, " & ".join(terminos))


def _condicion_texto(texto: str):
    """Coincidencia por texto, ISBN o código de barras."""
    tsq = _consulta_de_texto(texto)
    if tsq is None:  # solo signos: no hay nada que buscar
        return None
    # Solo palabras vacías ("de", "la"): la consulta queda vacía y no filtra nada.
    opciones = [or_(func.numnode(tsq) == 0, RB.busqueda.op("@@")(tsq))]

    limpio = texto.strip()
    if _ISBN.match(limpio):
        digitos = re.sub(r"[^0-9Xx]", "", limpio).upper()
        opciones.append(func.upper(func.replace(func.replace(RB.isbn, "-", ""), " ", "")) == digitos)
    if limpio and " " not in limpio:
        opciones.append(exists().where(and_(Item.biblio_id == RB.id,
                                            func.upper(Item.codigo_barras) == limpio.upper())))
    return or_(*opciones)


def _condicion_campo(columna, texto: str):
    tsq = _consulta_de_texto(texto)
    if tsq is None:
        return None
    vector = func.to_tsvector(CONFIG, func.coalesce(columna, ""))
    return or_(func.numnode(tsq) == 0, vector.op("@@")(tsq))


def _hay_disponible():
    """Sin circulación, un título está disponible si tiene algún ejemplar."""
    return exists().where(Item.biblio_id == RB.id)


def _condiciones(filtros: Filtros) -> list:
    condiciones = []
    if filtros.q and filtros.q.strip():
        c = _condicion_texto(filtros.q)
        if c is not None:
            condiciones.append(c)

    columnas = {"titulo": RB.titulo, "autor": RB.autor, "materia": RB.materia}
    for nombre, texto in filtros.campos.items():
        if not texto or not texto.strip():
            continue
        if nombre == "isbn":
            digitos = re.sub(r"[^0-9Xx]", "", texto).upper()
            # Sin dígitos no hay ISBN que buscar: LIKE '%%' traería todo el catálogo.
            condiciones.append(func.upper(func.replace(func.replace(RB.isbn, "-", ""), " ", ""))
                               .like(f"%{digitos}%") if digitos else false())
        elif nombre in columnas:
            c = _condicion_campo(columnas[nombre], texto)
            if c is not None:
                condiciones.append(c)

    if filtros.materia:
        condiciones.append(RB.materia == filtros.materia)
    if filtros.autor:
        condiciones.append(RB.autor == filtros.autor)
    if filtros.disponible is True:
        condiciones.append(_hay_disponible())
    elif filtros.disponible is False:
        condiciones.append(~_hay_disponible())
    if filtros.ano_desde is not None:
        condiciones.append(RB.ano_publicacion >= filtros.ano_desde)
    if filtros.ano_hasta is not None:
        condiciones.append(RB.ano_publicacion <= filtros.ano_hasta)
    return condiciones


def _orden(filtros: Filtros, orden: str):
    titulo = func.lower(RB.titulo)
    if orden == "titulo":
        return [titulo, RB.id]
    if orden == "ano_desc":
        return [RB.ano_publicacion.desc().nulls_last(), titulo, RB.id]
    if orden == "ano_asc":
        return [RB.ano_publicacion.asc().nulls_last(), titulo, RB.id]
    tsq = _consulta_de_texto(filtros.q)
    if tsq is None:
        return [titulo, RB.id]
    return [func.ts_rank_cd(RB.busqueda, tsq).desc(), titulo, RB.id]


def _facetas(db: Session, ids) -> dict:
    """Conteos sobre los títulos que cumplen la búsqueda (`ids` es una subconsulta)."""
    def top(columna):
        filas = db.execute(
            select(columna, func.count()).where(RB.id.in_(ids), columna.isnot(None),
                                                columna != "")
            .group_by(columna).order_by(func.count().desc(), columna).limit(MAX_POR_FACETA)
        ).all()
        return [{"valor": v, "cantidad": n} for v, n in filas]

    decada = (func.floor(RB.ano_publicacion / 10) * 10).label("decada")
    decadas = db.execute(
        select(decada, func.count()).where(RB.id.in_(ids), RB.ano_publicacion.isnot(None))
        .group_by(decada).order_by(decada.desc())
    ).all()

    con, sin = db.execute(
        select(func.count().filter(_hay_disponible()), func.count().filter(~_hay_disponible()))
        .select_from(RB).where(RB.id.in_(ids))
    ).one()

    return {
        "disponibilidad": [{"valor": "si", "etiqueta": "Con ejemplares", "cantidad": con},
                           {"valor": "no", "etiqueta": "Sin ejemplares", "cantidad": sin}],
        "materias": top(RB.materia),
        "autores": top(RB.autor),
        "decadas": [{"valor": int(d), "etiqueta": f"{int(d)}–{int(d) + 9}", "cantidad": n}
                    for d, n in decadas],
    }


def buscar(db: Session, filtros: Filtros, *, pagina: int = 1, por_pagina: int = 24,
           orden: str = "relevancia", con_facetas: bool = True) -> dict:
    """Ids de la página pedida, en orden, más el total y las facetas.

    Quien llama arma la vista de cada título a partir de `registros`, que ya viene en
    el orden correcto.
    """
    orden = orden if orden in ORDENES else "relevancia"
    pagina = max(1, pagina)
    condiciones = _condiciones(filtros)

    ids = select(RB.id).where(*condiciones)
    total = db.execute(select(func.count()).select_from(ids.subquery())).scalar_one()
    registros = db.query(RB).filter(*condiciones).order_by(*_orden(filtros, orden)).offset(
        (pagina - 1) * por_pagina).limit(por_pagina).all()

    return {
        "total": total,
        "pagina": pagina,
        "por_pagina": por_pagina,
        "paginas": max(1, -(-total // por_pagina)),
        "orden": orden,
        "registros": registros,
        "facetas": _facetas(db, ids) if con_facetas else None,
    }


def todos_los_que_cumplen(db: Session, filtros: Filtros, orden: str = "titulo"):
    """Consulta (sin paginar) de los registros que cumplen la búsqueda, para exportar."""
    return db.query(RB).filter(*_condiciones(filtros)).order_by(*_orden(filtros, orden))


def items_por_titulo(db: Session, biblio_ids: List[int]) -> Dict[int, list]:
    """Ejemplares de varios títulos en una sola consulta."""
    resultado: Dict[int, list] = {i: [] for i in biblio_ids}
    if biblio_ids:
        for item in db.query(Item).filter(Item.biblio_id.in_(biblio_ids)).order_by(Item.id):
            resultado[item.biblio_id].append(item)
    return resultado
