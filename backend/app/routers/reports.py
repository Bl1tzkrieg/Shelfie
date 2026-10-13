from typing import List

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app import schemas
from app.core.permisos import Permiso
from app.core.csv import respuesta_csv
from app.core.tiempo import sello_archivo
from app.database import get_db
from app.security import requiere
from app.services import reportes

router = APIRouter(prefix="/api/v1", tags=["Reportes"],
                   dependencies=[Depends(requiere(Permiso.REPORTES))])


@router.get("/reports/stats", response_model=schemas.SystemStatsResponse)
def get_system_stats(db: Session = Depends(get_db)):
    return reportes.estadisticas(db)


@router.get("/reports/available", response_model=List[schemas.ReporteDisponible])
def listar_reportes(db: Session = Depends(get_db)):
    return reportes.disponibles(db)


@router.get("/reports/generate")
def generar_reporte(
    tipo: str = Query(..., description="loans, returns, overdue, users o catalog"),
    periodo: str = Query("month", description="week, month, quarter, year o all"),
    formato: str = Query("csv", description="csv o json"),
    db: Session = Depends(get_db),
):
    """Genera un reporte. CSV se descarga como archivo; JSON se devuelve inline."""
    reporte = reportes.generar(db, tipo, periodo, formato)

    if formato == "json":
        return {"tipo": tipo, "titulo": reporte["titulo"], "periodo": periodo,
                "filas": reporte["filas"]}

    return respuesta_csv(
        reporte["filas"],
        f"{tipo}-{periodo}-{sello_archivo()}.csv",
        texto_si_vacio="sin datos para el período seleccionado\n",
    )
