from fastapi import APIRouter, Depends, Request, Response
from sqlalchemy.orm import Session

from app import models, schemas
from app.database import get_db
from app.security import abrir_sesion, cerrar_sesion, get_current_user, verificar_origen
from app.services import autenticacion, usuarios

router = APIRouter(prefix="/api/v1/auth", tags=["Autenticación"])


@router.post("/login", response_model=schemas.LoginResponse)
def login(payload: schemas.LoginRequest, request: Request, response: Response,
          db: Session = Depends(get_db)):
    """Inicia sesión en la intranet (username o carnet). Deja la sesión en una cookie httpOnly."""
    verificar_origen(request)
    usuario = autenticacion.autenticar_personal(db, payload.username, payload.password,
                                                 request.client.host if request.client else None)
    abrir_sesion(response, usuario)
    return {"usuario": usuarios.vista_de_usuario(db, usuario)}


@router.post("/logout", status_code=204)
def logout(response: Response, request: Request, db: Session = Depends(get_db)):
    cerrar_sesion(response, request, db)


@router.get("/me", response_model=schemas.UserResponse)
def me(usuario: models.Usuario = Depends(get_current_user), db: Session = Depends(get_db)):
    return usuarios.vista_de_usuario(db, usuario)


@router.post("/password", status_code=204)
def cambiar_clave(payload: schemas.CambiarClaveRequest, response: Response,
                  usuario: models.Usuario = Depends(get_current_user),
                  db: Session = Depends(get_db)):
    """Cambia la propia contraseña. Las otras sesiones abiertas se cierran; esta sigue."""
    autenticacion.cambiar_clave(db, usuario, payload.actual, payload.nueva)
    abrir_sesion(response, usuario)
