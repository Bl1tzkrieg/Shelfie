"""Reglas de circulación: categoría de lector × tipo de ítem × sede.

Una regla puede dejar cualquiera de las tres dimensiones en NULL ("todas").
Para un préstamo se aplica la regla más específica que coincida, con el mismo
orden de precedencia que Koha: la sede pesa más que el tipo de ítem, y el tipo
de ítem más que la categoría. La regla general (todo NULL) siempre existe.
"""

from typing import List, Optional

from sqlalchemy import or_
from sqlalchemy.orm import Session

from app import models
from app.core.errores import NoEncontrado, ReglaIncumplida

R = models.ReglaCirculacion
CAMPOS_EDITABLES = ("prestable", "dias_prestamo", "max_prestamos", "max_renovaciones",
                    "multa_por_dia", "multa_maxima", "dias_gracia", "max_reservas")


def _especificidad(regla: models.ReglaCirculacion) -> int:
    return (4 if regla.biblioteca_id else 0) + (2 if regla.tipo_item_id else 0) + \
        (1 if regla.categoria_id else 0)


def elegir(reglas: List[models.ReglaCirculacion], categoria_id: Optional[int],
           tipo_item_id: Optional[int], biblioteca_id: Optional[int]
           ) -> Optional[models.ReglaCirculacion]:
    """Igual que regla_para, sobre reglas ya cargadas (para listados sin N+1)."""
    candidatas = [r for r in reglas
                  if r.categoria_id in (None, categoria_id)
                  and r.tipo_item_id in (None, tipo_item_id)
                  and r.biblioteca_id in (None, biblioteca_id)]
    return max(candidatas, key=_especificidad) if candidatas else None


def regla_para(db: Session, categoria_id: Optional[int], tipo_item_id: Optional[int],
               biblioteca_id: Optional[int]) -> models.ReglaCirculacion:
    candidatas = db.query(R).filter(
        or_(R.categoria_id == None, R.categoria_id == categoria_id),  # noqa: E711
        or_(R.tipo_item_id == None, R.tipo_item_id == tipo_item_id),  # noqa: E711
        or_(R.biblioteca_id == None, R.biblioteca_id == biblioteca_id),  # noqa: E711
    ).all()
    if not candidatas:
        raise ReglaIncumplida(
            "No hay una regla de circulación aplicable: crea la regla general en Configuración")
    return max(candidatas, key=_especificidad)


def regla_general(db: Session) -> models.ReglaCirculacion:
    return regla_para(db, None, None, None)


# --- Administración -----------------------------------------------------------------

def vista(regla: models.ReglaCirculacion, nombres: dict) -> dict:
    return {
        "id": regla.id,
        "categoria_id": regla.categoria_id,
        "categoria": nombres["categorias"].get(regla.categoria_id, "Todas"),
        "tipo_item_id": regla.tipo_item_id,
        "tipo_item": nombres["tipos"].get(regla.tipo_item_id, "Todos"),
        "biblioteca_id": regla.biblioteca_id,
        "biblioteca": nombres["bibliotecas"].get(regla.biblioteca_id, "Todas"),
        "prestable": regla.prestable,
        "dias_prestamo": regla.dias_prestamo,
        "max_prestamos": regla.max_prestamos,
        "max_renovaciones": regla.max_renovaciones,
        "multa_por_dia": float(regla.multa_por_dia),
        "multa_maxima": float(regla.multa_maxima) if regla.multa_maxima is not None else None,
        "dias_gracia": regla.dias_gracia,
        "max_reservas": regla.max_reservas,
    }


def _nombres(db: Session) -> dict:
    return {
        "categorias": {c.id: c.descripcion for c in db.query(models.CategoriaUsuario).all()},
        "tipos": {t.id: t.descripcion for t in db.query(models.TipoItem).all()},
        "bibliotecas": {b.id: b.nombre for b in db.query(models.Biblioteca).all()},
    }


def opciones(db: Session) -> dict:
    """Valores posibles de cada dimensión, para armar el formulario de reglas."""
    def lista(modelo, nombre, orden):
        return [{"id": x.id, "codigo": x.codigo, "nombre": getattr(x, nombre)}
                for x in db.query(modelo).order_by(orden).all()]
    return {
        "categorias": lista(models.CategoriaUsuario, "descripcion", models.CategoriaUsuario.codigo),
        "tipos_item": lista(models.TipoItem, "descripcion", models.TipoItem.codigo),
        "bibliotecas": lista(models.Biblioteca, "nombre", models.Biblioteca.codigo),
    }


def listar(db: Session) -> List[dict]:
    nombres = _nombres(db)
    reglas = db.query(R).all()
    reglas.sort(key=lambda r: (_especificidad(r), r.id))
    return [vista(r, nombres) for r in reglas]


def guardar(db: Session, datos) -> dict:
    """Crea o reemplaza la regla de una combinación categoría × tipo × sede."""
    regla = db.query(R).filter(
        R.categoria_id.is_(None) if datos.categoria_id is None else R.categoria_id == datos.categoria_id,
        R.tipo_item_id.is_(None) if datos.tipo_item_id is None else R.tipo_item_id == datos.tipo_item_id,
        R.biblioteca_id.is_(None) if datos.biblioteca_id is None else R.biblioteca_id == datos.biblioteca_id,
    ).first()
    if regla is None:
        regla = R(categoria_id=datos.categoria_id, tipo_item_id=datos.tipo_item_id,
                  biblioteca_id=datos.biblioteca_id)
        db.add(regla)
    for campo in CAMPOS_EDITABLES:
        setattr(regla, campo, getattr(datos, campo))
    db.commit()
    db.refresh(regla)
    return vista(regla, _nombres(db))


def eliminar(db: Session, regla_id: int) -> None:
    regla = db.get(R, regla_id)
    if not regla:
        raise NoEncontrado("Regla no encontrada")
    if regla.categoria_id is None and regla.tipo_item_id is None and regla.biblioteca_id is None:
        raise ReglaIncumplida("La regla general no se puede eliminar: es la que aplica por defecto")
    db.delete(regla)
    db.commit()


def asegurar_regla_de_categoria(db: Session, categoria: models.CategoriaUsuario,
                                dias_prestamo: int, max_prestamos: int) -> models.ReglaCirculacion:
    """Crea la regla propia de una categoría (copiando la general) si todavía no existe."""
    regla = db.query(R).filter(R.categoria_id == categoria.id, R.tipo_item_id.is_(None),
                               R.biblioteca_id.is_(None)).first()
    if regla:
        return regla
    base = regla_general(db)
    regla = R(categoria_id=categoria.id, prestable=True, dias_prestamo=dias_prestamo,
              max_prestamos=max_prestamos, max_renovaciones=base.max_renovaciones,
              multa_por_dia=base.multa_por_dia, multa_maxima=base.multa_maxima,
              dias_gracia=base.dias_gracia, max_reservas=base.max_reservas)
    db.add(regla)
    db.flush()
    return regla
