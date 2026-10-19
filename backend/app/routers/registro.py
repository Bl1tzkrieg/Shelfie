"""Registro de acciones: consulta, exportación y qué se registra (action_logs de Koha)."""

from datetime import date
from typing import Dict, Optional

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.core.csv import respuesta_csv
from app.core.permisos import Permiso
from app.core.tiempo import sello_archivo
from app.database import get_db
from app.security import requiere
from app.services import registro

router = APIRouter(prefix="/api/v1/logs", tags=["Registro de acciones"])

CONSULTA = [Depends(requiere(Permiso.REGISTRO))]


def _filtros(modulo: Optional[str] = None, accion: Optional[str] = None,
             actor: Optional[str] = Query(None, description="Carnet o usuario de quien actuó; «sistema»"),
             lector: Optional[str] = Query(None, description="Carnet del lector afectado"),
             biblio_id: Optional[int] = None,
             codigo: Optional[str] = Query(None, description="Código de barras del ejemplar"),
             desde: Optional[date] = None, hasta: Optional[date] = None,
             q: Optional[str] = Query(None, description="Texto en la descripción")) -> dict:
    return {"modulo": modulo, "accion": accion, "actor": actor, "lector": lector,
            "biblio_id": biblio_id, "codigo": codigo, "desde": desde, "hasta": hasta, "q": q}


@router.get("", dependencies=CONSULTA)
def consultar(filtros: dict = Depends(_filtros), pagina: int = Query(1, ge=1),
              por_pagina: int = Query(50, ge=1, le=200), db: Session = Depends(get_db)):
    """Del más reciente al más viejo."""
    return registro.consultar(db, filtros, pagina, por_pagina)


@router.get("/export", dependencies=CONSULTA)
def exportar(filtros: dict = Depends(_filtros), db: Session = Depends(get_db)):
    return respuesta_csv(registro.exportar(db, filtros), f"registro-{sello_archivo()}.csv",
                         columnas=registro.COLUMNAS_EXPORTACION,
                         texto_si_vacio="sin acciones para esos filtros\n")


@router.get("/settings", dependencies=CONSULTA)
def ajustes(db: Session = Depends(get_db)):
    """Qué módulos se registran, cuánto se guarda y los nombres para la pantalla."""
    return {**registro.ajustes(db), "descripciones": registro.MODULOS,
            "acciones": registro.NOMBRE_ACCION}


class AjustesRegistroRequest(BaseModel):
    modulos: Optional[Dict[str, bool]] = None
    dias_retencion: Optional[int] = Field(default=None, ge=0, le=36500)


@router.put("/settings", dependencies=[Depends(requiere(Permiso.CONFIGURACION))])
def guardar_ajustes(payload: AjustesRegistroRequest, db: Session = Depends(get_db)):
    registro.guardar_ajustes(db, payload.model_dump(exclude_none=True))
    return {**registro.ajustes(db), "descripciones": registro.MODULOS,
            "acciones": registro.NOMBRE_ACCION}
