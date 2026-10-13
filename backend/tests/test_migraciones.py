import importlib
import warnings

from alembic.autogenerate import compare_metadata
from alembic.migration import MigrationContext

from app import models
from app.database import Base


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
    migracion = importlib.import_module("migrations.versions.0006_busqueda_texto_completo")
    assert migracion.EXPRESION == models.EXPRESION_BUSQUEDA
