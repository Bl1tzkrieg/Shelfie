from typing import List

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app import models, schemas
from app.core.permisos import Permiso
from app.database import get_db
from app.security import requiere, requiere_personal
from app.services import personal

router = APIRouter(prefix="/api/v1/staff", tags=["Personal"],
                   dependencies=[Depends(requiere_personal)])


@router.get("", response_model=List[schemas.UserResponse])
def listar_personal(db: Session = Depends(get_db)):
    return personal.listar(db)


@router.get("/permissions", response_model=schemas.CatalogoPermisosResponse)
def catalogo_de_permisos():
    """Permisos disponibles y perfiles predefinidos."""
    return personal.catalogo_de_permisos()


@router.put("/{nro_carnet}", response_model=schemas.UserResponse)
def asignar_permisos(
    nro_carnet: str,
    payload: schemas.AsignarPermisosRequest,
    db: Session = Depends(get_db),
    actor: models.Usuario = Depends(requiere(Permiso.SUPERBIBLIOTECARIO)),
):
    """Da o quita acceso a la intranet y fija los permisos. Solo superbibliotecarios."""
    return personal.asignar(db, actor, nro_carnet, payload.es_personal, payload.permisos)
