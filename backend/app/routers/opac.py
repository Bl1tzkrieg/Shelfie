"""OPAC — Online Public Access Catalog.

Endpoints públicos de consulta para la comunidad. A diferencia del resto de la
API (pensada para la intranet), aquí no se expone ningún dato personal de los
lectores: solo disponibilidad bibliográfica.
"""

from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import or_
from sqlalchemy.orm import Session

from app import models
from app.database import get_db

router = APIRouter(prefix="/api/v1/opac", tags=["OPAC"])


def _vista_publica(db: Session, biblio: models.RegistroBibliografico) -> dict:
    items = db.query(models.Item).filter(models.Item.biblio_id == biblio.id).all()
    disponibles = [i for i in items if i.estado == "Disponible"]
    return {
        "id": str(biblio.id),
        "titulo": biblio.titulo,
        "autor": biblio.autor,
        "isbn": biblio.isbn,
        "ano_publicacion": biblio.ano_publicacion,
        "materia": biblio.materia,
        "ejemplares": len(items),
        "disponibles": len(disponibles),
        "estado": "Disponible" if disponibles else "Todos los ejemplares prestados",
        "ubicaciones": sorted({i.signatura_topografica for i in items if i.signatura_topografica}),
    }


@router.get("/search")
def busqueda_basica(
    q: str = Query("", description="Texto libre: título, autor o ISBN"),
    limit: int = Query(50, ge=1, le=200),
    db: Session = Depends(get_db),
):
    """Búsqueda simple sobre título, autor e ISBN."""
    consulta = db.query(models.RegistroBibliografico)

    if q.strip():
        patron = f"%{q.strip()}%"
        consulta = consulta.filter(or_(
            models.RegistroBibliografico.titulo.ilike(patron),
            models.RegistroBibliografico.autor.ilike(patron),
            models.RegistroBibliografico.isbn.ilike(patron),
        ))

    registros = consulta.order_by(models.RegistroBibliografico.titulo).limit(limit).all()
    return {"query": q, "total": len(registros),
            "resultados": [_vista_publica(db, b) for b in registros]}


@router.get("/advanced-search")
def busqueda_avanzada(
    titulo: Optional[str] = None,
    autor: Optional[str] = None,
    isbn: Optional[str] = None,
    materia: Optional[str] = None,
    ano_desde: Optional[int] = None,
    ano_hasta: Optional[int] = None,
    solo_disponibles: bool = False,
    limit: int = Query(50, ge=1, le=200),
    db: Session = Depends(get_db),
):
    """Búsqueda por campos combinados, al estilo de un OPAC clásico."""
    consulta = db.query(models.RegistroBibliografico)

    if titulo:
        consulta = consulta.filter(models.RegistroBibliografico.titulo.ilike(f"%{titulo}%"))
    if autor:
        consulta = consulta.filter(models.RegistroBibliografico.autor.ilike(f"%{autor}%"))
    if isbn:
        consulta = consulta.filter(models.RegistroBibliografico.isbn.ilike(f"%{isbn}%"))
    if materia:
        consulta = consulta.filter(models.RegistroBibliografico.materia.ilike(f"%{materia}%"))
    if ano_desde:
        consulta = consulta.filter(models.RegistroBibliografico.ano_publicacion >= ano_desde)
    if ano_hasta:
        consulta = consulta.filter(models.RegistroBibliografico.ano_publicacion <= ano_hasta)

    registros = consulta.order_by(models.RegistroBibliografico.titulo).limit(limit).all()
    resultados = [_vista_publica(db, b) for b in registros]

    if solo_disponibles:
        resultados = [r for r in resultados if r["disponibles"] > 0]

    return {"total": len(resultados), "resultados": resultados}


@router.get("/record/{biblio_id}")
def ficha_publica(biblio_id: int, db: Session = Depends(get_db)):
    biblio = db.query(models.RegistroBibliografico).filter(
        models.RegistroBibliografico.id == biblio_id).first()
    if not biblio:
        raise HTTPException(status_code=404, detail="Registro no encontrado")
    return _vista_publica(db, biblio)


@router.get("/subjects", response_model=List[str])
def materias(db: Session = Depends(get_db)):
    """Materias presentes en el catálogo, para navegar por tema."""
    filas = db.query(models.RegistroBibliografico.materia).distinct().all()
    return sorted({f[0] for f in filas if f[0]})
