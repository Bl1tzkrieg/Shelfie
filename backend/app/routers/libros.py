"""Libros con la ficha simple y sus ejemplares. Todas las rutas exigen catalogador."""

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app import schemas
from app.core.permisos import Permiso
from app.database import get_db
from app.security import requiere
from app.services import libros

router = APIRouter(prefix="/api/v1/books", tags=["Libros"],
                   dependencies=[Depends(requiere(Permiso.CATALOGO))])


@router.get("")
def listar(q: str = Query("", description="Título, autor o cota"),
           pagina: int = Query(1, ge=1), por_pagina: int = Query(50, ge=1, le=200),
           db: Session = Depends(get_db)):
    """Libros en el orden del estante (por cota); los que no tienen cota, al final."""
    return libros.listar(db, q=q, pagina=pagina, por_pagina=por_pagina)


@router.post("", status_code=201)
def crear(payload: schemas.NuevoLibroRequest, db: Session = Depends(get_db)):
    """Alta con sus ejemplares. Si puede estar repetido responde 409 POSIBLE_DUPLICADO con
    las coincidencias; con `forzar` se guarda igual."""
    return libros.crear(db, payload.ficha, ejemplares=payload.ejemplares,
                        nota_ejemplares=payload.nota_ejemplares, forzar=payload.forzar)


@router.get("/{biblio_id}")
def obtener(biblio_id: int, db: Session = Depends(get_db)):
    return libros.obtener(db, biblio_id)


@router.put("/{biblio_id}")
def actualizar(biblio_id: int, payload: schemas.FichaLibro, db: Session = Depends(get_db)):
    """Guarda la ficha; lo que el formulario no muestra queda como estaba en el MARC."""
    return libros.actualizar(db, biblio_id, payload)


@router.delete("/{biblio_id}", status_code=204)
def eliminar(biblio_id: int, db: Session = Depends(get_db)):
    """Baja del libro con sus ejemplares."""
    libros.eliminar(db, biblio_id)


@router.post("/{biblio_id}/copies", status_code=201)
def agregar_ejemplar(biblio_id: int, payload: schemas.EjemplarRequest,
                     db: Session = Depends(get_db)):
    """Otro ejemplar; sin cota lleva la del libro y sin copia, la siguiente (c.N)."""
    return libros.agregar_ejemplar(db, biblio_id, **payload.model_dump())


@router.patch("/{biblio_id}/copies/{item_id}")
def editar_ejemplar(biblio_id: int, item_id: int, payload: schemas.EjemplarRequest,
                    db: Session = Depends(get_db)):
    """Corrige un ejemplar: solo cambia lo enviado. Devuelve el libro."""
    return libros.editar_ejemplar(db, biblio_id, item_id, payload.model_dump(exclude_unset=True))


@router.delete("/{biblio_id}/copies/{item_id}", status_code=204)
def eliminar_ejemplar(biblio_id: int, item_id: int, db: Session = Depends(get_db)):
    """Borra un ejemplar cargado por error."""
    libros.eliminar_ejemplar(db, biblio_id, item_id)
