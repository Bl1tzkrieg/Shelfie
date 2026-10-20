"""El personal de la biblioteca: altas, rol, estado y restablecimiento de la clave.

Cada usuario es del personal y tiene uno de los dos perfiles de app/core/permisos.py:
administrador (`superbibliotecario`) o catalogador (`catalogo`). Siempre tiene que
quedar al menos un administrador activo.
"""

from typing import List, Literal, Optional

from sqlalchemy import func
from sqlalchemy.orm import Session

from app import models
from app.core.errores import NoEncontrado, ReglaIncumplida
from app.core.permisos import PERFILES, Permiso
from app.security import hash_password
from app.services import registro

Rol = Literal["administrador", "catalogador"]

ADMIN = Permiso.SUPERBIBLIOTECARIO.value


def rol_de(u: models.Usuario) -> str:
    return "administrador" if ADMIN in (u.permisos or []) else "catalogador"


def _permisos_de(rol: str) -> List[str]:
    if rol not in PERFILES:
        raise ReglaIncumplida(f"Rol desconocido: '{rol}'")
    return [p.value for p in PERFILES[rol]["permisos"]]


def vista(u: models.Usuario, forzar_cambio: bool) -> dict:
    """Ficha de un miembro del personal. `forzar_cambio` es el ajuste de seguridad
    (se pasa leído, para no consultarlo una vez por persona al listar)."""
    return {
        "id": u.id,
        "username": u.username,
        "nombre": u.nombre,
        "apellido": u.apellido,
        "rol": rol_de(u),
        "activo": bool(u.activo),
        "debe_cambiar_clave": bool(u.debe_cambiar_clave) and bool(forzar_cambio),
    }


def _forzar_cambio(db: Session) -> bool:
    from app.services import configuracion
    return bool(configuracion.leer(db, "seguridad")["forzar_cambio_clave"])


def vista_de_usuario(db: Session, u: models.Usuario) -> dict:
    return vista(u, _forzar_cambio(db))


def vista_de_sesion(db: Session, u: models.Usuario) -> dict:
    """La ficha de quien entró, con sus permisos."""
    return {**vista_de_usuario(db, u), "permisos": list(u.permisos or [])}


def buscar_para_entrar(db: Session, username: str) -> Optional[models.Usuario]:
    """El usuario activo con ese username (sin distinguir mayúsculas), o None."""
    if not username:
        return None
    return db.query(models.Usuario).filter(
        func.lower(models.Usuario.username) == username.strip().lower(),
        models.Usuario.activo.is_(True)).first()


def _obtener(db: Session, usuario_id: int) -> models.Usuario:
    usuario = db.query(models.Usuario).filter(
        models.Usuario.id == usuario_id).with_for_update().first()
    if not usuario:
        raise NoEncontrado("Usuario no encontrado")
    return usuario


def listar(db: Session) -> List[dict]:
    forzar = _forzar_cambio(db)
    personal = db.query(models.Usuario).order_by(
        models.Usuario.apellido, models.Usuario.nombre, models.Usuario.id).all()
    return [vista(u, forzar) for u in personal]


def _validar_clave_temporal(clave: str) -> None:
    from app.services.autenticacion import MINIMO_CLAVE
    if len(clave or "") < MINIMO_CLAVE:
        raise ReglaIncumplida(
            f"La contraseña temporal necesita al menos {MINIMO_CLAVE} caracteres")


def crear(db: Session, *, username: str, nombre: str, apellido: str, rol: Rol,
          clave_temporal: str) -> dict:
    """Alta de un miembro del personal. Al entrar tendrá que cambiar la clave temporal."""
    username = (username or "").strip()
    nombre, apellido = (nombre or "").strip(), (apellido or "").strip()
    if not username or not nombre or not apellido:
        raise ReglaIncumplida("Usuario, nombre y apellido son obligatorios")
    permisos = _permisos_de(rol)
    _validar_clave_temporal(clave_temporal)
    if db.query(models.Usuario.id).filter(
            func.lower(models.Usuario.username) == username.lower()).first():
        raise ReglaIncumplida(f"Ya existe el usuario «{username}»")
    usuario = models.Usuario(username=username, nombre=nombre, apellido=apellido,
                             password_hash=hash_password(clave_temporal), activo=True,
                             permisos=permisos, debe_cambiar_clave=True)
    db.add(usuario)
    db.flush()
    registro.anotar(db, "configuracion", "alta",
                    f"Dio de alta a {registro.nombre(usuario)} como {rol}",
                    lector=usuario, objeto=("usuario", usuario.id), datos={"rol": rol})
    db.commit()
    db.refresh(usuario)
    return vista_de_usuario(db, usuario)


def _quedan_otros_administradores(db: Session, usuario: models.Usuario) -> bool:
    U = models.Usuario
    return db.query(U.id).filter(U.id != usuario.id, U.activo.is_(True),
                                 U.permisos.contains([ADMIN])).first() is not None


def _cuidar_ultimo_administrador(db: Session, usuario: models.Usuario) -> None:
    if usuario.activo and rol_de(usuario) == "administrador" \
            and not _quedan_otros_administradores(db, usuario):
        raise ReglaIncumplida("Es el único administrador activo: nombra a otro antes")


def cambiar_rol(db: Session, usuario_id: int, rol: Rol) -> dict:
    usuario = _obtener(db, usuario_id)
    permisos = _permisos_de(rol)
    antes = rol_de(usuario)
    if antes != rol:
        if antes == "administrador":
            _cuidar_ultimo_administrador(db, usuario)
        usuario.permisos = permisos
        registro.anotar(db, "configuracion", "permisos",
                        f"Rol de {registro.nombre(usuario)}: {rol}", lector=usuario,
                        objeto=("usuario", usuario.id), datos={"cambios": {"rol": [antes, rol]}})
    db.commit()
    db.refresh(usuario)
    return vista_de_usuario(db, usuario)


def cambiar_estado(db: Session, usuario_id: int, activo: bool) -> dict:
    """Activa o desactiva una cuenta. Desactivada no puede entrar ni usar su sesión."""
    usuario = _obtener(db, usuario_id)
    if bool(usuario.activo) != activo:
        if not activo:
            _cuidar_ultimo_administrador(db, usuario)
        usuario.activo = activo
        registro.anotar(db, "configuracion", "edicion",
                        f"{'Activó' if activo else 'Desactivó'} a {registro.nombre(usuario)}",
                        lector=usuario, objeto=("usuario", usuario.id),
                        datos={"cambios": {"activo": [not activo, activo]}})
    db.commit()
    db.refresh(usuario)
    return vista_de_usuario(db, usuario)


def restablecer_clave(db: Session, usuario_id: int, clave_temporal: str) -> dict:
    """Pone una clave temporal: las sesiones abiertas de esa persona dejan de valer y al
    entrar tendrá que elegir una propia."""
    usuario = _obtener(db, usuario_id)
    _validar_clave_temporal(clave_temporal)
    usuario.password_hash = hash_password(clave_temporal)
    usuario.debe_cambiar_clave = True
    registro.anotar(db, "configuracion", "clave_restablecida",
                    f"Restableció la contraseña de {registro.nombre(usuario)}",
                    lector=usuario, objeto=("usuario", usuario.id))
    db.commit()
    db.refresh(usuario)
    return vista_de_usuario(db, usuario)
