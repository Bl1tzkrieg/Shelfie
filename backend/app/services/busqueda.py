"""Búsqueda pública en el catálogo: por palabras, por campo, por cota y por ISBN.

El texto se busca en `registros_bibliograficos.busqueda` (tsvector con índice GIN,
migración 0001_lite) con la configuración `shelfie_es`: español, sin acentos y reducido a la
raíz. La última palabra se busca como prefijo, para que funcione mientras se escribe
("bioqui" ya encuentra "Bioquímica de Harper").

En `todo` se suman tres vías: el texto, la cota por prefijo (en el registro o en alguno de sus
ejemplares) y el ISBN con o sin guiones. En los demás campos solo vale esa vía. Autor, materia e
ISBN miran todos los puntos de acceso del registro (columnas `autores`, `materias` e `isbns`:
todos los 1XX/700/710, 650 y 020), no solo el primero.

Una consulta sin términos útiles ("de la", "¿?", "-") no llega a la base: da cero resultados.
"""

import re

from sqlalchemy import and_, exists, func, or_, select
from sqlalchemy.orm import Session

from app import models
from app.core.errores import ReglaIncumplida
from app.core.signaturas import clave_signatura_sql, escapar_like, normalizar_cota
from app.services import ficha as ficha_svc
from app.services.catalogo import isbn_parcial, tiene_isbn

RB = models.RegistroBibliografico
Item = models.Item
CONFIG = "shelfie_es"
CAMPOS = ("todo", "titulo", "autor", "materia", "cota", "isbn", "editorial")
_COLUMNAS_DE_TEXTO = {"titulo": RB.titulo, "autor": RB.autores, "materia": RB.materias,
                      "editorial": RB.editorial}

_PALABRA = re.compile(r"\w+", re.UNICODE)
_ISBN = re.compile(r"^[0-9][0-9\- ]{8,16}[0-9Xx]$")


def _digitos_isbn(texto: str) -> str:
    return re.sub(r"[^0-9Xx]", "", texto or "").upper()


def _consulta_de_texto(db: Session, texto: str):
    """tsquery con todas las palabras (AND) y la última como prefijo.

    None si no hay nada útil: sin palabras o solo palabras vacías ("de la"), cuya tsquery
    queda vacía, no encuentra nada y hace que PostgreSQL avise con un NOTICE."""
    palabras = _PALABRA.findall(texto or "")
    if not palabras:
        return None
    utiles = db.execute(select(func.length(func.to_tsvector(CONFIG, " ".join(palabras))))
                        ).scalar_one()
    if not utiles:
        return None
    terminos = palabras[:-1] + [f"{palabras[-1]}:*"]
    return func.to_tsquery(CONFIG, " & ".join(terminos))


def _condicion_cota(texto: str):
    """Cota por prefijo, normalizada como se guarda («616.39  h» → «616.39 H»)."""
    cota = normalizar_cota(texto)
    if not cota or not _PALABRA.search(cota):
        return None
    patron = escapar_like(cota) + "%"
    return or_(RB.cota.ilike(patron, escape="\\"),
               exists().where(and_(Item.biblio_id == RB.id,
                                   Item.signatura_topografica.ilike(patron, escape="\\"))))


def _condicion_isbn(texto: str, *, exacto: bool):
    digitos = _digitos_isbn(texto)
    if not digitos:
        return None
    if exacto:
        return tiene_isbn([digitos])
    return isbn_parcial(digitos)


def _condicion(db: Session, texto: str, campo: str):
    """(condición, tsquery usada para ordenar y vector sobre el que se aplica) o None."""
    if campo == "cota":
        c = _condicion_cota(texto)
        return (c, None, None) if c is not None else None
    if campo == "isbn":
        c = _condicion_isbn(texto, exacto=False)
        return (c, None, None) if c is not None else None

    tsq = _consulta_de_texto(db, texto)
    if campo != "todo":
        if tsq is None:
            return None
        vector = func.to_tsvector(CONFIG, func.coalesce(_COLUMNAS_DE_TEXTO[campo], ""))
        return vector.op("@@")(tsq), tsq, vector

    opciones = []
    if tsq is not None:
        opciones.append(RB.busqueda.op("@@")(tsq))
    cota = _condicion_cota(texto)
    if cota is not None:
        opciones.append(cota)
    if _ISBN.match(texto):
        opciones.append(_condicion_isbn(texto, exacto=True))
    return (or_(*opciones), tsq, RB.busqueda) if opciones else None


def _ejemplares_por_registro():
    return select(Item.biblio_id, func.count(Item.id).label("n")).group_by(
        Item.biblio_id).subquery()


def buscar(db: Session, q: str, *, campo: str = "todo", pagina: int = 1,
           por_pagina: int = 20) -> dict:
    """Una página de resultados, en orden de relevancia y luego de estante."""
    if campo not in CAMPOS:
        raise ReglaIncumplida(f"Campo de búsqueda no válido: usa {', '.join(CAMPOS)}")
    pagina = max(1, pagina)
    vacio = {"total": 0, "pagina": pagina, "resultados": []}
    texto = " ".join((q or "").split())
    encontrada = _condicion(db, texto, campo) if texto else None
    if encontrada is None:
        return vacio
    condicion, tsq, vector = encontrada

    total = db.query(func.count(RB.id)).filter(condicion).scalar()
    cuenta = _ejemplares_por_registro()
    orden = [RB.cota.is_(None), clave_signatura_sql(RB.cota), RB.titulo, RB.id]
    if tsq is not None:
        orden.insert(0, func.ts_rank_cd(vector, tsq).desc())
    filas = (db.query(RB, func.coalesce(cuenta.c.n, 0))
             .outerjoin(cuenta, cuenta.c.biblio_id == RB.id)
             .filter(condicion).order_by(*orden)
             .offset((pagina - 1) * por_pagina).limit(por_pagina).all())

    resultados = []
    for biblio, ejemplares in filas:
        ficha = ficha_svc.desde_marc(biblio.marc_json)
        resultados.append({
            "id": biblio.id, "cota": biblio.cota, "titulo": ficha.titulo or biblio.titulo,
            "subtitulo": ficha.subtitulo, "autor": biblio.autor, "edicion": ficha.edicion,
            "editorial": biblio.editorial, "ano": biblio.ano_publicacion,
            "ejemplares": ejemplares,
        })
    return {"total": total, "pagina": pagina, "resultados": resultados}
