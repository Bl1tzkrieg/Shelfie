"""Entorno de Alembic para Shelfie.

La URL de conexión sale de la misma configuración que usa la API
(`app.config.settings.DATABASE_URL`, leída de backend/.env), así que no hay una
segunda copia de credenciales en alembic.ini.
"""

from logging.config import fileConfig

from alembic import context
from sqlalchemy import engine_from_config, pool

from app import models  # noqa: F401  (registra todas las tablas en Base.metadata)
from app.config import settings
from app.database import Base

config = context.config

# Permite que los tests apunten a otra base con config.set_main_option(...).
if not config.get_main_option("sqlalchemy.url"):
    # ConfigParser interpreta «%»: una contraseña con % rompería la URL si no se duplica.
    config.set_main_option("sqlalchemy.url", settings.DATABASE_URL.replace("%", "%%"))

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata


def include_object(objeto, nombre, tipo, reflejado, comparado_con):
    """Solo se comparan las tablas que Shelfie declara en models.py.

    Si la base tiene tablas de otros proyectos en el mismo esquema, Alembic las
    ignora: nunca las reporta en `alembic check` ni propone borrarlas en un
    `revision --autogenerate`.
    """
    if tipo == "table" and reflejado and comparado_con is None:
        return False
    return True


def run_migrations_offline() -> None:
    """Genera el SQL sin conectarse (alembic upgrade head --sql)."""
    context.configure(
        url=config.get_main_option("sqlalchemy.url"),
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        compare_type=True,
        include_object=include_object,
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            compare_type=True,
            include_object=include_object,
        )
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
