"""Libros: alta con sus ejemplares, edición con la ficha simple, lista por cota y baja.

La ficha (`schemas.FichaLibro`) se traduce a MARC con `services/ficha.py`; el MARC sigue
siendo la fuente y las columnas se derivan de él con `catalogo.aplicar_marc`. Al editar se
parte siempre del MARC guardado, así lo importado que el formulario no muestra se conserva.
"""

import re
from typing import List, Optional

from sqlalchemy import and_, func, literal, or_
from sqlalchemy.orm import Session

from app import models
from app.core import marc_plantillas
from app.core.errores import Conflicto, NoEncontrado
from app.core.signaturas import clave_signatura_sql, escapar_like, normalizar_cota
from app.schemas import FichaLibro
from app.services import ficha as ficha_svc
from app.services import marc as marc_svc
from app.services import registro
from app.services.catalogo import (aplicar_marc, mover_ejemplares_de_cota, obtener_registro,
                                   tiene_isbn)

RB = models.RegistroBibliografico
Item = models.Item

# Columnas derivadas cuyo cambio se anota al editar.
_CAMPOS_DERIVADOS = ("titulo", "autor", "isbn", "ano_publicacion", "materia", "editorial", "cota")
# Campos de un ejemplar tal como los ve la API → columna del modelo.
_CAMPOS_EJEMPLAR = {"cota": "signatura_topografica", "codigo_barras": "codigo_barras",
                    "numero_copia": "numero_copia", "nota": "nota"}
_COPIA = re.compile(r"^c\.\s*(\d+)$", re.IGNORECASE)


# --- Apoyo ---------------------------------------------------------------------------

def _texto(valor: Optional[str]) -> Optional[str]:
    return (valor or "").strip() or None


def _ejemplares(db: Session, biblio_id: int) -> List[models.Item]:
    return db.query(Item).filter(Item.biblio_id == biblio_id).all()


def _exigir_codigo_libre(db: Session, codigo: Optional[str],
                         propio_id: Optional[int] = None) -> None:
    if not codigo:
        return
    consulta = db.query(Item.id).filter(Item.codigo_barras == codigo)
    if propio_id:
        consulta = consulta.filter(Item.id != propio_id)
    if consulta.first():
        raise Conflicto(f"Ya existe un ejemplar con el código de barras {codigo}")


def _nombre_ejemplar(item: models.Item) -> str:
    return f"ejemplar {item.codigo_barras}" if item.codigo_barras else "ejemplar sin código"


def _orden_de_copia(item: models.Item) -> tuple:
    """Orden natural: «c.2» antes de «c.10»; sin número de copia, al final; luego por id."""
    if not item.numero_copia:
        return (1, [], item.id)
    partes = re.split(r"(\d+)", item.numero_copia.lower())
    return (0, [int(p) if i % 2 else p for i, p in enumerate(partes)], item.id)


def _siguiente_copia(items: List[models.Item]) -> str:
    numeros = [int(m.group(1)) for m in (_COPIA.match(i.numero_copia or "") for i in items) if m]
    return f"c.{max(numeros, default=0) + 1}"


def _plural(n: int) -> str:
    return "1 ejemplar" if n == 1 else f"{n} ejemplares"


def _vista_ejemplar(item: models.Item) -> dict:
    return {"id": item.id, "cota": item.signatura_topografica,
            "codigo_barras": item.codigo_barras, "numero_copia": item.numero_copia,
            "nota": item.nota}


def _ficha(biblio: models.RegistroBibliografico) -> dict:
    """La ficha del formulario. Sin 092 (importado de Koha, con la cota del 952, el 082 o el
    050) muestra la cota guardada del registro. Un registro sin cota ni 245 $a trae la ficha
    sin validar (cota vacía): se muestra igual para poder completarla."""
    datos = ficha_svc.desde_marc(biblio.marc_json).model_dump()
    datos["cota"] = datos["cota"] or biblio.cota or ""
    return datos


def _vista(db: Session, biblio: models.RegistroBibliografico) -> dict:
    items = sorted(_ejemplares(db, biblio.id), key=_orden_de_copia)
    return {
        "id": biblio.id,
        "ficha": _ficha(biblio),
        "ejemplares": [_vista_ejemplar(i) for i in items],
        "creado_en": biblio.creado_en,
        "actualizado_en": biblio.actualizado_en,
    }


def ficha_publica(db: Session, biblio_id: int) -> dict:
    """Lo que ve cualquiera: la ficha y, por ejemplar, cota, copia y nota (sin códigos de barras)."""
    biblio = obtener_registro(db, biblio_id)
    items = sorted(_ejemplares(db, biblio.id), key=_orden_de_copia)
    return {
        "ficha": _ficha(biblio),
        "ejemplares": [{"cota": i.signatura_topografica, "numero_copia": i.numero_copia,
                        "nota": i.nota} for i in items],
    }


def sin_acentos(expresion):
    return func.lower(func.unaccent(expresion))


# --- Duplicados ----------------------------------------------------------------------

def posibles_duplicados(db: Session, ficha: FichaLibro,
                        propio_id: Optional[int] = None) -> List[dict]:
    """Registros que pueden ser el mismo libro: un ISBN en común (solo sus dígitos), o el mismo
    título y autor sin mayúsculas ni acentos. Título y autor se comparan como se derivan del
    MARC (título con subtítulo), igual que las columnas guardadas."""
    derivado = marc_svc.derivar(ficha_svc.a_marc(ficha))
    mismo_libro = and_(
        sin_acentos(RB.titulo) == sin_acentos(literal(derivado["titulo"])),
        sin_acentos(func.coalesce(RB.autor, "")) == sin_acentos(literal(derivado["autor"] or "")),
    )
    # Cualquiera de sus ISBN contra cualquiera de los 020 de cada registro.
    condiciones = [mismo_libro, tiene_isbn(ficha.isbn)]
    consulta = db.query(RB.id, RB.titulo, RB.autor, RB.cota).filter(or_(*condiciones))
    if propio_id is not None:
        consulta = consulta.filter(RB.id != propio_id)
    return [{"id": f.id, "titulo": f.titulo, "autor": f.autor, "cota": f.cota}
            for f in consulta.order_by(RB.id).limit(10)]


# --- Libros --------------------------------------------------------------------------

def crear(db: Session, ficha: FichaLibro, *, ejemplares: int = 1,
          nota_ejemplares: Optional[str] = None, forzar: bool = False) -> dict:
    """Alta de un libro con `ejemplares` copias (c.1, c.2…) que llevan la cota del libro."""
    if not forzar:
        coincidencias = posibles_duplicados(db, ficha)
        if coincidencias:
            raise Conflicto(
                "Puede que este libro ya esté en el catálogo: revisa las coincidencias o "
                "guárdalo igualmente", detalle={"codigo": "POSIBLE_DUPLICADO",
                                                "coincidencias": coincidencias})
    marc, plantilla = marc_svc.preparar(ficha_svc.a_marc(ficha), marc_plantillas.POR_DEFECTO)
    biblio = RB()
    aplicar_marc(biblio, marc, plantilla)
    db.add(biblio)
    db.flush()
    for n in range(1, ejemplares + 1):
        db.add(Item(biblio_id=biblio.id, signatura_topografica=biblio.cota,
                    numero_copia=f"c.{n}", nota=_texto(nota_ejemplares)))
    db.flush()
    registro.anotar(db, "catalogo", "alta",
                    f"Alta de «{biblio.titulo}» ({biblio.cota}) con {_plural(ejemplares)}",
                    biblio=biblio)
    db.commit()
    db.refresh(biblio)
    return _vista(db, biblio)


def actualizar(db: Session, biblio_id: int, ficha: FichaLibro) -> dict:
    """Guarda la ficha sobre el MARC actual. Los ejemplares que tenían la cota anterior del
    libro (la heredaban) pasan a la nueva; los que tienen una cota propia no cambian."""
    biblio = obtener_registro(db, biblio_id, bloquear=True)
    cota_anterior = biblio.cota
    antes = {c: getattr(biblio, c) for c in _CAMPOS_DERIVADOS}
    marc_antes = biblio.marc_json
    nuevo = ficha_svc.a_marc(ficha, marc_antes, cota_actual=cota_anterior)
    cota = normalizar_cota(ficha.cota)
    if (ficha_svc.cota_de_clasificacion(nuevo) or cota_anterior) != cota:
        # Sin 092, la cota saldría del 082 o del 050 y no sería la del formulario: se escribe.
        nuevo = ficha_svc.con_cota(nuevo, cota)
    marc, plantilla = marc_svc.preparar(nuevo, biblio.plantilla)
    aplicar_marc(biblio, marc, plantilla)
    heredan = mover_ejemplares_de_cota(db, biblio, cota_anterior)

    cambios = registro.diferencias(antes, {c: getattr(biblio, c) for c in _CAMPOS_DERIVADOS})
    if marc_antes != biblio.marc_json:
        datos = {"cambios": cambios, "marc_anterior": marc_antes}
        if heredan:
            datos["ejemplares_con_la_cota_nueva"] = [i.id for i in heredan]
        registro.anotar(db, "catalogo", "edicion", f"Editó la ficha de «{biblio.titulo}»",
                        biblio=biblio, datos=datos)
    db.commit()
    db.refresh(biblio)
    return _vista(db, biblio)


def obtener(db: Session, biblio_id: int) -> dict:
    return _vista(db, obtener_registro(db, biblio_id))


def listar(db: Session, *, q: str = "", pagina: int = 1, por_pagina: int = 50) -> dict:
    """Libros en el orden del estante (por cota); los que no tienen cota, al final.
    `q` filtra por título, autor o cota (sin mayúsculas ni acentos)."""
    cuenta = db.query(Item.biblio_id, func.count(Item.id).label("n")).group_by(
        Item.biblio_id).subquery()
    consulta = db.query(RB.id, RB.cota, RB.titulo, RB.autor, RB.ano_publicacion, RB.editorial,
                        func.coalesce(cuenta.c.n, 0).label("ejemplares")).outerjoin(
        cuenta, cuenta.c.biblio_id == RB.id)
    texto = " ".join((q or "").split())
    if texto:
        patron = func.unaccent(f"%{escapar_like(texto)}%")
        consulta = consulta.filter(or_(*(
            func.unaccent(columna).ilike(patron, escape="\\")
            for columna in (RB.titulo, RB.autor, RB.cota))))
    total = consulta.count()
    filas = consulta.order_by(RB.cota.is_(None), clave_signatura_sql(RB.cota), RB.titulo,
                              RB.id).offset((pagina - 1) * por_pagina).limit(por_pagina).all()
    return {
        "total": total,
        "pagina": pagina,
        "por_pagina": por_pagina,
        "paginas": max(1, -(-total // por_pagina)),
        "resultados": [{"id": f.id, "cota": f.cota, "titulo": f.titulo, "autor": f.autor,
                        "ano": f.ano_publicacion, "editorial": f.editorial,
                        "ejemplares": f.ejemplares} for f in filas],
    }


def eliminar(db: Session, biblio_id: int) -> None:
    """Baja del libro con todos sus ejemplares. En la anotación quedan el MARC y los
    ejemplares, para poder rehacerlo."""
    biblio = obtener_registro(db, biblio_id, bloquear=True)
    items = sorted(_ejemplares(db, biblio.id), key=_orden_de_copia)
    # Sin `biblio=`: el registro se borra; quedan su número y su MARC en la anotación.
    registro.anotar(db, "catalogo", "baja",
                    f"Dio de baja «{biblio.titulo}» ({biblio.cota or 'sin cota'}) "
                    f"con {_plural(len(items))}",
                    objeto=("registro", biblio.id),
                    datos={"marc": biblio.marc_json,
                           "ejemplares": [_vista_ejemplar(i) for i in items]})
    for item in items:
        db.delete(item)
    db.delete(biblio)
    db.commit()


# --- Ejemplares ----------------------------------------------------------------------

def agregar_ejemplar(db: Session, biblio_id: int, *, cota: Optional[str] = None,
                     codigo_barras: Optional[str] = None, numero_copia: Optional[str] = None,
                     nota: Optional[str] = None) -> dict:
    """Otro ejemplar. Sin cota lleva la del libro; sin número de copia, el siguiente c.N."""
    biblio = obtener_registro(db, biblio_id, bloquear=True)
    codigo = _texto(codigo_barras)
    _exigir_codigo_libre(db, codigo)
    item = Item(biblio_id=biblio.id, codigo_barras=codigo,
                signatura_topografica=normalizar_cota(cota) or biblio.cota,
                numero_copia=_texto(numero_copia) or _siguiente_copia(_ejemplares(db, biblio.id)),
                nota=_texto(nota))
    db.add(item)
    db.flush()
    registro.anotar(db, "catalogo", "ejemplar",
                    f"Nuevo {_nombre_ejemplar(item)} ({item.numero_copia}) de «{biblio.titulo}»",
                    biblio=biblio, item=item)
    db.commit()
    return _vista(db, biblio)


def _obtener_ejemplar(db: Session, biblio_id: int, item_id: int) -> models.Item:
    item = db.query(Item).filter(Item.id == item_id,
                                 Item.biblio_id == biblio_id).with_for_update().first()
    if not item:
        raise NoEncontrado("Ejemplar no encontrado en este libro")
    return item


def editar_ejemplar(db: Session, biblio_id: int, item_id: int, cambios: dict) -> dict:
    """Corrige un ejemplar; solo cambian las claves presentes (vacío = se borra el dato).
    Claves: cota, codigo_barras, numero_copia, nota."""
    item = _obtener_ejemplar(db, biblio_id, item_id)
    antes = {campo: getattr(item, columna) for campo, columna in _CAMPOS_EJEMPLAR.items()}
    if "codigo_barras" in cambios:
        codigo = _texto(cambios["codigo_barras"])
        _exigir_codigo_libre(db, codigo, propio_id=item.id)
        item.codigo_barras = codigo
    if "cota" in cambios:
        item.signatura_topografica = normalizar_cota(cambios["cota"])
    for campo in ("numero_copia", "nota"):
        if campo in cambios:
            setattr(item, campo, _texto(cambios[campo]))
    db.flush()
    despues = {campo: getattr(item, columna) for campo, columna in _CAMPOS_EJEMPLAR.items()}
    diferencias = registro.diferencias(antes, despues)
    if diferencias:
        registro.anotar(db, "catalogo", "ejemplar",
                        f"Editó el {_nombre_ejemplar(item)} ({', '.join(diferencias)})",
                        biblio=item.biblio_id, item=item, datos={"cambios": diferencias})
    db.commit()
    return obtener(db, biblio_id)


def eliminar_ejemplar(db: Session, biblio_id: int, item_id: int) -> None:
    item = _obtener_ejemplar(db, biblio_id, item_id)
    biblio = obtener_registro(db, biblio_id)
    registro.anotar(db, "catalogo", "ejemplar",
                    f"Eliminó el {_nombre_ejemplar(item)} de «{biblio.titulo}»",
                    biblio=biblio, objeto=("ejemplar", item.id),
                    datos=_vista_ejemplar(item))
    db.delete(item)
    db.commit()
