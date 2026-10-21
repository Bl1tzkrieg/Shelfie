"""Qué ruta se acepta como pg_dump.

El respaldo corre como SYSTEM (tarea programada) y ejecuta el pg_dump configurado: si se
aceptara cualquier archivo, un administrador de la web podría hacer correr cualquier programa
como SYSTEM. Por eso solo vale un archivo que se llame pg_dump (o pg_dump.exe), fuera de una
carpeta de red y fuera de las carpetas de usuario, donde cualquiera puede dejar un ejecutable.
"""

import ntpath
import os
from typing import List, Optional

NOMBRES = {"pg_dump", "pg_dump.exe"}


def _carpetas_de_perfiles() -> List[str]:
    """C:\\Users y la carpeta real de perfiles (la madre de %PUBLIC%, que existe también
    para SYSTEM), como en instalacion/comun.ps1."""
    carpetas = [r"C:\Users"]
    publica = os.environ.get("PUBLIC")
    if publica:
        carpetas.append(ntpath.dirname(publica.rstrip("\\/")))
    return [ntpath.normcase(ntpath.normpath(c)) for c in carpetas if c]


def _en_windows() -> bool:
    return os.name == "nt"


def _es_absoluta_posix(ruta: str) -> bool:
    """/usr/lib/postgresql/16/bin/pg_dump fuera de Windows (desarrollo, pruebas)."""
    return (not _en_windows() and ruta.startswith("/") and not ruta.startswith("//")
            and "\\" not in ruta)


def problema(ruta: Optional[str]) -> Optional[str]:
    """Por qué `ruta` no sirve como pg_dump, o None si sirve (o si está vacía).

    Todo se decide sobre la ruta normalizada como la lee Windows (con / pasada a \\): así
    \\/servidor/... o /\\servidor\\... cuentan como carpeta de red y C:\\Program Files\\..\\Users
    como carpeta de usuario."""
    ruta = (ruta or "").strip().strip('"').strip()
    if not ruta:
        return None
    normal = ntpath.normpath(ruta.replace("/", "\\"))
    if ntpath.basename(normal).lower() not in NOMBRES:
        return ("La ruta de pg_dump debe terminar en pg_dump.exe (por ejemplo "
                r"C:\Program Files\PostgreSQL\16\bin\pg_dump.exe)")
    unidad, resto = ntpath.splitdrive(normal)
    if unidad.startswith("\\\\") or normal.startswith("\\\\"):
        return "pg_dump debe estar en este equipo, no en una carpeta de red"
    con_unidad = len(unidad) == 2 and unidad[1] == ":" and resto.startswith("\\")
    if not con_unidad and not _es_absoluta_posix(ruta):
        return ("La ruta de pg_dump debe ser completa, con la unidad (por ejemplo "
                r"C:\Program Files\PostgreSQL\16\bin\pg_dump.exe)")
    normal = ntpath.normcase(normal)
    for perfiles in _carpetas_de_perfiles():
        if normal == perfiles or normal.startswith(perfiles + "\\"):
            return ("pg_dump no puede estar dentro de una carpeta de usuario "
                    f"({perfiles}): usa el de la instalación de PostgreSQL")
    return None
