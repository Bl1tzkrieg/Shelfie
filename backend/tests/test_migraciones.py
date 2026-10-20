import importlib
import os
import warnings

import pytest
from alembic import command
from alembic.autogenerate import compare_metadata
from alembic.config import Config
from alembic.migration import MigrationContext
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.engine import make_url

from app import models
from app.database import Base
from tests.conftest import BACKEND_DIR, TEST_DATABASE_URL

TABLAS_LITE = {
    "registros_bibliograficos", "items", "usuarios", "configuraciones", "registro_acciones",
    "sesiones_cerradas", "intentos_acceso", "ejecuciones_tarea", "alembic_version",
}


def test_models_y_migraciones_coinciden(engine):
    """Falla si alguien cambia models.py sin generar la migración correspondiente."""
    with engine.connect() as conexion:
        contexto = MigrationContext.configure(conexion, opts={"compare_type": True})
        with warnings.catch_warnings():
            # Alembic no compara expresiones de columnas generadas; lo cubre el test siguiente.
            warnings.filterwarnings("ignore", message="Computed default on")
            diferencias = compare_metadata(contexto, Base.metadata)
    assert diferencias == [], diferencias


def test_expresion_de_busqueda_igual_en_modelo_y_migracion():
    migracion = importlib.import_module("migrations.versions.0001_lite")
    assert migracion.EXPRESION == models.EXPRESION_BUSQUEDA


@pytest.fixture()
def base_vacia():
    """Una base propia y vacía (`<base de pruebas>_mig`): no pisa la de la sesión."""
    url = make_url(TEST_DATABASE_URL)
    nombre = f"{url.database}_mig"
    servidor = create_engine(url.set(database="postgres"), isolation_level="AUTOCOMMIT")
    with servidor.connect() as c:
        c.execute(text(f'DROP DATABASE IF EXISTS "{nombre}"'))
        c.execute(text(f'CREATE DATABASE "{nombre}"'))
    destino = url.set(database=nombre).render_as_string(hide_password=False)
    try:
        yield destino
    finally:
        with servidor.connect() as c:
            c.execute(text(f'DROP DATABASE IF EXISTS "{nombre}" WITH (FORCE)'))
        servidor.dispose()


def test_lite_sube_y_baja(base_vacia):
    cfg = Config(os.path.join(BACKEND_DIR, "alembic.ini"))
    cfg.set_main_option("script_location", os.path.join(BACKEND_DIR, "migrations"))
    cfg.set_main_option("sqlalchemy.url", base_vacia.replace("%", "%%"))
    motor = create_engine(base_vacia)
    try:
        command.upgrade(cfg, "head")
        with motor.connect() as c:
            assert set(inspect(c).get_table_names()) == TABLAS_LITE
            config = c.execute(text("SELECT count(*) FROM pg_ts_config "
                                    "WHERE cfgname = 'shelfie_es'")).scalar_one()
            assert config == 1

        command.downgrade(cfg, "base")
        with motor.connect() as c:
            assert set(inspect(c).get_table_names()) == {"alembic_version"}
            assert c.execute(text("SELECT count(*) FROM alembic_version")).scalar_one() == 0
            assert c.execute(text("SELECT count(*) FROM pg_ts_config "
                                  "WHERE cfgname = 'shelfie_es'")).scalar_one() == 0
    finally:
        motor.dispose()
