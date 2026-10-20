"""Crea (o promueve) un administrador (permiso superbibliotecario) para entrar a la intranet.

Uso (desde backend/, con el entorno virtual activo):

    python -m scripts.crear_admin

Pide los datos por consola. Si el usuario ya existe, lo convierte en
administrador, lo reactiva y opcionalmente le cambia la contraseña.
"""

import getpass
import os
import sys

BACKEND_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, BACKEND_DIR)

from sqlalchemy import func  # noqa: E402

from app import models  # noqa: E402
from app.core.permisos import Permiso  # noqa: E402
from app.core.tiempo import ahora  # noqa: E402
from app.database import SessionLocal  # noqa: E402
from app.security import hash_password  # noqa: E402


def _preguntar(texto: str, obligatorio: bool = True) -> str:
    while True:
        valor = input(f"{texto}: ").strip()
        if valor or not obligatorio:
            return valor
        print("  (obligatorio)")


def _pedir_clave() -> str:
    while True:
        clave = getpass.getpass("Contraseña (mín. 8 caracteres): ")
        if len(clave) < 8:
            print("  Muy corta.")
            continue
        if clave != getpass.getpass("Repite la contraseña: "):
            print("  No coinciden.")
            continue
        return clave


def main() -> None:
    db = SessionLocal()
    try:
        username = _preguntar("Usuario (para iniciar sesión)")
        usuario = db.query(models.Usuario).filter(
            func.lower(models.Usuario.username) == username.lower()).first()

        if usuario:
            print(f"Ya existe: {usuario.nombre} {usuario.apellido} ({usuario.username}).")
            if input("¿Cambiar su contraseña? [s/N]: ").strip().lower() == "s":
                usuario.password_hash = hash_password(_pedir_clave())
        else:
            usuario = models.Usuario(
                username=username,
                nombre=_preguntar("Nombre"),
                apellido=_preguntar("Apellido"),
                email=_preguntar("Email (opcional)", obligatorio=False) or None,
                password_hash=hash_password(_pedir_clave()),
                fecha_creacion=ahora(),
            )
            db.add(usuario)

        usuario.activo = True
        usuario.permisos = sorted(set(usuario.permisos or []) | {Permiso.SUPERBIBLIOTECARIO.value})
        db.commit()
        print(f"\nListo: '{usuario.username}' es administrador y puede entrar a la intranet.")
    except Exception as error:  # noqa: BLE001 — mensaje claro en vez de traceback
        db.rollback()
        sys.exit(f"No se pudo crear el administrador: {error}")
    finally:
        db.close()


if __name__ == "__main__":
    main()
