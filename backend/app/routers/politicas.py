"""Reglas de circulación y calendario de la biblioteca."""

from typing import List

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app import schemas
from app.core.permisos import Permiso
from app.database import get_db
from app.security import requiere, requiere_personal
from app.services import calendario, reglas

router = APIRouter(prefix="/api/v1", tags=["Políticas de circulación"],
                   dependencies=[Depends(requiere_personal)])

CONFIGURA = [Depends(requiere(Permiso.CONFIGURACION))]


@router.get("/circulation-rules", response_model=List[schemas.ReglaResponse])
def listar_reglas(db: Session = Depends(get_db)):
    """Reglas de la más general a la más específica."""
    return reglas.listar(db)


@router.get("/circulation-rules/options", response_model=schemas.OpcionesReglaResponse)
def opciones_de_reglas(db: Session = Depends(get_db)):
    """Categorías, tipos de ítem y sedes que puede combinar una regla."""
    return reglas.opciones(db)


@router.put("/circulation-rules", response_model=schemas.ReglaResponse, dependencies=CONFIGURA)
def guardar_regla(payload: schemas.ReglaRequest, db: Session = Depends(get_db)):
    """Crea o reemplaza la regla de una combinación categoría × tipo de ítem × sede."""
    return reglas.guardar(db, payload)


@router.delete("/circulation-rules/{regla_id}", status_code=204, dependencies=CONFIGURA)
def eliminar_regla(regla_id: int, db: Session = Depends(get_db)):
    reglas.eliminar(db, regla_id)


@router.get("/calendar", response_model=schemas.CalendarioResponse)
def ver_calendario(db: Session = Depends(get_db)):
    return calendario.vista(db)


@router.put("/calendar/closed-days", response_model=schemas.CalendarioResponse,
            dependencies=CONFIGURA)
def fijar_dias_cerrados(payload: schemas.DiasCerradosRequest, db: Session = Depends(get_db)):
    """Días de la semana en que la biblioteca cierra (0 = lunes … 6 = domingo)."""
    return calendario.fijar_dias_cerrados(db, payload.dias)


@router.post("/calendar/holidays", response_model=schemas.CalendarioResponse, status_code=201,
             dependencies=CONFIGURA)
def agregar_feriado(payload: schemas.FeriadoRequest, db: Session = Depends(get_db)):
    return calendario.agregar_feriado(db, payload.fecha, payload.descripcion)


@router.delete("/calendar/holidays/{feriado_id}", response_model=schemas.CalendarioResponse,
               dependencies=CONFIGURA)
def eliminar_feriado(feriado_id: int, db: Session = Depends(get_db)):
    return calendario.eliminar_feriado(db, feriado_id)
