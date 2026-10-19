"""Gestión del personal de la biblioteca y sus permisos."""

from typing import List

from sqlalchemy.orm import Session

from app import models
from app.core.errores import ReglaIncumplida
from app.core.permisos import DESCRIPCIONES, PERFILES, Permiso, normalizar
from app.services import registro, usuarios


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
    return usuarios.listar_vistas(db, personal)


def asignar(db: Session, actor: models.Usuario, nro_carnet: str,
            es_personal: bool, permisos: List[str]) -> dict:
    """Da o quita acceso a la intranet y fija los permisos de una persona."""
    try:
        permisos = normalizar(permisos) if es_personal else []
    except ValueError as error:
        raise ReglaIncumplida(str(error))

    destino = usuarios.obtener_por_carnet(db, nro_carnet)

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
        registro.anotar(db, "lectores", "permisos",
                        f"Permisos de {registro.nombre(destino)}: {detalle}",
                        lector=destino, objeto=("usuario", destino.id), datos={"cambios": cambios})
    db.commit()
    db.refresh(destino)
    return usuarios.vista_de_usuario(db, destino)
