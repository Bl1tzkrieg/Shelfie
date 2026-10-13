"""OPAC — Online Public Access Catalog.

Endpoints públicos de consulta para la comunidad. A diferencia del resto de la
API (pensada para la intranet), aquí no se expone ningún dato personal de los
lectores: solo disponibilidad bibliográfica.
"""

from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response
from sqlalchemy.orm import Session

from app import models, schemas
from app.database import get_db
from app.security import abrir_sesion_opac, cerrar_sesion_opac, get_lector, verificar_origen
from app.services import autenticacion, cuenta_opac, listas, opac

router = APIRouter(prefix="/api/v1/opac", tags=["OPAC"])


@router.get("/search")
def busqueda_basica(
    q: str = Query("", description="Texto libre: título, autor, materia o ISBN"),
    limit: int = Query(50, ge=1, le=200),
    pagina: int = Query(1, ge=1),
    orden: str = Query("relevancia", pattern="^(relevancia|titulo|ano_desc|ano_asc)$"),
    materia: Optional[str] = None,
    autor: Optional[str] = None,
    tipo: Optional[str] = None,
    disponible: Optional[str] = Query(None, pattern="^(si|no)$"),
    decada: Optional[int] = None,
    db: Session = Depends(get_db),
):
    """Búsqueda simple sin acentos y por raíz ("arbol" encuentra "Árboles"), con facetas."""
    return opac.busqueda_basica(db, q, limit, pagina, orden, materia=materia, autor=autor,
                                tipo=tipo, disponible=disponible, decada=decada)


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
    pagina: int = Query(1, ge=1),
    db: Session = Depends(get_db),
):
    """Búsqueda por campos combinados, al estilo de un OPAC clásico."""
    return opac.busqueda_avanzada(db, titulo, autor, isbn, materia, ano_desde, ano_hasta,
                                  solo_disponibles, limit, pagina)


@router.get("/record/{biblio_id}")
def ficha_publica(biblio_id: int, db: Session = Depends(get_db)):
    return opac.ficha(db, biblio_id)


@router.get("/subjects", response_model=List[str])
def materias(db: Session = Depends(get_db)):
    """Materias presentes en el catálogo, para navegar por tema."""
    return opac.materias(db)


@router.get("/library")
def biblioteca(db: Session = Depends(get_db)):
    """Nombre y contacto de la institución, para la cabecera y el pie del OPAC."""
    return opac.biblioteca(db)


@router.get("/branches")
def puntos_de_retiro(db: Session = Depends(get_db)):
    """Sedes donde se retiran las reservas, con dirección y teléfono."""
    return opac.puntos_de_retiro(db)


def _lector_opcional(request: Request, db: Session = Depends(get_db)) -> Optional[models.Usuario]:
    try:
        return get_lector(request, db)
    except HTTPException:
        return None


@router.get("/lists/{lista_id}")
def lista_publica(lista_id: int, lector: Optional[models.Usuario] = Depends(_lector_opcional),
                  db: Session = Depends(get_db)):
    """Una lista pública (o una propia, con sesión del OPAC)."""
    return listas.ver(db, lista_id, lector)


# --- Sesión del lector -------------------------------------------------------------------

@router.post("/login")
def login(payload: schemas.LoginRequest, request: Request, response: Response,
          db: Session = Depends(get_db)):
    """Entrada del lector con su carnet (o usuario) y contraseña. Cookie propia del OPAC."""
    verificar_origen(request)
    usuario = autenticacion.autenticar_lector(db, payload.username, payload.password)
    abrir_sesion_opac(response, usuario)
    return cuenta_opac.resumen(db, usuario)


@router.post("/logout", status_code=204)
def logout(response: Response):
    cerrar_sesion_opac(response)
