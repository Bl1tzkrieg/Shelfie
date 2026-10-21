"""Permisos del personal: catalogar o acceso total (superbibliotecario).

Cada miembro del personal guarda su lista de permisos en `usuarios.permisos`.
Los perfiles son solo plantillas para asignar varios de una vez: al aplicar uno,
sus permisos se copian a la persona y luego pueden ajustarse a mano.
"""

from enum import Enum
from typing import Iterable


class Permiso(str, Enum):
    CATALOGO = "catalogo"
    SUPERBIBLIOTECARIO = "superbibliotecario"


DESCRIPCIONES = {
    Permiso.CATALOGO: "Alta y edición de libros, ejemplares y registros MARC",
    Permiso.SUPERBIBLIOTECARIO: "Acceso total: personal, configuración, registro de acciones y respaldo",
}

PERFILES = {
    "administrador": {
        "nombre": "Administrador",
        "permisos": [Permiso.SUPERBIBLIOTECARIO],
    },
    "catalogador": {
        "nombre": "Catalogador",
        "permisos": [Permiso.CATALOGO],
    },
}


def normalizar(permisos: Iterable[str]) -> list:
    """Valida, quita duplicados y ordena. Lanza ValueError ante un permiso desconocido."""
    validos = {p.value for p in Permiso}
    resultado = set()
    for p in permisos:
        valor = p.value if isinstance(p, Permiso) else str(p)
        if valor not in validos:
            raise ValueError(f"Permiso desconocido: '{valor}'")
        resultado.add(valor)
    return sorted(resultado)


def tiene(permisos_del_usuario: Iterable[str], requerido: Permiso) -> bool:
    otorgados = set(permisos_del_usuario or [])
    return Permiso.SUPERBIBLIOTECARIO.value in otorgados or requerido.value in otorgados
