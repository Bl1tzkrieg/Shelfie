"""Login de la intranet y cambio de la propia contraseña."""

from typing import Optional

from sqlalchemy.orm import Session

from app import models
from app.core.errores import CredencialesInvalidas, DemasiadosIntentos, ReglaIncumplida
from app.security import hash_password, verify_password
from app.services import personal, registro


# --- Entrar ------------------------------------------------------------------------------
#
# Mismo mensaje para usuario inexistente y contraseña incorrecta, y el mismo trabajo en
# ambos casos (se verifica contra un hash de relleno), para no revelar qué usuarios
# existen; una cuenta desactivada cuenta como inexistente. Tras varios fallos seguidos
# con el mismo usuario (o desde la misma IP) hay que esperar unos minutos: el bloqueo es
# temporal, no deja la cuenta inhabilitada.

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
    por_usuario = db.query(I).filter(I.identificador == identificador, I.fecha > desde).count()
    por_ip = db.query(I).filter(I.ip == ip, I.fecha > desde).count() if ip else 0
    if por_usuario >= maximo or por_ip >= maximo * 6:
        raise DemasiadosIntentos(
            f"Demasiados intentos fallidos. Espera {minutos} minutos y vuelve a intentarlo")


def _verificar(db: Session, identificador: str, password: str, ip: Optional[str],
               mensaje: str) -> models.Usuario:
    from app.core.tiempo import ahora

    clave = (identificador or "").strip().lower()[:100]
    _frenar_si_insiste(db, clave, ip)
    usuario = personal.buscar_para_entrar(db, identificador)
    valida = verify_password(password, usuario.password_hash if usuario else _HASH_DE_RELLENO)
    if not usuario or not valida:
        db.add(models.IntentoAcceso(identificador=clave, ip=ip, fecha=ahora()))
        db.commit()
        raise CredencialesInvalidas(mensaje)
    db.query(models.IntentoAcceso).filter(models.IntentoAcceso.identificador == clave).delete(
        synchronize_session=False)
    # Entrar con el nombre de usuario como contraseña obliga a elegir una propia.
    if _seguridad(db)["forzar_cambio_clave"] and \
            password.strip().lower() == usuario.username.lower():
        usuario.debe_cambiar_clave = True
    db.commit()
    return usuario


def autenticar_personal(db: Session, identificador: str, password: str,
                        ip: Optional[str] = None):
    """Devuelve el usuario si las credenciales son válidas y la cuenta está activa.

    Entradas y fallos quedan en el registro (módulo «sesion»), con el identificador
    que se escribió; nunca la contraseña."""
    db.info["ip"] = ip
    try:
        usuario = _verificar(db, identificador, password, ip, "Usuario o contraseña incorrectos")
    except CredencialesInvalidas as error:
        registro.anotar(db, "sesion", "entrada_fallida",
                        f"Intento fallido de entrar a la intranet como «{(identificador or '').strip()[:60]}»"
                        f": {error.mensaje}", actor=None)
        db.commit()
        raise
    registro.anotar(db, "sesion", "entrada", f"Entró a la intranet: {registro.nombre(usuario)}",
                    actor=usuario, usuario_afectado=usuario)
    db.commit()
    return usuario


def tiene_que_cambiar_clave(db: Session, usuario: models.Usuario) -> bool:
    return bool(usuario.debe_cambiar_clave) and bool(_seguridad(db)["forzar_cambio_clave"])


MINIMO_CLAVE = 8


def validar_clave_nueva(usuario: models.Usuario, nueva: str) -> None:
    if len(nueva or "") < MINIMO_CLAVE:
        raise ReglaIncumplida(f"La contraseña nueva necesita al menos {MINIMO_CLAVE} caracteres")
    if nueva.strip().lower() == usuario.username.lower():
        raise ReglaIncumplida("La contraseña no puede ser el nombre de usuario")


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
    registro.anotar(db, "sesion", "clave_cambiada",
                    f"{registro.nombre(usuario)} cambió su contraseña", usuario_afectado=usuario)
    db.commit()
