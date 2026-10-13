from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app import schemas
from app.core.permisos import Permiso
from app.database import get_db
from app.security import requiere, requiere_personal
from app.services import configuracion, sedes

router = APIRouter(prefix="/api/v1/settings", tags=["Configuración"],
                   dependencies=[Depends(requiere_personal)])


@router.get("", response_model=schemas.ConfiguracionResponse)
def get_settings(db: Session = Depends(get_db)):
    return configuracion.leer_todo(db)


@router.put("", response_model=schemas.ConfiguracionResponse,
            dependencies=[Depends(requiere(Permiso.CONFIGURACION))])
def update_settings(payload: schemas.ActualizarConfiguracionRequest,
                    db: Session = Depends(get_db)):
    """Guarda solo las secciones enviadas; las omitidas quedan intactas."""
    return configuracion.guardar(db, {
        "institucion": payload.institucion,
        "politicas_prestamo": payload.politicas_prestamo,
        "notificaciones": payload.notificaciones,
        "circulacion": (payload.circulacion.model_dump(exclude_none=True) or None
                        if payload.circulacion else None),
    })


@router.get("/system-info")
def system_info(db: Session = Depends(get_db)):
    """Datos técnicos reales para la tarjeta 'Sistema' de la pantalla de ajustes."""
    return configuracion.info_sistema(db)


# --- Sedes ----------------------------------------------------------------------------

@router.get("/branches")
def listar_sedes(con_uso: bool = False, db: Session = Depends(get_db)):
    """Sedes de la biblioteca. `con_uso` agrega cuántos ejemplares y lectores tiene cada una."""
    return sedes.listar(db, con_uso=con_uso)


@router.post("/branches", status_code=201, dependencies=[Depends(requiere(Permiso.CONFIGURACION))])
def crear_sede(payload: schemas.SedeRequest, db: Session = Depends(get_db)):
    return sedes.crear(db, payload.model_dump(exclude_unset=True))


@router.put("/branches/{sede_id}", dependencies=[Depends(requiere(Permiso.CONFIGURACION))])
def actualizar_sede(sede_id: int, payload: schemas.SedeRequest, db: Session = Depends(get_db)):
    return sedes.actualizar(db, sede_id, payload.model_dump(exclude_unset=True))


@router.delete("/branches/{sede_id}", dependencies=[Depends(requiere(Permiso.CONFIGURACION))])
def eliminar_sede(sede_id: int, db: Session = Depends(get_db)):
    sedes.eliminar(db, sede_id)
    return {"mensaje": "Sede eliminada"}
