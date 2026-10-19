"""Avisos por correo y tareas programadas (Configuración → Avisos)."""

from typing import Optional

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app import schemas
from app.core.permisos import Permiso
from app.database import get_db
from app.security import requiere, requiere_personal
from app.services import avisos, tareas

CONFIGURA = requiere(Permiso.CONFIGURACION)

router = APIRouter(prefix="/api/v1/notices", tags=["Avisos y tareas"],
                   dependencies=[Depends(requiere_personal)])


@router.get("")
def resumen(db: Session = Depends(get_db)):
    """Cuántos avisos hay en cada estado, cómo sale el correo y si las tareas son automáticas."""
    return {**avisos.resumen(db), "tareas": tareas.automaticas(), "ajustes": tareas.ajustes(db)}


@router.get("/queue")
def cola(estado: Optional[str] = None, carnet: Optional[str] = None,
         db: Session = Depends(get_db)):
    """Últimos avisos (todos, o de un lector con `carnet`)."""
    return avisos.listar(db, estado, carnet)


@router.post("/queue/send", dependencies=[Depends(CONFIGURA)])
def enviar_cola(db: Session = Depends(get_db)):
    return tareas.ejecutar(db, "enviar_cola", origen="manual")


@router.post("/queue/{aviso_id}/retry", dependencies=[Depends(CONFIGURA)])
def reintentar(aviso_id: int, db: Session = Depends(get_db)):
    return avisos.reintentar(db, aviso_id)


@router.post("/test", dependencies=[Depends(CONFIGURA)])
def probar_correo(payload: schemas.CorreoPruebaRequest, db: Session = Depends(get_db)):
    return avisos.prueba(db, payload.destinatario)


@router.get("/templates")
def plantillas(db: Session = Depends(get_db)):
    return avisos.plantillas(db)


@router.put("/templates/{codigo}", dependencies=[Depends(CONFIGURA)])
def guardar_plantilla(codigo: str, payload: schemas.PlantillaAvisoRequest,
                      db: Session = Depends(get_db)):
    return avisos.guardar_plantilla(db, codigo, payload.model_dump())


@router.post("/templates/{codigo}/preview")
def vista_previa(codigo: str, payload: schemas.VistaPreviaAvisoRequest,
                 db: Session = Depends(get_db)):
    """Cómo se vería con datos de ejemplo (lo enviado, o lo guardado si no se envía nada)."""
    return avisos.ejemplo(db, codigo, payload.asunto, payload.cuerpo)


@router.get("/settings")
def ajustes(db: Session = Depends(get_db)):
    return tareas.ajustes(db)


@router.put("/settings", dependencies=[Depends(CONFIGURA)])
def guardar_ajustes(payload: schemas.AjustesAvisosRequest, db: Session = Depends(get_db)):
    return tareas.guardar_ajustes(db, payload.model_dump(exclude_unset=True))


@router.get("/tasks")
def listar_tareas(db: Session = Depends(get_db)):
    return {"tareas": tareas.listar(db), "automaticas": tareas.automaticas()}


@router.get("/tasks/history")
def historial(db: Session = Depends(get_db)):
    return tareas.historial(db)


@router.post("/tasks/{nombre}/run", dependencies=[Depends(CONFIGURA)])
def ejecutar_tarea(nombre: str, db: Session = Depends(get_db)):
    return tareas.ejecutar(db, nombre, origen="manual")
