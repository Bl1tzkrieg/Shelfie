"""Login de la intranet y del OPAC, y cambio de contraseña."""

from sqlalchemy.orm import Session

from app import models
from app.core.errores import AccesoDenegado, CredencialesInvalidas, ReglaIncumplida
from app.security import hash_password, verify_password
from app.services import usuarios


def autenticar_personal(db: Session, identificador: str, password: str):
    """Devuelve el usuario si las credenciales son válidas y tiene acceso a la intranet."""
    usuario = usuarios.buscar_por_identificador(db, identificador)

    # Mismo mensaje para usuario inexistente y contraseña incorrecta: no se
    # revela cuál de los dos falló.
    if not usuario or not verify_password(password, usuario.password_hash):
        raise CredencialesInvalidas("Usuario o contraseña incorrectos")
    if not usuario.activo:
        raise AccesoDenegado("La cuenta está suspendida")
    if not usuario.es_personal:
        raise AccesoDenegado("Esta cuenta no tiene acceso a la intranet")
    return usuario


def autenticar_lector(db: Session, identificador: str, password: str):
    """Login del OPAC: cualquier usuario activo entra a su propia cuenta."""
    usuario = usuarios.buscar_por_identificador(db, (identificador or "").strip())
    if not usuario or not verify_password(password, usuario.password_hash):
        raise CredencialesInvalidas("Carnet o contraseña incorrectos")
    if not usuario.activo:
        raise AccesoDenegado("Tu cuenta está suspendida: consulta en la biblioteca")
    return usuario


MINIMO_CLAVE = 8


def validar_clave_nueva(usuario: models.Usuario, nueva: str) -> None:
    if len(nueva or "") < MINIMO_CLAVE:
        raise ReglaIncumplida(f"La contraseña nueva necesita al menos {MINIMO_CLAVE} caracteres")
    if nueva.strip().lower() in {usuario.nro_carnet.lower(), (usuario.username or "").lower()}:
        raise ReglaIncumplida("La contraseña no puede ser el carnet ni el nombre de usuario")


def cambiar_clave(db: Session, usuario: models.Usuario, actual: str, nueva: str) -> None:
    """Cambio de la propia contraseña: exige la actual. Cierra las demás sesiones."""
    if not verify_password(actual, usuario.password_hash):
        raise CredencialesInvalidas("La contraseña actual no es correcta")
    if actual == nueva:
        raise ReglaIncumplida("La contraseña nueva debe ser distinta de la actual")
    validar_clave_nueva(usuario, nueva)
    usuario.password_hash = hash_password(nueva)
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
    db.commit()
