"""Catálogo MARC: el registro como fuente y sus columnas derivadas.

El alta, la edición simple y los ejemplares están en `services/libros.py`."""

import re
from typing import Iterable, List, Optional, Union

from sqlalchemy import false, func, or_
from sqlalchemy.orm import Session

from app import models
from app.core.errores import NoEncontrado, ReglaIncumplida
from app.core.signaturas import normalizar_cota
from app.services import ficha, registro
from app.services import marc as marc_svc

RB = models.RegistroBibliografico


# --- ISBN ---------------------------------------------------------------------------

def digitos_isbn(texto: Optional[str]) -> str:
    """Solo los dígitos (y la X final) de un ISBN: «978-0-307» → «9780307»."""
    return re.sub(r"[^0-9X]", "", (marc_svc.normalizar_isbn(texto) or "").upper())


def _isbns_sin_signos():
    """« 9780307474728 8497592208 »: todos los ISBN del registro, sin guiones y entre
    espacios, para comparar uno entero sin que el final de uno y el principio del otro
    formen otro."""
    limpios = func.upper(func.regexp_replace(func.coalesce(RB.isbns, ""), "[^0-9Xx ]", "", "g"))
    return func.concat(" ", limpios, " ")


def tiene_isbn(isbns: Iterable[str]):
    """Condición: el registro tiene alguno de esos ISBN (con o sin guiones) en cualquier 020."""
    digitos = sorted({d for d in (digitos_isbn(i) for i in isbns) if d})
    if not digitos:
        return false()
    return or_(*(_isbns_sin_signos().like(f"% {d} %") for d in digitos))


def isbn_parcial(digitos: str):
    """Condición: alguno de los ISBN del registro contiene esos dígitos."""
    return _isbns_sin_signos().like(f"%{digitos}%")


def buscar_por_isbn(db: Session, isbns: Union[str, Iterable[str], None],
                    excluir_id: Optional[int] = None) -> Optional[models.RegistroBibliografico]:
    """El primer registro que comparte un ISBN (cualquiera de sus 020) aunque uno tenga guiones
    o espacios y el otro no."""
    lista: List[str] = [isbns] if isinstance(isbns, str) else list(isbns or [])
    if not any(digitos_isbn(i) for i in lista):
        return None
    consulta = db.query(RB).filter(tiene_isbn(lista))
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

def aplicar_marc(biblio: models.RegistroBibliografico, marc: dict, plantilla, *,
                 editando: bool = False) -> None:
    """Guarda el MARC y actualiza las columnas que se derivan de él.

    La cota sale del 092 $a + $b; si no hay, del 082 o del 050 ($a + $b), normalizada. Si
    el MARC no trae ninguno, el registro conserva la cota que tenía (p. ej. la del 952 al
    importar de Koha). Al editar (`editando`), la cota solo se recalcula si cambió esa
    clasificación: un importado con 082 y la cota del 952 la conserva aunque se guarde, y
    cambiar el 092, el 082 o el 050 sí la cambia. La editorial (264 con 2.º indicador 1 o,
    si no hay, 260 $b, sin la puntuación ISBD final) se lee igual que en el formulario."""
    clasificacion = ficha.cota_de_clasificacion(marc)
    if (editando and biblio.cota and biblio.marc_json is not None
            and ficha.cota_de_clasificacion(biblio.marc_json) == clasificacion):
        clasificacion = None  # no cambió: queda la cota que tenía
    biblio.marc_json = marc
    biblio.plantilla = plantilla.codigo
    for columna, valor in marc_svc.derivar(marc).items():
        setattr(biblio, columna, valor)
    biblio.cota = clasificacion or biblio.cota
    biblio.editorial = ficha.desde_marc(marc).editorial


def mover_ejemplares_de_cota(db: Session, biblio: models.RegistroBibliografico,
                             cota_anterior: Optional[str]) -> List[models.Item]:
    """Si la cota del registro cambió, los ejemplares que tenían la anterior (la heredaban)
    pasan a la nueva; los que tienen una cota propia no cambian. Devuelve los movidos."""
    cota_anterior = normalizar_cota(cota_anterior)
    if biblio.cota == cota_anterior:
        return []
    heredan = [i for i in db.query(models.Item).filter(models.Item.biblio_id == biblio.id)
               if normalizar_cota(i.signatura_topografica) == cota_anterior]
    for item in heredan:
        item.signatura_topografica = biblio.cota
    return heredan


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


def _avisar_isbn_duplicado(db: Session, marc: dict, propio_id: Optional[int]) -> None:
    isbns = (marc_svc.derivar(marc)["isbns"] or "").split()
    otro = buscar_por_isbn(db, isbns, excluir_id=propio_id)
    if otro:
        repetido = next((i for i in isbns if db.query(RB.id).filter(
            RB.id == otro.id, tiene_isbn([i])).first()), isbns[0])
        raise ReglaIncumplida(
            f"El ISBN {repetido} ya está en «{otro.titulo}» (registro {otro.id}). "
            "Agrega el ejemplar a ese registro o guarda igualmente si es otra edición.")


def obtener_marc(db: Session, biblio_id: int) -> dict:
    return vista_marc(obtener_registro(db, biblio_id))


_CAMPOS_DERIVADOS = ("titulo", "autor", "isbn", "ano_publicacion", "materia", "editorial", "cota",
                     "plantilla")


def guardar_marc(db: Session, biblio_id: int, datos) -> dict:
    biblio = obtener_registro(db, biblio_id, bloquear=True)
    marc, plantilla = marc_svc.preparar(datos.marc, datos.plantilla)
    if not datos.permitir_duplicado:
        _avisar_isbn_duplicado(db, marc, biblio.id)
    antes = {c: getattr(biblio, c) for c in _CAMPOS_DERIVADOS}
    marc_antes = biblio.marc_json
    cota_anterior = biblio.cota
    aplicar_marc(biblio, marc, plantilla, editando=True)
    heredan = mover_ejemplares_de_cota(db, biblio, cota_anterior)
    cambios = registro.diferencias(antes, {c: getattr(biblio, c) for c in _CAMPOS_DERIVADOS})
    if marc_antes != biblio.marc_json or heredan:
        # Como el CataloguingLog de Koha: queda el MARC anterior para ver qué cambió.
        detalle = {"cambios": cambios, "marc_anterior": marc_antes}
        if heredan:
            detalle["ejemplares_con_la_cota_nueva"] = [i.id for i in heredan]
        registro.anotar(db, "catalogo", "edicion", f"Editó el registro MARC de «{biblio.titulo}»",
                        biblio=biblio, datos=detalle)
    db.commit()
    db.refresh(biblio)
    return vista_marc(biblio)


def crear_registro(db: Session, datos) -> dict:
    """Catalogación completa: un registro MARC sin ejemplares (se agregan después)."""
    marc, plantilla = marc_svc.preparar(datos.marc, datos.plantilla)
    if not datos.permitir_duplicado:
        _avisar_isbn_duplicado(db, marc, None)
    biblio = models.RegistroBibliografico()
    aplicar_marc(biblio, marc, plantilla)
    db.add(biblio)
    db.flush()
    registro.anotar(db, "catalogo", "alta", f"Catalogó «{biblio.titulo}» ({biblio.plantilla})",
                    biblio=biblio)
    db.commit()
    db.refresh(biblio)
    return vista_marc(biblio)
