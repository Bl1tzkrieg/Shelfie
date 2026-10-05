"""Hashing de contraseñas y emisión/validación de tokens de acceso."""

import hashlib
import hmac
import os
from datetime import datetime, timedelta, timezone
from typing import Optional

import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app import models
from app.config import settings
from app.database import get_db

# --- Hashing ---------------------------------------------------------------
# Formato almacenado: pbkdf2:sha256:<iteraciones>$<salt_hex>$<hash_hex>
# Se usa pbkdf2_hmac de la librería estándar para no sumar dependencias nativas.

_ALGORITMO = "sha256"
_ITERACIONES = 260_000


def hash_password(password: str) -> str:
    salt = os.urandom(16)
    derivada = hashlib.pbkdf2_hmac(_ALGORITMO, password.encode("utf-8"), salt, _ITERACIONES)
    return f"pbkdf2:{_ALGORITMO}:{_ITERACIONES}${salt.hex()}${derivada.hex()}"


def verify_password(password: str, hash_almacenado: Optional[str]) -> bool:
    """Compara en tiempo constante. Devuelve False ante cualquier hash malformado.

    Los usuarios sembrados por seed.py tienen el literal 'pbkdf2:sha256...' como
    contraseña, que no es un hash válido: para ellos esta función siempre falla,
    que es justamente lo que queremos hasta que se les asigne una contraseña real.
    """
    if not hash_almacenado:
        return False
    try:
        prefijo, salt_hex, hash_hex = hash_almacenado.split("$")
        _, algoritmo, iteraciones = prefijo.split(":")
        derivada = hashlib.pbkdf2_hmac(
            algoritmo, password.encode("utf-8"), bytes.fromhex(salt_hex), int(iteraciones)
        )
    except (ValueError, TypeError):
        return False
    return hmac.compare_digest(derivada.hex(), hash_hex)


# --- Tokens ----------------------------------------------------------------

def crear_token_acceso(usuario: models.Usuario, horas_validez: int = 12) -> str:
    expira = datetime.now(timezone.utc) + timedelta(hours=horas_validez)
    payload = {
        "sub": str(usuario.id),
        "carnet": usuario.nro_carnet,
        "username": usuario.username,
        "exp": expira,
    }
    return jwt.encode(payload, settings.SECRET_KEY, algorithm="HS256")


_bearer = HTTPBearer(auto_error=False)


def get_current_user(
    credenciales: Optional[HTTPAuthorizationCredentials] = Depends(_bearer),
    db: Session = Depends(get_db),
) -> models.Usuario:
    """Dependencia para proteger endpoints de la intranet."""
    if credenciales is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Se requiere autenticación",
            headers={"WWW-Authenticate": "Bearer"},
        )
    try:
        payload = jwt.decode(credenciales.credentials, settings.SECRET_KEY, algorithms=["HS256"])
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="La sesión expiró, inicia sesión nuevamente")
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=401, detail="Token inválido")

    usuario = db.query(models.Usuario).filter(models.Usuario.id == int(payload["sub"])).first()
    if not usuario or not usuario.activo:
        raise HTTPException(status_code=401, detail="Usuario inexistente o inactivo")
    return usuario
