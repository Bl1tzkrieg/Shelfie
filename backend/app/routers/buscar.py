"""Búsqueda y ficha públicas: sin sesión."""

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.database import get_db
from app.services import busqueda, libros

router = APIRouter(prefix="/api/v1/buscar", tags=["Búsqueda pública"])


@router.get("")
def buscar(q: str = Query("", description="Palabras, cota o ISBN"),
           campo: str = Query("todo", description="todo, titulo, autor, materia, cota, isbn o editorial"),
           pagina: int = Query(1, ge=1), db: Session = Depends(get_db)):
    """Resultados de 20 en 20: por relevancia y luego en el orden del estante."""
    return busqueda.buscar(db, q, campo=campo, pagina=pagina)


@router.get("/{biblio_id}")
def ficha(biblio_id: int, db: Session = Depends(get_db)):
    """La ficha del libro y la cota y nota de cada ejemplar; sin códigos de barras ni MARC."""
    return libros.ficha_publica(db, biblio_id)
