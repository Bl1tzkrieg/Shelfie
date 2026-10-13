"""Catálogo: títulos con su disponibilidad, alta de material y ejemplares.

Las reservas viven en app/services/reservas.py.
"""

import re
from typing import List, Optional

from sqlalchemy import func
from sqlalchemy.orm import Session

from app import models
from app.core.errores import NoEncontrado, ReglaIncumplida
from app.core.tiempo import ahora, formatear_fecha
from app.core import marc_plantillas
from app.services import busqueda
from app.services.reservas import ACTIVAS as RESERVAS_ACTIVAS
from app.services import marc as marc_svc

def sede_por_defecto(db: Session) -> Optional[int]:
    """Única sede mientras la biblioteca no tenga varias (Fase 3: una sola sede)."""
    sede = db.query(models.Biblioteca.id).order_by(models.Biblioteca.id).first()
    return sede[0] if sede else None


def buscar_por_isbn(db: Session, isbn: Optional[str]) -> Optional[models.RegistroBibliografico]:
    """Mismo ISBN aunque uno tenga guiones o espacios y el otro no."""
    digitos = re.sub(r"[^0-9X]", "", (isbn or "").upper())
    if not digitos:
        return None
    RB = models.RegistroBibliografico
    return db.query(RB).filter(
        func.upper(func.regexp_replace(RB.isbn, "[^0-9Xx]", "", "g")) == digitos).order_by(
        RB.id).first()


def _obtener_registro(db: Session, biblio_id: int) -> models.RegistroBibliografico:
    biblio = db.query(models.RegistroBibliografico).filter(
        models.RegistroBibliografico.id == biblio_id).first()
    if not biblio:
        raise NoEncontrado("Título no encontrado en el catálogo")
    return biblio


def vista_de_titulo(db: Session, biblio: models.RegistroBibliografico,
                    items: Optional[list] = None, tipos: Optional[dict] = None,
                    reservas_pendientes: Optional[int] = None) -> dict:
    """Un título con la disponibilidad agregada de sus ejemplares.

    `items`, `tipos` y `reservas_pendientes` se pasan ya cargados al listar el
    catálogo completo, para no hacer una consulta por título.
    """
    if items is None:
        items = db.query(models.Item).filter(models.Item.biblio_id == biblio.id).all()
    disponibles = [i for i in items if i.estado == "Disponible"]

    tipo = None
    if items and items[0].tipo_item_id:
        tipo = (tipos.get(items[0].tipo_item_id) if tipos is not None
                else db.get(models.TipoItem, items[0].tipo_item_id))
    if reservas_pendientes is None:
        reservas_pendientes = db.query(models.Reserva).filter(
            models.Reserva.biblio_id == biblio.id,
            models.Reserva.estado.in_(RESERVAS_ACTIVAS)).count()

    return {
        "id": str(biblio.id),
        "title": biblio.titulo or "Sin título",
        "author": biblio.autor or "Autor desconocido",
        "year": biblio.ano_publicacion,
        "category": biblio.materia or "Sin clasificar",
        "type": tipo.descripcion if tipo else "Sin tipo",
        "isbn": biblio.isbn or "N/A",
        "location": items[0].signatura_topografica if items else None,
        "copies": len(items),
        "available": len(disponibles),
        # /circulation/checkout necesita un código de barras para prestar desde la tarjeta.
        "availableBarcode": disponibles[0].codigo_barras if disponibles else None,
        "holds": reservas_pendientes,
    }


# --- Títulos y ejemplares ---------------------------------------------------------

def vistas_de_titulos(db: Session, registros: list) -> List[dict]:
    """Vista de varios títulos con tres consultas en total, sin importar cuántos sean."""
    ids = [b.id for b in registros]
    items = busqueda.items_por_titulo(db, ids)
    tipos = {t.id: t for t in db.query(models.TipoItem).all()}
    reservas = dict(db.query(models.Reserva.biblio_id, func.count(models.Reserva.id)).filter(
        models.Reserva.biblio_id.in_(ids),
        models.Reserva.estado.in_(RESERVAS_ACTIVAS)).group_by(
        models.Reserva.biblio_id).all()) if ids else {}
    return [vista_de_titulo(db, b, items[b.id], tipos, reservas.get(b.id, 0))
            for b in registros]


def listar_titulos(db: Session) -> List[dict]:
    registros = db.query(models.RegistroBibliografico).order_by(
        models.RegistroBibliografico.titulo).all()
    return vistas_de_titulos(db, registros)


def buscar_titulos(db: Session, filtros: "busqueda.Filtros", *, pagina: int, por_pagina: int,
                   orden: str) -> dict:
    """Búsqueda de la intranet: página de títulos con disponibilidad y facetas."""
    r = busqueda.buscar(db, filtros, pagina=pagina, por_pagina=por_pagina, orden=orden)
    registros = r.pop("registros")
    return {**r, "resultados": vistas_de_titulos(db, registros)}


def obtener_titulo(db: Session, biblio_id: int) -> dict:
    return vista_de_titulo(db, _obtener_registro(db, biblio_id))


def dar_de_alta(db: Session, datos) -> dict:
    """Alta de un ejemplar; si el ISBN ya existe, se suma al título en vez de duplicarlo."""
    if db.query(models.Item).filter(models.Item.codigo_barras == datos.codigo_barras).first():
        raise ReglaIncumplida(
            f"Ya existe un ejemplar con el código de barras {datos.codigo_barras}")

    tipo = db.query(models.TipoItem).filter(
        models.TipoItem.codigo == datos.tipo_item_codigo).first()
    if not tipo:
        raise ReglaIncumplida(f"No existe el tipo de ítem '{datos.tipo_item_codigo}'")

    biblio = buscar_por_isbn(db, marc_svc.normalizar_isbn(datos.isbn))
    if not biblio:
        borrador = marc_svc.desde_columnas(datos.titulo, datos.autor, datos.isbn,
                                           datos.ano_publicacion, datos.materia)
        marc, plantilla = marc_svc.preparar(borrador, marc_plantillas.POR_DEFECTO)
        biblio = models.RegistroBibliografico()
        aplicar_marc(biblio, marc, plantilla)
        db.add(biblio)
        db.flush()

    _nuevo_item(db, biblio, datos.codigo_barras, tipo, datos.signatura_topografica,
                datos.precio_reposicion)
    db.commit()
    db.refresh(biblio)
    return vista_de_titulo(db, biblio)


def _nuevo_item(db: Session, biblio, codigo_barras: str, tipo, signatura, precio,
                sede: Optional[int] = None) -> models.Item:
    sede = sede or sede_por_defecto(db)
    item = models.Item(
        biblio_id=biblio.id,
        codigo_barras=codigo_barras,
        tipo_item_id=tipo.id,
        signatura_topografica=signatura,
        estado="Disponible",
        biblioteca_propia_id=sede,
        biblioteca_actual_id=sede,
        precio_reposicion=precio,
    )
    db.add(item)
    return item


def agregar_ejemplar(db: Session, biblio_id: int, datos) -> dict:
    """Otro ejemplar de un título que ya existe (p. ej. una tesis, que no tiene ISBN)."""
    biblio = _obtener_registro(db, biblio_id)
    if db.query(models.Item).filter(models.Item.codigo_barras == datos.codigo_barras).first():
        raise ReglaIncumplida(
            f"Ya existe un ejemplar con el código de barras {datos.codigo_barras}")
    tipo = db.query(models.TipoItem).filter(
        models.TipoItem.codigo == datos.tipo_item_codigo).first()
    if not tipo:
        raise ReglaIncumplida(f"No existe el tipo de ítem '{datos.tipo_item_codigo}'")
    _nuevo_item(db, biblio, datos.codigo_barras, tipo, datos.signatura_topografica,
                datos.precio_reposicion)
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
    otro = db.query(models.RegistroBibliografico).filter(
        models.RegistroBibliografico.isbn == isbn,
        models.RegistroBibliografico.id != (propio_id or 0)).first()
    if otro:
        raise ReglaIncumplida(
            f"El ISBN {isbn} ya está en «{otro.titulo}» (registro {otro.id}). "
            "Agrega el ejemplar a ese registro o guarda igualmente si es otra edición.")


def obtener_marc(db: Session, biblio_id: int) -> dict:
    return vista_marc(_obtener_registro(db, biblio_id))


def guardar_marc(db: Session, biblio_id: int, datos) -> dict:
    biblio = _obtener_registro(db, biblio_id)
    marc, plantilla = marc_svc.preparar(datos.marc, datos.plantilla)
    if not datos.permitir_duplicado:
        _avisar_isbn_duplicado(db, marc_svc.derivar(marc)["isbn"], biblio.id)
    aplicar_marc(biblio, marc, plantilla)
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
    db.commit()
    db.refresh(biblio)
    return vista_marc(biblio)


def eliminar_registro(db: Session, biblio_id: int) -> None:
    """Solo se borra un registro sin ejemplares ni reservas activas, como en Koha."""
    biblio = _obtener_registro(db, biblio_id)
    if db.query(models.Item).filter(models.Item.biblio_id == biblio.id).count():
        raise ReglaIncumplida("El registro tiene ejemplares: elimínalos o muévelos primero")
    reservas_del_titulo = db.query(models.Reserva).filter(models.Reserva.biblio_id == biblio.id)
    if reservas_del_titulo.filter(models.Reserva.estado.in_(RESERVAS_ACTIVAS)).count():
        raise ReglaIncumplida("El registro tiene reservas activas")
    reservas_del_titulo.delete(synchronize_session=False)
    db.delete(biblio)
    db.commit()


def listar_ejemplares(db: Session, biblio_id: int) -> List[dict]:
    _obtener_registro(db, biblio_id)
    items = db.query(models.Item).filter(models.Item.biblio_id == biblio_id).order_by(
        models.Item.id).all()
    nombres = {b.id: b.nombre for b in db.query(models.Biblioteca).all()}
    destinos = {t.item_id: t.hacia_id for t in db.query(models.Traslado).filter(
        models.Traslado.item_id.in_([i.id for i in items]),
        models.Traslado.estado.in_(("Solicitado", "Enviado")))} if items else {}

    resultado = []
    for item in items:
        prestamo = db.query(models.Prestamo).filter(
            models.Prestamo.item_id == item.id,
            models.Prestamo.fecha_devolucion == None).first()  # noqa: E711
        lector = None
        if prestamo:
            usuario = db.query(models.Usuario).filter(
                models.Usuario.id == prestamo.usuario_id).first()
            lector = f"{usuario.nombre} {usuario.apellido}" if usuario else None

        resultado.append({
            "id": str(item.id),
            "barcode": item.codigo_barras,
            "location": item.signatura_topografica,
            "enumeration": item.enumeracion,
            "status": item.estado,
            "dueDate": formatear_fecha(prestamo.fecha_vencimiento) if prestamo else None,
            "borrowedBy": lector,
            "branch": nombres.get(item.biblioteca_actual_id),
            "homeBranch": nombres.get(item.biblioteca_propia_id),
            "transitTo": nombres.get(destinos.get(item.id)),
        })
    return resultado


# --- Métricas ---------------------------------------------------------------------

def estadisticas_dashboard(db: Session) -> dict:
    momento = ahora()
    return {
        "totalItems": db.query(models.Item).count(),
        "totalUsers": db.query(models.Usuario).filter(
            models.Usuario.activo == True).count(),  # noqa: E712
        "activeLoans": db.query(models.Prestamo).filter(
            models.Prestamo.fecha_devolucion == None).count(),  # noqa: E711
        "overdueLoans": db.query(models.Prestamo).filter(
            models.Prestamo.fecha_devolucion == None,  # noqa: E711
            models.Prestamo.fecha_vencimiento < momento).count(),
    }
