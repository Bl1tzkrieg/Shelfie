"""Permisos del personal, al estilo de los permisos por módulo de Koha.

Cada miembro del personal guarda su lista de permisos en `usuarios.permisos`.
Los perfiles son solo plantillas para asignar varios de una vez: al aplicar uno,
sus permisos se copian a la persona y luego pueden ajustarse a mano.
"""

from enum import Enum
from typing import Iterable


class Permiso(str, Enum):
    CIRCULACION = "circulacion"
    CATALOGO = "catalogo"
    LECTORES = "lectores"
    REPORTES = "reportes"
    CONFIGURACION = "configuracion"
    ADQUISICIONES = "adquisiciones"
    SERIADAS = "seriadas"
    SUPERBIBLIOTECARIO = "superbibliotecario"


DESCRIPCIONES = {
    Permiso.CIRCULACION: "Préstamos, devoluciones, renovaciones, reservas, pérdidas y cobros",
    Permiso.CATALOGO: "Alta y edición de material bibliográfico",
    Permiso.LECTORES: "Alta, edición y suspensión de lectores; condonación de deudas",
    Permiso.REPORTES: "Estadísticas y reportes descargables",
    Permiso.CONFIGURACION: "Institución, reglas de circulación y calendario",
    Permiso.ADQUISICIONES: "Proveedores y órdenes de compra",
    Permiso.SERIADAS: "Suscripciones y kardex de fascículos",
    Permiso.SUPERBIBLIOTECARIO: "Acceso total, incluida la gestión de permisos del personal",
}

PERFILES = {
    "administrador": {
        "nombre": "Administrador",
        "permisos": [Permiso.SUPERBIBLIOTECARIO],
    },
    "bibliotecario": {
        "nombre": "Bibliotecario",
        "permisos": [Permiso.CIRCULACION, Permiso.CATALOGO, Permiso.LECTORES,
                     Permiso.REPORTES, Permiso.ADQUISICIONES, Permiso.SERIADAS],
    },
    "auxiliar": {
        "nombre": "Auxiliar de circulación",
        "permisos": [Permiso.CIRCULACION],
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
