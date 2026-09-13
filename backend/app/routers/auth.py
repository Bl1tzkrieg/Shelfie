from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app import models, schemas
from app.database import get_db
from app.security import crear_token_acceso, get_current_user, hash_password, verify_password
from app.routers.users import _serializar_usuario

router = APIRouter(prefix="/api/v1/auth", tags=["Autenticación"])


@router.post("/login", response_model=schemas.LoginResponse)
def login(payload: schemas.LoginRequest, db: Session = Depends(get_db)):
    """Autenticación de intranet. Acepta username o número de carnet."""
    usuario = db.query(models.Usuario).filter(
        models.Usuario.username == payload.username).first()
    if not usuario:
        usuario = db.query(models.Usuario).filter(
            models.Usuario.nro_carnet == payload.username).first()

    # Mismo mensaje para usuario inexistente y contraseña incorrecta: no se
    # revela cuál de los dos falló.
    if not usuario or not verify_password(payload.password, usuario.password_hash):
        raise HTTPException(status_code=401, detail="Usuario o contraseña incorrectos")

    if not usuario.activo:
        raise HTTPException(status_code=403, detail="La cuenta está suspendida")

    return {
        "access_token": crear_token_acceso(usuario),
        "token_type": "bearer",
        "usuario": _serializar_usuario(db, usuario),
    }


@router.get("/me", response_model=schemas.UserResponse)
def me(
    usuario: models.Usuario = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return _serializar_usuario(db, usuario)


@router.post("/set-password")
def set_password(
    payload: schemas.LoginRequest,
    db: Session = Depends(get_db),
):
    """Asigna contraseña a una cuenta que todavía no tiene un hash válido.

    Los usuarios sembrados por seed.py guardan el literal 'pbkdf2:sha256...',
    que no es un hash utilizable. Este endpoint permite inicializarlos una sola
    vez; si la cuenta ya tiene contraseña real, se rechaza.
    """
    usuario = db.query(models.Usuario).filter(
        models.Usuario.username == payload.username).first()
    if not usuario:
        usuario = db.query(models.Usuario).filter(
            models.Usuario.nro_carnet == payload.username).first()
    if not usuario:
        raise HTTPException(status_code=404, detail="Usuario no encontrado")

    # Un hash válido tiene la forma prefijo$salt$hash; los del seed no la tienen.
    if usuario.password_hash and usuario.password_hash.count("$") == 2:
        raise HTTPException(
            status_code=400,
            detail="La cuenta ya tiene contraseña asignada")

    usuario.password_hash = hash_password(payload.password)
    db.commit()
    return {"mensaje": f"Contraseña asignada a {usuario.username}"}
