"""Instalador de la base de datos de Shelfie (equivalente a `koha-create`).

Lee DATABASE_URL de backend/.env y, usando una cuenta administradora de
PostgreSQL solo durante la instalación, deja todo listo:

  1. Crea el usuario (rol) de la URL si no existe.
  2. Crea la base de la URL y su gemela `<base>_test`, con ese usuario como dueño.
  3. Aplica las migraciones (`alembic upgrade head`).
  4. Opcionalmente carga los datos de ejemplo (--seed).

Es idempotente: se puede correr de nuevo sin romper nada. La API sigue
conectándose con el usuario sin privilegios de DATABASE_URL; la cuenta
administradora no se guarda en ningún lado.

Uso (desde backend/, con el entorno virtual activo):

    python -m scripts.inicializar_bd --seed
    python -m scripts.inicializar_bd --admin-user postgres --seed
"""

import argparse
import getpass
import os
import sys

import psycopg2
from psycopg2 import sql
from sqlalchemy.engine import make_url

BACKEND_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, BACKEND_DIR)


def _conectar_admin(destino, admin_user: str, admin_password: str):
    try:
        conexion = psycopg2.connect(
            host=destino.host or "localhost",
            port=destino.port or 5432,
            user=admin_user,
            password=admin_password,
            dbname="postgres",
        )
    except UnicodeDecodeError:
        # PostgreSQL en español responde en Latin-1 antes de autenticar y
        # psycopg2 no puede mostrar el mensaje: casi siempre es la contraseña.
        sys.exit(
            f"No se pudo conectar como '{admin_user}'. Lo más probable es una contraseña "
            "incorrecta (PostgreSQL respondió en una codificación que psycopg2 no puede mostrar)."
        )
    except psycopg2.OperationalError as error:
        sys.exit(f"No se pudo conectar como '{admin_user}': {error}")
    conexion.autocommit = True  # CREATE DATABASE no puede ir dentro de una transacción
    return conexion


def _crear_rol(cursor, usuario: str, password: str) -> None:
    cursor.execute("SELECT 1 FROM pg_roles WHERE rolname = %s", (usuario,))
    if cursor.fetchone():
        print(f"  [--] usuario '{usuario}' ya existe")
        return
    cursor.execute(sql.SQL("CREATE ROLE {} LOGIN PASSWORD {}").format(
        sql.Identifier(usuario), sql.Literal(password)))
    print(f"  [ok] usuario '{usuario}' creado")


def _crear_base(cursor, nombre: str, dueno: str) -> None:
    cursor.execute("SELECT 1 FROM pg_database WHERE datname = %s", (nombre,))
    if cursor.fetchone():
        print(f"  [--] base '{nombre}' ya existe")
        return
    cursor.execute(sql.SQL("CREATE DATABASE {} OWNER {} ENCODING 'UTF8' TEMPLATE template0").format(
        sql.Identifier(nombre), sql.Identifier(dueno)))
    print(f"  [ok] base '{nombre}' creada (dueño: {dueno})")


def _migrar(url: str) -> None:
    from alembic import command
    from alembic.config import Config

    cfg = Config(os.path.join(BACKEND_DIR, "alembic.ini"))
    cfg.set_main_option("script_location", os.path.join(BACKEND_DIR, "migrations"))
    cfg.set_main_option("sqlalchemy.url", url.replace("%", "%%"))
    command.upgrade(cfg, "head")


def _despedida(destino, seed: bool, sin_test: bool, desde_instalador: bool) -> list:
    """Los mensajes finales. El instalador ya levanta la API y crea al administrador, así
    que cuando él llama no se imprime nada de esto."""
    if desde_instalador:
        return []
    lineas = ["\nListo. Levanta la API con: uvicorn app.main:app --reload"]
    if not seed:
        lineas.append("Crea tu usuario administrador con: python -m scripts.crear_admin")
    if not sin_test:
        prueba = destino.set(database=f"{destino.database}_test")
        lineas.append(f"Para los tests: TEST_DATABASE_URL="
                      f"{prueba.render_as_string(hide_password=True)}  (con tu clave en lugar de ***)")
    return lineas


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--admin-user", default="postgres",
                        help="Cuenta administradora de PostgreSQL (por defecto: postgres)")
    parser.add_argument("--seed", action="store_true", help="Cargar los datos de ejemplo")
    parser.add_argument("--desde-instalador", action="store_true",
                        help="Lo llama instalar.ps1: no imprime los pasos siguientes de desarrollo")
    parser.add_argument("--sin-test", action="store_true", help="No crear la base <base>_test")
    args = parser.parse_args()

    from app.config import settings  # lee backend/.env

    destino = make_url(settings.DATABASE_URL)
    if not destino.username or not destino.database:
        sys.exit("DATABASE_URL debe incluir usuario y base: postgresql://USUARIO:CLAVE@host:5432/BASE")
    if destino.username != args.admin_user and not destino.password:
        sys.exit("DATABASE_URL no trae contraseña: el usuario de Shelfie se crearía sin clave. "
                 "Usa postgresql://USUARIO:CLAVE@host:5432/BASE")
    if destino.username == args.admin_user:
        print(f"Aviso: la API usará la cuenta administradora '{args.admin_user}'. "
              "Se recomienda un usuario propio para Shelfie.")

    admin_password = os.environ.get("PGPASSWORD") or getpass.getpass(
        f"Contraseña de '{args.admin_user}' (solo para instalar, no se guarda): ")

    print(f"Preparando PostgreSQL en {destino.host or 'localhost'}:{destino.port or 5432}")
    conexion = _conectar_admin(destino, args.admin_user, admin_password)
    with conexion.cursor() as cursor:
        if destino.username != args.admin_user:
            _crear_rol(cursor, destino.username, destino.password)
        _crear_base(cursor, destino.database, destino.username)
        if not args.sin_test:
            _crear_base(cursor, f"{destino.database}_test", destino.username)
    conexion.close()

    print("Aplicando migraciones…")
    _migrar(settings.DATABASE_URL)
    print("  [ok] esquema al día")

    if args.seed:
        print("Cargando datos de ejemplo…")
        import runpy
        runpy.run_path(os.path.join(BACKEND_DIR, "seed.py"), run_name="__main__")

    for linea in _despedida(destino, args.seed, args.sin_test, args.desde_instalador):
        print(linea)


if __name__ == "__main__":
    main()
