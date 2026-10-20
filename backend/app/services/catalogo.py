"""Catálogo: títulos con su disponibilidad, alta de material y ejemplares."""

import re
from typing import List, Optional

from sqlalchemy import func
from sqlalchemy.orm import Session

from app import models
from app.core.errores import NoEncontrado, ReglaIncumplida
from app.core.tiempo import formatear_fecha
from app.core import marc_plantillas
from app.services import busqueda, registro
from app.services import marc as marc_svc

def sede_por_defecto(db: Session) -> Optional[int]:
    """Única sede mientras la biblioteca no tenga varias (Fase 3: una sola sede)."""
    sede = db.query(models.Biblioteca.id).order_by(models.Biblioteca.id).first()
    return sede[0] if sede else None


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
                    items: Optional[list] = None, tipos: Optional[dict] = None) -> dict:
    """Un título con la disponibilidad agregada de sus ejemplares.

    `items` y `tipos` se pasan ya cargados al listar el catálogo completo, para no
    hacer una consulta por título.
    """
    if items is None:
        items = db.query(models.Item).filter(models.Item.biblio_id == biblio.id).all()
    disponibles = [i for i in items if i.estado == "Disponible"]

    tipo = None
    if items and items[0].tipo_item_id:
        tipo = (tipos.get(items[0].tipo_item_id) if tipos is not None
                else db.get(models.TipoItem, items[0].tipo_item_id))

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
        "availableBarcode": disponibles[0].codigo_barras if disponibles else None,
    }


# --- Títulos y ejemplares ---------------------------------------------------------

def vistas_de_titulos(db: Session, registros: list) -> List[dict]:
    """Vista de varios títulos con dos consultas en total, sin importar cuántos sean."""
    ids = [b.id for b in registros]
    items = busqueda.items_por_titulo(db, ids)
    tipos = {t.id: t for t in db.query(models.TipoItem).all()}
    return [vista_de_titulo(db, b, items[b.id], tipos) for b in registros]


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

    item = _nuevo_item(db, biblio, datos.codigo_barras, tipo, datos.signatura_topografica,
                       datos.precio_reposicion)
    db.flush()
    registro.anotar(db, "catalogo", "alta",
                    f"Alta rápida: ejemplar {item.codigo_barras} de «{biblio.titulo}»",
                    biblio=biblio, item=item)
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
    item = _nuevo_item(db, biblio, datos.codigo_barras, tipo, datos.signatura_topografica,
                       datos.precio_reposicion)
    db.flush()
    registro.anotar(db, "catalogo", "alta",
                    f"Nuevo ejemplar {item.codigo_barras} de «{biblio.titulo}»",
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


_CAMPOS_EJEMPLAR = ("codigo_barras", "tipo_item_id", "signatura_topografica", "enumeracion",
                    "precio_reposicion", "biblioteca_propia_id", "estado")


def editar_ejemplar(db: Session, biblio_id: int, item_id: int, datos: dict) -> List[dict]:
    """Corrige un ejemplar: código, signatura, tipo, sede propia, precio o baja (Retirado)."""
    item = _obtener_ejemplar(db, biblio_id, item_id)
    antes = {c: getattr(item, c) for c in _CAMPOS_EJEMPLAR}
    if "codigo_barras" in datos:
        codigo = (datos["codigo_barras"] or "").strip()
        if not codigo:
            raise ReglaIncumplida("El código de barras no puede quedar vacío")
        otro = db.query(models.Item.id).filter(models.Item.codigo_barras == codigo,
                                               models.Item.id != item.id).first()
        if otro:
            raise ReglaIncumplida(f"Ya existe un ejemplar con el código de barras {codigo}")
        item.codigo_barras = codigo
    if datos.get("tipo_item_codigo") is not None:
        tipo = db.query(models.TipoItem).filter(
            models.TipoItem.codigo == datos["tipo_item_codigo"]).first()
        if not tipo:
            raise ReglaIncumplida(f"No existe el tipo de ítem '{datos['tipo_item_codigo']}'")
        item.tipo_item_id = tipo.id
    for campo in ("signatura_topografica", "enumeracion"):
        if campo in datos:
            item.__setattr__(campo, (datos[campo] or "").strip() or None)
    if "precio_reposicion" in datos:
        item.precio_reposicion = datos["precio_reposicion"]
    if datos.get("biblioteca_propia_id") is not None:
        if not db.get(models.Biblioteca, datos["biblioteca_propia_id"]):
            raise ReglaIncumplida("La sede elegida no existe")
        item.biblioteca_propia_id = datos["biblioteca_propia_id"]
    if datos.get("estado"):
        item.estado = datos["estado"]
    db.flush()
    cambios = registro.diferencias(antes, {c: getattr(item, c) for c in _CAMPOS_EJEMPLAR})
    if cambios:
        baja = cambios.get("estado", [None, None])[1] == "Retirado"
        registro.anotar(db, "catalogo", "baja" if baja else "edicion",
                        f"{'Dio de baja' if baja else 'Editó'} el ejemplar {item.codigo_barras}"
                        + ("" if baja else f" ({', '.join(cambios)})"),
                        biblio=item.biblio_id, item=item, datos={"cambios": cambios})
    db.commit()
    return listar_ejemplares(db, biblio_id)


def eliminar_ejemplar(db: Session, biblio_id: int, item_id: int) -> None:
    """Borra un ejemplar cargado por error."""
    item = _obtener_ejemplar(db, biblio_id, item_id)
    registro.anotar(db, "catalogo", "eliminacion",
                    f"Eliminó el ejemplar {item.codigo_barras} (cargado por error)",
                    biblio=item.biblio_id, objeto=("ejemplar", item.id),
                    datos={"codigo_barras": item.codigo_barras,
                           "signatura": item.signatura_topografica})
    db.delete(item)
    db.commit()


def listar_ejemplares(db: Session, biblio_id: int) -> List[dict]:
    _obtener_registro(db, biblio_id)
    items = db.query(models.Item).filter(models.Item.biblio_id == biblio_id).order_by(
        models.Item.id).all()
    nombres = {b.id: b.nombre for b in db.query(models.Biblioteca).all()}
    tipos = {t.id: t.codigo for t in db.query(models.TipoItem).all()}

    resultado = []
    for item in items:
        resultado.append({
            "id": str(item.id),
            "barcode": item.codigo_barras,
            "location": item.signatura_topografica,
            "enumeration": item.enumeracion,
            "status": item.estado,
            "branch": nombres.get(item.biblioteca_actual_id),
            "homeBranch": nombres.get(item.biblioteca_propia_id),
            "itemType": tipos.get(item.tipo_item_id),
            "homeBranchId": item.biblioteca_propia_id,
            "price": float(item.precio_reposicion) if item.precio_reposicion is not None else None,
            "lastSeen": formatear_fecha(item.fecha_ultimo_inventario),
        })
    return resultado
