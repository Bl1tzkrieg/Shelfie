"""Hashing de contraseñas, sesión por cookie y control de permisos."""

import hashlib
import hmac
import os
import secrets
from urllib.parse import urlsplit
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
_METODOS_SEGUROS = {"GET", "HEAD", "OPTIONS"}


def huella_de_clave(usuario: models.Usuario) -> str:
    """Un pedazo del hash actual: si la contraseña cambia, las sesiones viejas dejan de valer."""
    return hashlib.sha256((usuario.password_hash or "").encode()).hexdigest()[:12]


def crear_token_acceso(usuario: models.Usuario) -> str:
    expira = datetime.now(timezone.utc) + timedelta(hours=settings.SESION_HORAS)
    # Sin el username: el token solo identifica al usuario por su id.
    # jti: identifica este token para poder anularlo al cerrar la sesión.
    payload = {"sub": str(usuario.id), "exp": expira, "clave": huella_de_clave(usuario),
               "jti": secrets.token_hex(16)}
    return jwt.encode(payload, settings.SECRET_KEY, algorithm="HS256")


def _poner_cookie(response: Response, nombre: str, token: str) -> None:
    response.set_cookie(nombre, token, max_age=settings.SESION_HORAS * 3600, httponly=True,
                        secure=settings.COOKIE_SECURE, samesite="lax", path="/")


def _borrar_cookie(response: Response, nombre: str) -> None:
    response.delete_cookie(nombre, path="/", httponly=True, secure=settings.COOKIE_SECURE,
                           samesite="lax")


def abrir_sesion(response: Response, usuario: models.Usuario) -> None:
    _poner_cookie(response, COOKIE_SESION, crear_token_acceso(usuario))


def _anular_token(request: Optional[Request], db: Optional[Session]) -> None:
    """Guarda el jti del token de la cookie: aunque alguien lo haya copiado, ya no sirve."""
    token = request.cookies.get(COOKIE_SESION) if request is not None else None
    if not token or db is None:
        return
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=["HS256"])
    except jwt.InvalidTokenError:
        return  # vencido o inválido: ya no vale
    if payload.get("jti") and not db.get(models.SesionCerrada, payload["jti"]):
        db.add(models.SesionCerrada(jti=payload["jti"],
                                    expira=datetime.fromtimestamp(payload["exp"], timezone.utc)))
        from app.services import registro
        usuario = db.get(models.Usuario, int(payload["sub"]))
        db.info["ip"] = ip_de(request)
        registro.anotar(db, "sesion", "salida", f"Salió de la intranet: {registro.nombre(usuario)}",
                        actor=usuario, lector=usuario)
        db.commit()


def cerrar_sesion(response: Response, request: Optional[Request] = None,
                  db: Optional[Session] = None) -> None:
    _anular_token(request, db)
    _borrar_cookie(response, COOKIE_SESION)


def verificar_origen(request: Request) -> None:
    """Defensa CSRF: una escritura con cookie solo se acepta desde orígenes conocidos.

    SameSite=Lax ya impide que otro sitio envíe la cookie en un POST; esto cubre
    además subdominios hermanos y navegadores antiguos. Sin Origin se mira el Referer
    (algunos navegadores viejos solo mandan ese); sin ninguno de los dos (scripts,
    curl, tests) la petición no viene de un navegador ajeno.
    """
    if request.method in _METODOS_SEGUROS:
        return
    origen = request.headers.get("origin")
    if not origen:
        referer = request.headers.get("referer")
        if not referer:
            return
        partes = urlsplit(referer)
        origen = f"{partes.scheme}://{partes.netloc}"
    propio = str(request.base_url).rstrip("/")
    if origen != propio and origen not in settings.cors_origins_list:
        raise HTTPException(status_code=403, detail="Origen no autorizado")


def ip_de(request: Optional[Request]) -> Optional[str]:
    return request.client.host if request is not None and request.client else None


def marcar_actor(db: Session, request: Optional[Request], usuario: Optional[models.Usuario]) -> None:
    """Deja en la sesión de base de datos quién actúa (lo lee app/services/registro.py)."""
    db.info["actor_id"] = usuario.id if usuario else None
    db.info["ip"] = ip_de(request)


def _usuario_del_token(request: Request, db: Session) -> models.Usuario:
    token = request.cookies.get(COOKIE_SESION)
    if not token:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED,
                            detail="Se requiere iniciar sesión")
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=["HS256"])
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="La sesión expiró, inicia sesión nuevamente")
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=401, detail="Sesión inválida, inicia sesión nuevamente")

    verificar_origen(request)

    if payload.get("jti") and db.get(models.SesionCerrada, payload["jti"]):
        raise HTTPException(status_code=401, detail="La sesión se cerró, inicia sesión nuevamente")
    usuario = db.get(models.Usuario, int(payload["sub"]))
    if not usuario or not usuario.activo:
        raise HTTPException(status_code=401, detail="Usuario inexistente o suspendido")
    if payload.get("clave") != huella_de_clave(usuario):
        raise HTTPException(status_code=401,
                            detail="La contraseña cambió: inicia sesión nuevamente")
    # Para el registro de acciones: quién actúa en esta petición y desde dónde.
    marcar_actor(db, request, usuario)
    if usuario.debe_cambiar_clave and request.url.path not in _SIN_CAMBIO_DE_CLAVE:
        from app.services.autenticacion import tiene_que_cambiar_clave
        if tiene_que_cambiar_clave(db, usuario):
            raise HTTPException(status_code=403, detail=CAMBIO_DE_CLAVE_PENDIENTE)
    return usuario


# Con una contraseña que no eligió el usuario solo se puede ver quién es, cambiarla o salir.
CAMBIO_DE_CLAVE_PENDIENTE = "Tienes que elegir una contraseña nueva antes de seguir"
_SIN_CAMBIO_DE_CLAVE = {
    "/api/v1/auth/me", "/api/v1/auth/password", "/api/v1/auth/logout",
}


def get_current_user(request: Request, db: Session = Depends(get_db)) -> models.Usuario:
    """Usuario autenticado por la cookie de sesión de la intranet."""
    return _usuario_del_token(request, db)


def requiere_personal(usuario: models.Usuario = Depends(get_current_user)) -> models.Usuario:
    """Cualquier miembro del personal con sesión: basta para consultar la intranet."""
    return usuario


def requiere(permiso: Permiso):
    """Dependencia que exige un permiso de módulo (o superbibliotecario)."""

    def _verificar(usuario: models.Usuario = Depends(requiere_personal)) -> models.Usuario:
        if not tiene(usuario.permisos, permiso):
            raise HTTPException(
                status_code=403, detail=f"No tienes el permiso '{permiso.value}' para esta acción")
        return usuario

    return _verificar
