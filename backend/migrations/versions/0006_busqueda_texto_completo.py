"""Búsqueda de texto completo (Fase 4)

- Extensión `unaccent` (es "trusted": la crea el dueño de la base sin superusuario).
- Configuración de búsqueda `shelfie_es`: la de español de PostgreSQL con los
  acentos quitados antes de reducir a la raíz. Así "arbol" encuentra "Árboles" y
  "garcia" encuentra "García".
- `registros_bibliograficos.busqueda`: tsvector generado (título > autor >
  materia > ISBN) con índice GIN. Lo mantiene PostgreSQL: no hay que acordarse de
  actualizarlo al editar un registro.

Revision ID: 0006_busqueda
Revises: 0005_cierre_circulacion
"""
from typing import Sequence, Union

from alembic import op

revision: str = "0006_busqueda"
down_revision: Union[str, None] = "0005_cierre_circulacion"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# Debe coincidir con models.EXPRESION_BUSQUEDA (el test de migraciones lo vigila).
EXPRESION = (
    "setweight(to_tsvector('shelfie_es'::regconfig, coalesce(titulo, '')), 'A') || "
    "setweight(to_tsvector('shelfie_es'::regconfig, coalesce(autor, '')), 'B') || "
    "setweight(to_tsvector('shelfie_es'::regconfig, coalesce(materia, '')), 'C') || "
    "setweight(to_tsvector('simple'::regconfig, coalesce(isbn, '')), 'D')"
)


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS unaccent")
    op.execute("""
        DO $$
        BEGIN
            IF NOT EXISTS (SELECT 1 FROM pg_ts_config WHERE cfgname = 'shelfie_es') THEN
                CREATE TEXT SEARCH CONFIGURATION shelfie_es (COPY = pg_catalog.spanish);
                ALTER TEXT SEARCH CONFIGURATION shelfie_es
                    ALTER MAPPING FOR hword, hword_part, word WITH unaccent, spanish_stem;
            END IF;
        END $$
    """)
    op.execute(f"""
        ALTER TABLE registros_bibliograficos
        ADD COLUMN busqueda tsvector GENERATED ALWAYS AS ({EXPRESION}) STORED
    """)
    op.create_index("ix_registros_busqueda", "registros_bibliograficos", ["busqueda"],
                    postgresql_using="gin")


def downgrade() -> None:
    op.drop_index("ix_registros_busqueda", table_name="registros_bibliograficos")
    op.drop_column("registros_bibliograficos", "busqueda")
    op.execute("DROP TEXT SEARCH CONFIGURATION IF EXISTS shelfie_es")
    # La extensión se deja: otra cosa en la base podría estar usándola.
