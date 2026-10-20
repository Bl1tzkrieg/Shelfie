"""Catálogo: títulos con su disponibilidad, alta de material y ejemplares."""

import re
from typing import List, Optional

from sqlalchemy import func
from sqlalchemy.orm import Session

from app import models
from app.core.errores import Conflicto, NoEncontrado, ReglaIncumplida
from app.core import marc_plantillas
from app.services import busqueda, registro
from app.services import marc as marc_svc

def buscar_por_isbn(db: Session, isbn: Optional[str],
                    excluir_id: Optional[int] = None) -> Optional[models.RegistroBibliografico]:
    """Mismo ISBN aunque uno tenga guiones o espacios y el otro no."""
    digitos = re.sub(r"[^0-9X]", "", (isbn or "").upper())
    if not digitos:
        return None
    RB = models.RegistroBibliografico
    consulta = db.query(RB).filter(
        func.upper(func.regexp_replace(RB.isbn, "[^0-9Xx]", "", "g")) == digitos)
    if excluir_id:
        consulta = consulta.filter(RB.id != excluir_id)
    return consulta.order_by(RB.id).first()


def _obtener_registro(db: Session, biblio_id: int) -> models.RegistroBibliografico:
    biblio = db.query(models.RegistroBibliografico).filter(
        models.RegistroBibliografico.id == biblio_id).first()
    if not biblio:
        raise NoEncontrado("Título no encontrado en el catálogo")
    return biblio


def vista_de_titulo(db: Session, biblio: models.RegistroBibliografico,
                    items: Optional[list] = None) -> dict:
    """Un título con la cantidad de ejemplares.

    `items` se pasa ya cargado al listar el catálogo completo, para no hacer una
    consulta por título. Sin circulación, todos los ejemplares están en el estante.
    """
    if items is None:
        items = db.query(models.Item).filter(models.Item.biblio_id == biblio.id).all()
    return {
        "id": str(biblio.id),
        "title": biblio.titulo or "Sin título",
        "author": biblio.autor or "Autor desconocido",
        "year": biblio.ano_publicacion,
        "category": biblio.materia or "Sin clasificar",
        "type": marc_plantillas.obtener(biblio.plantilla).nombre,
        "isbn": biblio.isbn or "N/A",
        "location": biblio.cota or next(
            (i.signatura_topografica for i in items if i.signatura_topografica), None),
        "copies": len(items),
        "available": len(items),
    }


# --- Títulos y ejemplares ---------------------------------------------------------

def vistas_de_titulos(db: Session, registros: list) -> List[dict]:
    """Vista de varios títulos con una consulta de ejemplares, sin importar cuántos sean."""
    ids = [b.id for b in registros]
    items = busqueda.items_por_titulo(db, ids)
    return [vista_de_titulo(db, b, items[b.id]) for b in registros]


def listar_titulos(db: Session) -> List[dict]:
    registros = db.query(models.RegistroBibliografico).order_by(
        models.RegistroBibliografico.titulo).all()
    return vistas_de_titulos(db, registros)


def buscar_titulos(db: Session, filtros: "busqueda.Filtros", *, pagina: int, por_pagina: int,
                   orden: str) -> dict:
    """Búsqueda de la intranet: página de títulos con sus ejemplares y facetas."""
    r = busqueda.buscar(db, filtros, pagina=pagina, por_pagina=por_pagina, orden=orden)
    registros = r.pop("registros")
    return {**r, "resultados": vistas_de_titulos(db, registros)}


def obtener_titulo(db: Session, biblio_id: int) -> dict:
    return vista_de_titulo(db, _obtener_registro(db, biblio_id))


def _codigo(texto: Optional[str]) -> Optional[str]:
    return (texto or "").strip() or None


def _exigir_codigo_libre(db: Session, codigo: Optional[str],
                         propio_id: Optional[int] = None) -> None:
    if not codigo:
        return
    consulta = db.query(models.Item.id).filter(models.Item.codigo_barras == codigo)
    if propio_id:
        consulta = consulta.filter(models.Item.id != propio_id)
    if consulta.first():
        raise Conflicto(f"Ya existe un ejemplar con el código de barras {codigo}")


def dar_de_alta(db: Session, datos) -> dict:
    """Alta de un ejemplar; si el ISBN ya existe, se suma al título en vez de duplicarlo."""
    codigo = _codigo(datos.codigo_barras)
    _exigir_codigo_libre(db, codigo)

    biblio = buscar_por_isbn(db, marc_svc.normalizar_isbn(datos.isbn))
    if not biblio:
        borrador = marc_svc.desde_columnas(datos.titulo, datos.autor, datos.isbn,
                                           datos.ano_publicacion, datos.materia)
        marc, plantilla = marc_svc.preparar(borrador, marc_plantillas.POR_DEFECTO)
        biblio = models.RegistroBibliografico()
        aplicar_marc(biblio, marc, plantilla)
        db.add(biblio)
        db.flush()

    item = _nuevo_item(db, biblio, codigo=codigo, signatura=datos.signatura_topografica)
    db.flush()
    registro.anotar(db, "catalogo", "alta",
                    f"Alta rápida: {_nombre_ejemplar(item)} de «{biblio.titulo}»",
                    biblio=biblio, item=item)
    db.commit()
    db.refresh(biblio)
    return vista_de_titulo(db, biblio)


def _nombre_ejemplar(item: models.Item) -> str:
    return f"ejemplar {item.codigo_barras}" if item.codigo_barras else "ejemplar sin código"


def _nuevo_item(db: Session, biblio, *, codigo: Optional[str], signatura: Optional[str],
                copia: Optional[str] = None, nota: Optional[str] = None) -> models.Item:
    item = models.Item(
        biblio_id=biblio.id,
        codigo_barras=codigo,
        signatura_topografica=_codigo(signatura),
        numero_copia=_codigo(copia),
        nota=_codigo(nota),
    )
    db.add(item)
    return item


def agregar_ejemplar(db: Session, biblio_id: int, datos) -> dict:
    """Otro ejemplar de un título que ya existe (p. ej. una tesis, que no tiene ISBN)."""
    biblio = _obtener_registro(db, biblio_id)
    codigo = _codigo(datos.codigo_barras)
    _exigir_codigo_libre(db, codigo)
    item = _nuevo_item(db, biblio, codigo=codigo, signatura=datos.signatura_topografica,
                       copia=datos.numero_copia, nota=datos.nota)
    db.flush()
    registro.anotar(db, "catalogo", "alta",
                    f"Nuevo {_nombre_ejemplar(item)} de «{biblio.titulo}»",
                    biblio=biblio, item=item)
    db.commit()
    return vista_de_titulo(db, biblio)


# --- Registro MARC ----------------------------------------------------------------

def aplicar_marc(biblio: models.RegistroBibliografico, marc: dict, plantilla) -> None:
    """Guarda el MARC y actualiza las columnas que se derivan de él."""
    biblio.marc_json = marc
    biblio.plantilla = plantilla.codigo
    for columna, valor in marc_svc.derivar(marc).items():
        setattr(biblio, columna, valor)


def vista_marc(biblio: models.RegistroBibliografico) -> dict:
    return {
        "id": str(biblio.id),
        "plantilla": biblio.plantilla,
        "marc": biblio.marc_json,
        "texto": marc_svc.texto_legible(biblio.marc_json),
        "titulo": biblio.titulo,
        "autor": biblio.autor,
        "materia": biblio.materia,
        "ano_publicacion": biblio.ano_publicacion,
        "isbn": biblio.isbn,
    }


def _avisar_isbn_duplicado(db: Session, isbn: Optional[str], propio_id: Optional[int]) -> None:
    if not isbn:
        return
    otro = buscar_por_isbn(db, isbn, excluir_id=propio_id)
    if otro:
        raise ReglaIncumplida(
            f"El ISBN {isbn} ya está en «{otro.titulo}» (registro {otro.id}). "
            "Agrega el ejemplar a ese registro o guarda igualmente si es otra edición.")


def obtener_marc(db: Session, biblio_id: int) -> dict:
    return vista_marc(_obtener_registro(db, biblio_id))


_CAMPOS_DERIVADOS = ("titulo", "autor", "isbn", "ano_publicacion", "materia", "plantilla")


def guardar_marc(db: Session, biblio_id: int, datos) -> dict:
    biblio = _obtener_registro(db, biblio_id)
    marc, plantilla = marc_svc.preparar(datos.marc, datos.plantilla)
    if not datos.permitir_duplicado:
        _avisar_isbn_duplicado(db, marc_svc.derivar(marc)["isbn"], biblio.id)
    antes = {c: getattr(biblio, c) for c in _CAMPOS_DERIVADOS}
    marc_antes = biblio.marc_json
    aplicar_marc(biblio, marc, plantilla)
    cambios = registro.diferencias(antes, {c: getattr(biblio, c) for c in _CAMPOS_DERIVADOS})
    if marc_antes != biblio.marc_json:
        # Como el CataloguingLog de Koha: queda el MARC anterior para ver qué cambió.
        registro.anotar(db, "catalogo", "edicion", f"Editó el registro MARC de «{biblio.titulo}»",
                        biblio=biblio, datos={"cambios": cambios, "marc_anterior": marc_antes})
    db.commit()
    db.refresh(biblio)
    return vista_marc(biblio)


def crear_registro(db: Session, datos) -> dict:
    """Catalogación completa: un registro MARC sin ejemplares (se agregan después)."""
    marc, plantilla = marc_svc.preparar(datos.marc, datos.plantilla)
    if not datos.permitir_duplicado:
        _avisar_isbn_duplicado(db, marc_svc.derivar(marc)["isbn"], None)
    biblio = models.RegistroBibliografico()
    aplicar_marc(biblio, marc, plantilla)
    db.add(biblio)
    db.flush()
    registro.anotar(db, "catalogo", "alta", f"Catalogó «{biblio.titulo}» ({biblio.plantilla})",
                    biblio=biblio)
    db.commit()
    db.refresh(biblio)
    return vista_marc(biblio)


def eliminar_registro(db: Session, biblio_id: int) -> None:
    """Solo se borra un registro sin ejemplares, como en Koha."""
    biblio = _obtener_registro(db, biblio_id)
    if db.query(models.Item).filter(models.Item.biblio_id == biblio.id).count():
        raise ReglaIncumplida("El registro tiene ejemplares: elimínalos o muévelos primero")
    # Sin `biblio=`: el registro se borra; quedan su número y su MARC en la anotación.
    registro.anotar(db, "catalogo", "eliminacion", f"Eliminó el registro «{biblio.titulo}»",
                    objeto=("registro", biblio.id), datos={"marc": biblio.marc_json})
    db.delete(biblio)
    db.commit()


def _obtener_ejemplar(db: Session, biblio_id: int, item_id: int) -> models.Item:
    item = db.query(models.Item).filter(models.Item.id == item_id,
                                        models.Item.biblio_id == biblio_id).with_for_update().first()
    if not item:
        raise NoEncontrado("Ejemplar no encontrado en este registro")
    return item


_CAMPOS_EJEMPLAR = ("codigo_barras", "signatura_topografica", "numero_copia", "nota")


def editar_ejemplar(db: Session, biblio_id: int, item_id: int, datos: dict) -> List[dict]:
    """Corrige un ejemplar: código, signatura, número de copia o nota."""
    item = _obtener_ejemplar(db, biblio_id, item_id)
    antes = {c: getattr(item, c) for c in _CAMPOS_EJEMPLAR}
    if "codigo_barras" in datos:
        codigo = _codigo(datos["codigo_barras"])
        _exigir_codigo_libre(db, codigo, propio_id=item.id)
        item.codigo_barras = codigo
    for campo in ("signatura_topografica", "numero_copia", "nota"):
        if campo in datos:
            setattr(item, campo, _codigo(datos[campo]))
    db.flush()
    cambios = registro.diferencias(antes, {c: getattr(item, c) for c in _CAMPOS_EJEMPLAR})
    if cambios:
        registro.anotar(db, "catalogo", "edicion",
                        f"Editó el {_nombre_ejemplar(item)} ({', '.join(cambios)})",
                        biblio=item.biblio_id, item=item, datos={"cambios": cambios})
    db.commit()
    return listar_ejemplares(db, biblio_id)


def eliminar_ejemplar(db: Session, biblio_id: int, item_id: int) -> None:
    """Borra un ejemplar cargado por error."""
    item = _obtener_ejemplar(db, biblio_id, item_id)
    registro.anotar(db, "catalogo", "eliminacion",
                    f"Eliminó el {_nombre_ejemplar(item)} (cargado por error)",
                    biblio=item.biblio_id, objeto=("ejemplar", item.id),
                    datos={"codigo_barras": item.codigo_barras,
                           "signatura": item.signatura_topografica})
    db.delete(item)
    db.commit()


def listar_ejemplares(db: Session, biblio_id: int) -> List[dict]:
    _obtener_registro(db, biblio_id)
    items = db.query(models.Item).filter(models.Item.biblio_id == biblio_id).order_by(
        models.Item.id).all()
    return [{
        "id": str(item.id),
        "barcode": item.codigo_barras,
        "location": item.signatura_topografica,
        "copy": item.numero_copia,
        "note": item.nota,
    } for item in items]
