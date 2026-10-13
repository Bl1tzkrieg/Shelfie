"""Crea (o promueve) un superbibliotecario para entrar a la intranet.

Uso (desde backend/, con el entorno virtual activo):

    python -m scripts.crear_admin

Pide los datos por consola. Si el carnet ya existe, lo convierte en
superbibliotecario y opcionalmente le cambia la contraseña.
"""

import getpass
import os
import sys

BACKEND_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, BACKEND_DIR)

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
        carnet = _preguntar("Número de carnet")
        usuario = db.query(models.Usuario).filter_by(nro_carnet=carnet).first()

        if usuario:
            print(f"Ya existe: {usuario.nombre} {usuario.apellido} ({usuario.username}).")
            if input("¿Cambiar su contraseña? [s/N]: ").strip().lower() == "s":
                usuario.password_hash = hash_password(_pedir_clave())
        else:
            categoria = (db.query(models.CategoriaUsuario).filter_by(codigo="ADM").first()
                         or db.query(models.CategoriaUsuario).first())
            if not categoria:
                sys.exit("No hay categorías de usuario. Corre primero el instalador o seed.py.")
            usuario = models.Usuario(
                nro_carnet=carnet,
                username=_preguntar("Usuario (para iniciar sesión)"),
                nombre=_preguntar("Nombre"),
                apellido=_preguntar("Apellido"),
                email=_preguntar("Email"),
                password_hash=hash_password(_pedir_clave()),
                categoria_id=categoria.id,
                saldo_multas=0,
                activo=True,
                fecha_creacion=ahora(),
            )
            db.add(usuario)

        usuario.es_personal = True
        usuario.activo = True
        usuario.permisos = sorted(set(usuario.permisos or []) | {Permiso.SUPERBIBLIOTECARIO.value})
        db.commit()
        print(f"\nListo: '{usuario.username}' es superbibliotecario y puede entrar a la intranet.")
    except Exception as error:  # noqa: BLE001 — mensaje claro en vez de traceback
        db.rollback()
        sys.exit(f"No se pudo crear el administrador: {error}")
    finally:
        db.close()


if __name__ == "__main__":
    main()
