"""Login de la intranet y del OPAC, y cambio de contraseña."""

from typing import Optional

from sqlalchemy.orm import Session

from app import models
from app.core.errores import (AccesoDenegado, CredencialesInvalidas, DemasiadosIntentos,
                              ReglaIncumplida)
from app.security import hash_password, verify_password
from app.services import usuarios


# --- Entrar ------------------------------------------------------------------------------
#
# Mismo mensaje para usuario inexistente y contraseña incorrecta, y el mismo trabajo en
# ambos casos (se verifica contra un hash de relleno), para no revelar qué carnets
# existen. Tras varios fallos seguidos con el mismo carnet (o desde la misma IP) hay que
# esperar unos minutos (FailedLoginAttempts de Koha, pero temporal).

_HASH_DE_RELLENO = hash_password("shelfie-relleno-para-igualar-tiempos")


def _seguridad(db: Session) -> dict:
    from app.services import configuracion
    return configuracion.leer(db, "seguridad")


def _frenar_si_insiste(db: Session, identificador: str, ip: Optional[str]) -> None:
    from datetime import timedelta

    from app.core.tiempo import ahora

    ajustes = _seguridad(db)
    maximo, minutos = int(ajustes["max_intentos"]), int(ajustes["minutos_bloqueo"])
    if maximo <= 0:
        return
    I = models.IntentoAcceso
    desde = ahora() - timedelta(minutes=minutos)
    por_carnet = db.query(I).filter(I.identificador == identificador, I.fecha > desde).count()
    por_ip = db.query(I).filter(I.ip == ip, I.fecha > desde).count() if ip else 0
    if por_carnet >= maximo or por_ip >= maximo * 6:
        raise DemasiadosIntentos(
            f"Demasiados intentos fallidos. Espera {minutos} minutos y vuelve a intentarlo")


def _verificar(db: Session, identificador: str, password: str, ip: Optional[str],
               mensaje: str) -> models.Usuario:
    from app.core.tiempo import ahora

    clave = (identificador or "").strip().lower()[:100]
    _frenar_si_insiste(db, clave, ip)
    usuario = usuarios.buscar_por_identificador(db, (identificador or "").strip())
    valida = verify_password(password, usuario.password_hash if usuario else _HASH_DE_RELLENO)
    if not usuario or not valida:
        db.add(models.IntentoAcceso(identificador=clave, ip=ip, fecha=ahora()))
        db.commit()
        raise CredencialesInvalidas(mensaje)
    db.query(models.IntentoAcceso).filter(models.IntentoAcceso.identificador == clave).delete(
        synchronize_session=False)
    # Entrar con el carnet (o el usuario) como contraseña obliga a elegir una propia.
    if _seguridad(db)["forzar_cambio_clave"] and password.strip().lower() in {
            usuario.nro_carnet.lower(), (usuario.username or "").lower()}:
        usuario.debe_cambiar_clave = True
    db.commit()
    return usuario


def autenticar_personal(db: Session, identificador: str, password: str,
                        ip: Optional[str] = None):
    """Devuelve el usuario si las credenciales son válidas y tiene acceso a la intranet."""
    usuario = _verificar(db, identificador, password, ip, "Usuario o contraseña incorrectos")
    if not usuario.activo:
        raise AccesoDenegado("La cuenta está suspendida")
    if not usuario.es_personal:
        raise AccesoDenegado("Esta cuenta no tiene acceso a la intranet")
    return usuario


def autenticar_lector(db: Session, identificador: str, password: str,
                      ip: Optional[str] = None):
    """Login del OPAC: cualquier usuario activo entra a su propia cuenta."""
    usuario = _verificar(db, identificador, password, ip, "Carnet o contraseña incorrectos")
    if not usuario.activo:
        raise AccesoDenegado("Tu cuenta está suspendida: consulta en la biblioteca")
    return usuario


def tiene_que_cambiar_clave(db: Session, usuario: models.Usuario) -> bool:
    return bool(usuario.debe_cambiar_clave) and bool(_seguridad(db)["forzar_cambio_clave"])


MINIMO_CLAVE = 8


def validar_clave_nueva(usuario: models.Usuario, nueva: str) -> None:
    if len(nueva or "") < MINIMO_CLAVE:
        raise ReglaIncumplida(f"La contraseña nueva necesita al menos {MINIMO_CLAVE} caracteres")
    if nueva.strip().lower() in {usuario.nro_carnet.lower(), (usuario.username or "").lower()}:
        raise ReglaIncumplida("La contraseña no puede ser el carnet ni el nombre de usuario")


def cambiar_clave(db: Session, usuario: models.Usuario, actual: str, nueva: str) -> None:
    """Cambio de la propia contraseña: exige la actual. Cierra las demás sesiones."""
    if not verify_password(actual, usuario.password_hash):
        # 400 y no 401: la sesión sigue siendo válida, solo se equivocó de contraseña.
        raise ReglaIncumplida("La contraseña actual no es correcta")
    if actual == nueva:
        raise ReglaIncumplida("La contraseña nueva debe ser distinta de la actual")
    validar_clave_nueva(usuario, nueva)
    usuario.password_hash = hash_password(nueva)
    usuario.debe_cambiar_clave = False
    db.commit()


def restablecer_clave(db: Session, actor: models.Usuario, usuario: models.Usuario,
                      nueva: str) -> None:
    """Restablecimiento por el personal. La de otro miembro del personal, solo un superbibliotecario."""
    from app.core.permisos import Permiso, tiene
    if usuario.es_personal and not tiene(actor.permisos, Permiso.SUPERBIBLIOTECARIO):
        raise AccesoDenegado(
            "Solo un superbibliotecario puede restablecer la contraseña de otro miembro del personal")
    if usuario.id == actor.id:
        raise ReglaIncumplida("Para tu propia contraseña usa «Cambiar contraseña»")
    validar_clave_nueva(usuario, nueva)
    usuario.password_hash = hash_password(nueva)
    usuario.debe_cambiar_clave = True
    db.commit()


# --- Recuperar la contraseña por correo ------------------------------------------------------

MINUTOS_ENLACE = 60
MAX_ENLACES_POR_HORA = 3


def _hash_token(token: str) -> str:
    import hashlib
    return hashlib.sha256(token.encode()).hexdigest()


def solicitar_recuperacion(db: Session, identificador: str) -> None:
    """Manda un enlace de un solo uso al correo del lector.

    No dice si el carnet existe: quien pide para otro no se entera de nada. Tampoco
    manda más de MAX_ENLACES_POR_HORA, para que no se use para llenarle el buzón a alguien.
    """
    import secrets
    from datetime import timedelta

    from app.config import settings
    from app.core.tiempo import ahora
    from app.services import avisos

    usuario = usuarios.buscar_por_identificador(db, (identificador or "").strip())
    if not usuario or not usuario.activo or not usuario.email:
        return
    T = models.TokenClave
    hace_una_hora = ahora() - timedelta(hours=1)
    if db.query(T).filter(T.usuario_id == usuario.id,
                          T.fecha_creacion > hace_una_hora).count() >= MAX_ENLACES_POR_HORA:
        return
    # Un enlace nuevo anula los anteriores sin usar.
    db.query(T).filter(T.usuario_id == usuario.id, T.usado == None).update(  # noqa: E711
        {"usado": ahora()}, synchronize_session=False)
    token = secrets.token_urlsafe(32)
    db.add(T(usuario_id=usuario.id, token_hash=_hash_token(token), fecha_creacion=ahora(),
             expira=ahora() + timedelta(minutes=MINUTOS_ENLACE)))
    aviso = avisos.para_lector(db, "RECUPERAR_CLAVE", usuario, {
        "enlace": f"{settings.URL_PUBLICA.rstrip('/')}/opac/recuperar?token={token}",
        "minutos": MINUTOS_ENLACE})
    db.commit()
    avisos.enviar_ahora(db, aviso)


def _token_valido(db: Session, token: str) -> models.TokenClave:
    from app.core.tiempo import ahora

    fila = db.query(models.TokenClave).filter_by(token_hash=_hash_token(token or "")).first()
    if not fila or fila.usado is not None or fila.expira < ahora():
        raise ReglaIncumplida("El enlace no es válido o ya venció: pide uno nuevo")
    return fila


def verificar_enlace(db: Session, token: str) -> dict:
    fila = _token_valido(db, token)
    usuario = db.get(models.Usuario, fila.usuario_id)
    return {"nombre": usuario.nombre}


def restablecer_con_enlace(db: Session, token: str, nueva: str) -> None:
    """Fija la contraseña nueva. El enlace se gasta y las sesiones abiertas se cierran."""
    from app.core.tiempo import ahora

    fila = _token_valido(db, token)
    usuario = db.get(models.Usuario, fila.usuario_id)
    if not usuario or not usuario.activo:
        raise ReglaIncumplida("El enlace no es válido o ya venció: pide uno nuevo")
    validar_clave_nueva(usuario, nueva)
    usuario.password_hash = hash_password(nueva)
    usuario.debe_cambiar_clave = False
    fila.usado = ahora()
    db.commit()
