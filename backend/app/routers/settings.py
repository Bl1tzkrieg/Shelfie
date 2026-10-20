from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session

from app import models, schemas
from app.core.permisos import Permiso, tiene
from app.database import get_db
from app.security import _usuario_del_token, requiere, requiere_personal
from app.services import configuracion, respaldo

router = APIRouter(prefix="/api/v1/settings", tags=["Configuración"])


def usuario_opcional(request: Request, db: Session = Depends(get_db)) -> Optional[models.Usuario]:
    """El personal con sesión válida, o None: sirve a los endpoints que también son públicos."""
    try:
        return _usuario_del_token(request, db)
    except HTTPException:
        return None


def _segun_quien_pregunta(db: Session, usuario: Optional[models.Usuario]) -> dict:
    """Sin sesión solo el nombre de la biblioteca (el encabezado público); el personal ve la
    biblioteca completa; el respaldo, solo quien puede editarlo (el administrador)."""
    todo = configuracion.leer_todo(db)
    if usuario is None:
        return {"biblioteca": {"nombre": todo["biblioteca"]["nombre"]}}
    if tiene(usuario.permisos, Permiso.SUPERBIBLIOTECARIO):
        return todo
    return {"biblioteca": todo["biblioteca"]}


@router.get("", response_model=schemas.ConfiguracionResponse, response_model_exclude_unset=True)
def get_settings(usuario: Optional[models.Usuario] = Depends(usuario_opcional),
                 db: Session = Depends(get_db)):
    return _segun_quien_pregunta(db, usuario)


@router.put("", response_model=schemas.ConfiguracionResponse, response_model_exclude_unset=True)
def update_settings(payload: schemas.ActualizarConfiguracionRequest,
                    usuario: models.Usuario = Depends(requiere(Permiso.SUPERBIBLIOTECARIO)),
                    db: Session = Depends(get_db)):
    """Guarda solo las secciones enviadas; las omitidas quedan intactas."""
    biblioteca = (payload.biblioteca.model_dump(exclude_none=True) or None
                  if payload.biblioteca else None)
    respaldo = None
    if payload.respaldo:
        # Un texto vacío borra el valor; lo omitido no cambia.
        respaldo = {k: (v.strip() or None)
                    for k, v in payload.respaldo.model_dump(exclude_unset=True).items()
                    if v is not None} or None
    configuracion.guardar(db, {"biblioteca": biblioteca, "respaldo": respaldo})
    return _segun_quien_pregunta(db, usuario)


@router.get("/system-info", dependencies=[Depends(requiere_personal)])
def system_info(db: Session = Depends(get_db)):
    """Totales reales del catálogo para la tarjeta «Sistema» de la pantalla de ajustes."""
    return configuracion.info_sistema(db)


@router.get("/backup")
def estado_del_respaldo(usuario: models.Usuario = Depends(requiere(Permiso.SUPERBIBLIOTECARIO)),
                        db: Session = Depends(get_db)):
    """Último resultado y si hay que avisar (más de 7 días, o el último falló)."""
    return respaldo.estado(db)


@router.post("/backup")
def respaldar_ahora(usuario: models.Usuario = Depends(requiere(Permiso.SUPERBIBLIOTECARIO)),
                    db: Session = Depends(get_db)):
    """Hace el respaldo ya. Un fallo (pendrive desconectado, sin pg_dump) no es un error de
    la API: responde 200 con `ok: false` y el motivo."""
    return {**respaldo.ejecutar(db), "estado": respaldo.estado(db)}
