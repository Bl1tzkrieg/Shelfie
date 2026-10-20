"""Personal de la biblioteca: solo el administrador lo gestiona."""

from typing import List

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app import schemas
from app.core.permisos import Permiso
from app.database import get_db
from app.security import requiere
from app.services import personal

router = APIRouter(prefix="/api/v1/staff", tags=["Personal"],
                   dependencies=[Depends(requiere(Permiso.SUPERBIBLIOTECARIO))])


@router.get("", response_model=List[schemas.UserResponse])
def listar_personal(db: Session = Depends(get_db)):
    return personal.listar(db)


@router.post("", response_model=schemas.UserResponse, status_code=201)
def crear(payload: schemas.NuevoPersonalRequest, db: Session = Depends(get_db)):
    """Alta con una clave temporal: al entrar tendrá que elegir una propia."""
    return personal.crear(db, username=payload.username, nombre=payload.nombre,
                          apellido=payload.apellido, rol=payload.rol,
                          clave_temporal=payload.clave_temporal)


@router.put("/{usuario_id}/role", response_model=schemas.UserResponse)
def cambiar_rol(usuario_id: int, payload: schemas.RolRequest, db: Session = Depends(get_db)):
    return personal.cambiar_rol(db, usuario_id, payload.rol)


@router.put("/{usuario_id}/active", response_model=schemas.UserResponse)
def cambiar_estado(usuario_id: int, payload: schemas.EstadoRequest,
                   db: Session = Depends(get_db)):
    return personal.cambiar_estado(db, usuario_id, payload.activo)


@router.post("/{usuario_id}/password", response_model=schemas.UserResponse)
def restablecer_clave(usuario_id: int, payload: schemas.ClaveTemporalRequest,
                      db: Session = Depends(get_db)):
    return personal.restablecer_clave(db, usuario_id, payload.clave_temporal)
