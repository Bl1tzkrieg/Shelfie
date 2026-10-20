"""Inventario: pasadas por sede y tramo de signaturas (Inventory de Koha)."""

from typing import List, Optional

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app import models
from app.core.csv import respuesta_csv
from app.core.permisos import Permiso
from app.core.tiempo import sello_archivo
from app.database import get_db
from app.security import requiere, requiere_personal, sede_de_trabajo
from app.services import inventario

router = APIRouter(prefix="/api/v1/inventories", tags=["Inventario"],
                   dependencies=[Depends(requiere_personal)])

CATALOGA = requiere(Permiso.CATALOGO)


class NuevoInventarioRequest(BaseModel):
    nombre: Optional[str] = Field(default=None, max_length=120)
    biblioteca_id: Optional[int] = None
    tipo_item_codigo: Optional[str] = None
    signatura_desde: Optional[str] = Field(default=None, max_length=100)
    signatura_hasta: Optional[str] = Field(default=None, max_length=100)
    devolver_prestados: bool = False


class LecturaRequest(BaseModel):
    codigos: List[str] = Field(min_length=1)


@router.get("")
def listar(db: Session = Depends(get_db)):
    return inventario.listar(db)


@router.post("", status_code=201)
def crear(payload: NuevoInventarioRequest, db: Session = Depends(get_db),
          actor: models.Usuario = Depends(CATALOGA)):
    return inventario.crear(db, payload.model_dump(), actor.id)


@router.get("/{inventario_id}")
def obtener(inventario_id: int, resultado: Optional[str] = None, db: Session = Depends(get_db)):
    """Resumen, faltantes y las últimas lecturas (o las de un resultado, p. ej. fuera_de_lugar)."""
    return inventario.obtener(db, inventario_id, resultado)


@router.post("/{inventario_id}/scan")
def leer(inventario_id: int, payload: LecturaRequest, db: Session = Depends(get_db),
         actor: models.Usuario = Depends(CATALOGA),
         sede: Optional[int] = Depends(sede_de_trabajo)):
    """Uno o varios códigos (escáner, pegados o de un archivo)."""
    return inventario.leer(db, inventario_id, payload.codigos, actor.id, sede)


@router.post("/{inventario_id}/close")
def cerrar(inventario_id: int, db: Session = Depends(get_db),
           _actor: models.Usuario = Depends(CATALOGA)):
    return inventario.cerrar(db, inventario_id)


@router.get("/{inventario_id}/missing.csv")
def exportar_faltantes(inventario_id: int, db: Session = Depends(get_db)):
    return respuesta_csv(inventario.faltantes(db, inventario_id),
                         f"faltantes-{inventario_id}-{sello_archivo()}.csv",
                         columnas=inventario.COLUMNAS_FALTANTES,
                         texto_si_vacio="no faltó nada\n")
