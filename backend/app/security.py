"""Hashing de contraseñas, sesión por cookie y control de permisos."""

import hashlib
import hmac
import os
from datetime import datetime, timedelta, timezone
from typing import Optional

import jwt
from fastapi import Depends, HTTPException, Request, Response, status
from sqlalchemy.orm import Session

from app import models
from app.config import settings
from app.core.permisos import Permiso, tiene
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
    """Compara en tiempo constante. Devuelve False ante cualquier hash malformado."""
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


# --- Sesión ----------------------------------------------------------------
# El token viaja en una cookie httpOnly: el JavaScript de la página no puede
# leerlo, así que un script inyectado no puede robar la sesión.

COOKIE_SESION = "shelfie_sesion"
# La sesión del OPAC va aparte: un lector (o alguien del personal consultando su propia
# cuenta) entra al catálogo público sin abrir la intranet, y viceversa.
COOKIE_OPAC = "shelfie_opac"
AUDIENCIA_OPAC = "opac"
_METODOS_SEGUROS = {"GET", "HEAD", "OPTIONS"}


def huella_de_clave(usuario: models.Usuario) -> str:
    """Un pedazo del hash actual: si la contraseña cambia, las sesiones viejas dejan de valer."""
    return hashlib.sha256((usuario.password_hash or "").encode()).hexdigest()[:12]


def crear_token_acceso(usuario: models.Usuario, audiencia: Optional[str] = None) -> str:
    expira = datetime.now(timezone.utc) + timedelta(hours=settings.SESION_HORAS)
    payload = {"sub": str(usuario.id), "carnet": usuario.nro_carnet, "exp": expira,
               "clave": huella_de_clave(usuario)}
    if audiencia:
        payload["aud"] = audiencia
    return jwt.encode(payload, settings.SECRET_KEY, algorithm="HS256")


def _poner_cookie(response: Response, nombre: str, token: str) -> None:
    response.set_cookie(nombre, token, max_age=settings.SESION_HORAS * 3600, httponly=True,
                        secure=settings.COOKIE_SECURE, samesite="lax", path="/")


def _borrar_cookie(response: Response, nombre: str) -> None:
    response.delete_cookie(nombre, path="/", httponly=True, secure=settings.COOKIE_SECURE,
                           samesite="lax")


def abrir_sesion(response: Response, usuario: models.Usuario) -> None:
    _poner_cookie(response, COOKIE_SESION, crear_token_acceso(usuario))


def cerrar_sesion(response: Response) -> None:
    _borrar_cookie(response, COOKIE_SESION)


def abrir_sesion_opac(response: Response, usuario: models.Usuario) -> None:
    _poner_cookie(response, COOKIE_OPAC, crear_token_acceso(usuario, AUDIENCIA_OPAC))


def cerrar_sesion_opac(response: Response) -> None:
    _borrar_cookie(response, COOKIE_OPAC)


def verificar_origen(request: Request) -> None:
    """Defensa CSRF: una escritura con cookie solo se acepta desde orígenes conocidos.

    SameSite=Lax ya impide que otro sitio envíe la cookie en un POST; esto cubre
    además subdominios hermanos y navegadores antiguos. Las peticiones sin
    cabecera Origin (scripts, curl, tests) no vienen de un navegador ajeno.
    """
    if request.method in _METODOS_SEGUROS:
        return
    origen = request.headers.get("origin")
    if not origen:
        return
    propio = str(request.base_url).rstrip("/")
    if origen != propio and origen not in settings.cors_origins_list:
        raise HTTPException(status_code=403, detail="Origen no autorizado")


def _usuario_del_token(request: Request, db: Session, cookie: str,
                       audiencia: Optional[str]) -> models.Usuario:
    token = request.cookies.get(cookie)
    if not token:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED,
                            detail="Se requiere iniciar sesión")
    try:
        # Un token del OPAC trae audiencia y uno de la intranet no: ninguno sirve en el otro lado.
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=["HS256"],
                             audience=audiencia)
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="La sesión expiró, inicia sesión nuevamente")
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=401, detail="Sesión inválida, inicia sesión nuevamente")

    verificar_origen(request)

    usuario = db.get(models.Usuario, int(payload["sub"]))
    if not usuario or not usuario.activo:
        raise HTTPException(status_code=401, detail="Usuario inexistente o suspendido")
    if payload.get("clave") != huella_de_clave(usuario):
        raise HTTPException(status_code=401,
                            detail="La contraseña cambió: inicia sesión nuevamente")
    return usuario


def get_current_user(request: Request, db: Session = Depends(get_db)) -> models.Usuario:
    """Usuario autenticado por la cookie de sesión de la intranet."""
    return _usuario_del_token(request, db, COOKIE_SESION, None)


def get_lector(request: Request, db: Session = Depends(get_db)) -> models.Usuario:
    """Lector autenticado en el OPAC (su propia cuenta; cualquier usuario activo)."""
    return _usuario_del_token(request, db, COOKIE_OPAC, AUDIENCIA_OPAC)


def requiere_personal(usuario: models.Usuario = Depends(get_current_user)) -> models.Usuario:
    """Cualquier miembro del personal: basta para consultar la intranet."""
    if not usuario.es_personal:
        raise HTTPException(status_code=403, detail="Esta cuenta no tiene acceso a la intranet")
    return usuario


def requiere(permiso: Permiso):
    """Dependencia que exige un permiso de módulo (o superbibliotecario)."""

    def _verificar(usuario: models.Usuario = Depends(requiere_personal)) -> models.Usuario:
        if not tiene(usuario.permisos, permiso):
            raise HTTPException(
                status_code=403, detail=f"No tienes el permiso '{permiso.value}' para esta acción")
        return usuario

    return _verificar


def sede_de_trabajo(request: Request, usuario: models.Usuario = Depends(requiere_personal),
                    db: Session = Depends(get_db)) -> Optional[int]:
    """Sede donde opera el personal (cabecera X-Shelfie-Sede; ver app/services/sedes.py)."""
    from app.services import sedes
    return sedes.de_trabajo(db, usuario, request.headers.get(sedes.CABECERA))
