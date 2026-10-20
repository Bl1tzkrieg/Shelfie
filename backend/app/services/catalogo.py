"""Catálogo MARC: el registro como fuente y sus columnas derivadas.

El alta, la edición simple y los ejemplares están en `services/libros.py`."""

import re
from typing import Optional

from sqlalchemy import func
from sqlalchemy.orm import Session

from app import models
from app.core.errores import NoEncontrado, ReglaIncumplida
from app.services import ficha, registro
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


def obtener_registro(db: Session, biblio_id: int, *,
                     bloquear: bool = False) -> models.RegistroBibliografico:
    """El registro o 404. `bloquear` lo toma con FOR UPDATE (p. ej. para numerar copias)."""
    consulta = db.query(models.RegistroBibliografico).filter(
        models.RegistroBibliografico.id == biblio_id)
    biblio = (consulta.with_for_update() if bloquear else consulta).first()
    if not biblio:
        raise NoEncontrado("Título no encontrado en el catálogo")
    return biblio


# --- Registro MARC ----------------------------------------------------------------

def aplicar_marc(biblio: models.RegistroBibliografico, marc: dict, plantilla) -> None:
    """Guarda el MARC y actualiza las columnas que se derivan de él.

    La cota (092 $a + $b, normalizada) y la editorial (264 con 2.º indicador 1 o, si no hay,
    260 $b, sin la puntuación ISBD final) se leen igual que en el formulario."""
    biblio.marc_json = marc
    biblio.plantilla = plantilla.codigo
    for columna, valor in marc_svc.derivar(marc).items():
        setattr(biblio, columna, valor)
    leida = ficha.desde_marc(marc)
    biblio.cota = leida.cota or None
    biblio.editorial = leida.editorial


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
    return vista_marc(obtener_registro(db, biblio_id))


_CAMPOS_DERIVADOS = ("titulo", "autor", "isbn", "ano_publicacion", "materia", "editorial", "cota",
                     "plantilla")


def guardar_marc(db: Session, biblio_id: int, datos) -> dict:
    biblio = obtener_registro(db, biblio_id)
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
