"""Gestión del personal de la biblioteca y sus permisos."""

from typing import List

from sqlalchemy.orm import Session

from app import models
from app.core.errores import NoEncontrado, ReglaIncumplida
from app.core.permisos import DESCRIPCIONES, PERFILES, Permiso, normalizar
from app.services import registro


def _debe_cambiar(db: Session, u: models.Usuario) -> bool:
    if not u.debe_cambiar_clave:
        return False
    from app.services.autenticacion import tiene_que_cambiar_clave
    return tiene_que_cambiar_clave(db, u)


def vista_de_usuario(db: Session, u: models.Usuario) -> dict:
    """Ficha de un miembro del personal (sin préstamos, deudas ni sede)."""
    return {
        "nro_carnet": u.nro_carnet,
        "nombre": u.nombre,
        "apellido": u.apellido,
        "email": u.email,
        "activo": u.activo,
        "departamento": u.departamento,
        "fecha_creacion": u.fecha_creacion,
        "es_personal": bool(u.es_personal),
        "permisos": list(u.permisos or []),
        "debe_cambiar_clave": _debe_cambiar(db, u),
    }


def listar_vistas(db: Session, usuarios: List[models.Usuario]) -> List[dict]:
    return [vista_de_usuario(db, u) for u in usuarios]


def obtener_por_carnet(db: Session, nro_carnet: str) -> models.Usuario:
    usuario = db.query(models.Usuario).filter(models.Usuario.nro_carnet == nro_carnet).first()
    if not usuario:
        raise NoEncontrado("Usuario no encontrado")
    return usuario


def buscar_por_identificador(db: Session, identificador: str):
    """Username o número de carnet, en ese orden."""
    usuario = db.query(models.Usuario).filter(models.Usuario.username == identificador).first()
    if not usuario:
        usuario = db.query(models.Usuario).filter(
            models.Usuario.nro_carnet == identificador).first()
    return usuario


def catalogo_de_permisos() -> dict:
    """Permisos y perfiles disponibles, para construir la pantalla de asignación."""
    return {
        "permisos": [{"codigo": p.value, "descripcion": DESCRIPCIONES[p]} for p in Permiso],
        "perfiles": [
            {"codigo": codigo, "nombre": perfil["nombre"],
             "permisos": [p.value for p in perfil["permisos"]]}
            for codigo, perfil in PERFILES.items()
        ],
    }


def listar(db: Session) -> List[dict]:
    personal = db.query(models.Usuario).filter(
        models.Usuario.es_personal == True).order_by(models.Usuario.apellido).all()  # noqa: E712
    return listar_vistas(db, personal)


def asignar(db: Session, actor: models.Usuario, nro_carnet: str,
            es_personal: bool, permisos: List[str]) -> dict:
    """Da o quita acceso a la intranet y fija los permisos de una persona."""
    try:
        permisos = normalizar(permisos) if es_personal else []
    except ValueError as error:
        raise ReglaIncumplida(str(error))

    destino = obtener_por_carnet(db, nro_carnet)

    # Evita que un administrador se deje fuera a sí mismo por accidente.
    if destino.id == actor.id and Permiso.SUPERBIBLIOTECARIO.value not in permisos:
        raise ReglaIncumplida(
            "No puedes quitarte tu propio permiso de superbibliotecario; "
            "pídeselo a otro administrador")

    antes = {"es_personal": bool(destino.es_personal), "permisos": list(destino.permisos or [])}
    destino.es_personal = es_personal
    destino.permisos = permisos
    cambios = registro.diferencias(antes, {"es_personal": es_personal, "permisos": permisos})
    if cambios:
        detalle = (", ".join(permisos) or "ninguno") if es_personal else "sin acceso a la intranet"
        registro.anotar(db, "configuracion", "permisos",
                        f"Permisos de {registro.nombre(destino)}: {detalle}",
                        lector=destino, objeto=("usuario", destino.id), datos={"cambios": cambios})
    db.commit()
    db.refresh(destino)
    return vista_de_usuario(db, destino)
