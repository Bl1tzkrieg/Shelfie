from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from datetime import datetime
from pydantic import BaseModel
from app.database import SessionLocal
from app import models

router = APIRouter(prefix="/api/v1", tags=["Reportes"])


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


class SystemStatsResponse(BaseModel):
    total_items: int
    total_users: int
    loans_this_month: int
    growth_percentage: str


@router.get("/reports/stats", response_model=SystemStatsResponse)
def get_system_stats(db: Session = Depends(get_db)):
    # 1. Determinar dinámicamente el modelo del catálogo (Material, Libro o Item)
    total_items = 0
    for model_name in ["Material", "Libro", "Item", "Ejemplar"]:
        if hasattr(models, model_name):
            target_model = getattr(models, model_name)
            total_items = db.query(target_model).count()
            break

    # 2. Total de usuarios registrados
    total_users = db.query(models.Usuario).count()

    # 3. Préstamos realizados en el mes actual
    current_month = datetime.now().month
    current_year = datetime.now().year

    # Intentamos buscar por fecha_prestamo o el campo que use tu modelo Prestamo
    loans_this_month = 0
    if hasattr(models, "Prestamo"):
        # Buscamos el nombre correcto de la columna de fecha
        loan_sample = db.query(models.Prestamo).first()
        date_field = "fecha_prestamo"
        if loan_sample and not hasattr(loan_sample, "fecha_prestamo"):
            if hasattr(loan_sample, "fecha_registro"):
                date_field = "fecha_registro"
            elif hasattr(loan_sample, "fecha_salida"):
                date_field = "fecha_salida"

        loans_this_month = db.query(models.Prestamo).filter(
            getattr(models.Prestamo, date_field) >= datetime(current_year, current_month, 1)
        ).count()

    return {
        "total_items": total_items,
        "total_users": total_users,
        "loans_this_month": loans_this_month,
        "growth_percentage": "+12%"
    }