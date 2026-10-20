from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app import schemas
from app.core.permisos import Permiso
from app.database import get_db
from app.security import requiere, requiere_personal
from app.services import configuracion

router = APIRouter(prefix="/api/v1/settings", tags=["Configuración"],
                   dependencies=[Depends(requiere_personal)])


@router.get("", response_model=schemas.ConfiguracionResponse)
def get_settings(db: Session = Depends(get_db)):
    return configuracion.leer_todo(db)


@router.put("", response_model=schemas.ConfiguracionResponse,
            dependencies=[Depends(requiere(Permiso.SUPERBIBLIOTECARIO))])
def update_settings(payload: schemas.ActualizarConfiguracionRequest,
                    db: Session = Depends(get_db)):
    """Guarda solo las secciones enviadas; las omitidas quedan intactas."""
    return configuracion.guardar(db, {
        "institucion": payload.institucion,
        "notificaciones": payload.notificaciones,
        "circulacion": (payload.circulacion.model_dump(exclude_none=True) or None
                        if payload.circulacion else None),
    })


@router.get("/system-info")
def system_info(db: Session = Depends(get_db)):
    """Datos técnicos reales para la tarjeta 'Sistema' de la pantalla de ajustes."""
    return configuracion.info_sistema(db)
