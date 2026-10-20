"""Shelfie-lite: esquema inicial único

Reemplaza las migraciones 0001–0016 de Shelfie completo. Una base de Shelfie completo
no se actualiza a lite: los datos se pasan exportando MARC desde Shelfie e importándolo
aquí.

- Extensión `unaccent` (es "trusted": la crea el dueño de la base sin superusuario).
- Configuración de búsqueda `shelfie_es`: la de español de PostgreSQL con los acentos
  quitados antes de reducir a la raíz. Así "arbol" encuentra "Árboles" y "garcia"
  encuentra "García".
- `registros_bibliograficos.busqueda`: tsvector generado (título A, autor B, materia y
  editorial C, ISBN y cota D) con índice GIN. Lo mantiene PostgreSQL.
- `items.codigo_barras` es opcional: el índice único es parcial (solo los no nulos).

Revision ID: 0001_lite
Revises:
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0001_lite"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# Debe coincidir con models.EXPRESION_BUSQUEDA (el test de migraciones lo vigila).
EXPRESION = (
    "setweight(to_tsvector('shelfie_es'::regconfig, coalesce(titulo, '')), 'A') || "
    "setweight(to_tsvector('shelfie_es'::regconfig, coalesce(autor, '')), 'B') || "
    "setweight(to_tsvector('shelfie_es'::regconfig, coalesce(materia, '')), 'C') || "
    "setweight(to_tsvector('shelfie_es'::regconfig, coalesce(editorial, '')), 'C') || "
    "setweight(to_tsvector('simple'::regconfig, coalesce(isbn, '')), 'D') || "
    "setweight(to_tsvector('simple'::regconfig, coalesce(cota, '')), 'D')"
)

FECHA = sa.DateTime(timezone=True)


def _ahora():
    return sa.text("now()")


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

    op.create_table(
        "usuarios",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("username", sa.String(50), nullable=False, unique=True),
        sa.Column("password_hash", sa.String(255), nullable=False),
        sa.Column("nombre", sa.String(100), nullable=False),
        sa.Column("apellido", sa.String(100), nullable=False),
        sa.Column("email", sa.String(100), nullable=True),
        sa.Column("activo", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("permisos", postgresql.JSONB(), nullable=False,
                  server_default=sa.text("'[]'::jsonb")),
        sa.Column("debe_cambiar_clave", sa.Boolean(), nullable=False,
                  server_default=sa.text("false")),
        sa.Column("fecha_creacion", FECHA, nullable=False, server_default=_ahora()),
    )
    op.create_index("ix_usuarios_id", "usuarios", ["id"])

    op.create_table(
        "registros_bibliograficos",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("isbn", sa.String(20), nullable=True),
        sa.Column("titulo", sa.Text(), nullable=False),
        sa.Column("autor", sa.Text(), nullable=True),
        sa.Column("ano_publicacion", sa.Integer(), nullable=True),
        sa.Column("materia", sa.String(100), nullable=True),
        sa.Column("editorial", sa.Text(), nullable=True),
        sa.Column("cota", sa.String(100), nullable=True),
        sa.Column("marc_json", postgresql.JSONB(), nullable=False),
        sa.Column("plantilla", sa.String(10), nullable=False, server_default="BKS"),
        sa.Column("busqueda", postgresql.TSVECTOR(),
                  sa.Computed(EXPRESION, persisted=True)),
        sa.Column("creado_en", FECHA, nullable=False, server_default=_ahora()),
        sa.Column("actualizado_en", FECHA, nullable=False, server_default=_ahora()),
    )
    op.create_index("ix_registros_bibliograficos_id", "registros_bibliograficos", ["id"])
    op.create_index("ix_registros_busqueda", "registros_bibliograficos", ["busqueda"],
                    postgresql_using="gin")

    op.create_table(
        "items",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("biblio_id", sa.Integer(),
                  sa.ForeignKey("registros_bibliograficos.id", ondelete="CASCADE"),
                  nullable=False),
        sa.Column("codigo_barras", sa.String(50), nullable=True),
        sa.Column("signatura_topografica", sa.String(100), nullable=True),
        sa.Column("numero_copia", sa.String(20), nullable=True),
        sa.Column("nota", sa.Text(), nullable=True),
        sa.Column("creado_en", FECHA, nullable=False, server_default=_ahora()),
    )
    op.create_index("ix_items_id", "items", ["id"])
    op.create_index("ix_items_biblio_id", "items", ["biblio_id"])
    op.create_index("ux_items_codigo_barras", "items", ["codigo_barras"], unique=True,
                    postgresql_where=sa.text("codigo_barras IS NOT NULL"))

    op.create_table(
        "configuraciones",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("clave", sa.String(50), nullable=False),
        sa.Column("valor", postgresql.JSONB(), nullable=False),
        sa.Column("actualizado_en", FECHA, nullable=True),
    )
    op.create_index("ix_configuraciones_id", "configuraciones", ["id"])
    op.create_index("ix_configuraciones_clave", "configuraciones", ["clave"], unique=True)

    op.create_table(
        "ejecuciones_tarea",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("tarea", sa.String(40), nullable=False),
        sa.Column("inicio", FECHA, nullable=False),
        sa.Column("fin", FECHA, nullable=True),
        sa.Column("ok", sa.Boolean(), nullable=True),
        sa.Column("resultado", postgresql.JSONB(), nullable=True),
        sa.Column("error", sa.Text(), nullable=True),
        sa.Column("origen", sa.String(20), nullable=False, server_default="automatica"),
    )
    op.create_index("ix_ejecuciones_tarea_id", "ejecuciones_tarea", ["id"])
    op.create_index("ix_ejecuciones_tarea_tarea", "ejecuciones_tarea", ["tarea"])

    op.create_table(
        "sesiones_cerradas",
        sa.Column("jti", sa.String(32), primary_key=True),
        sa.Column("expira", FECHA, nullable=False),
    )
    op.create_index("ix_sesiones_cerradas_expira", "sesiones_cerradas", ["expira"])

    op.create_table(
        "intentos_acceso",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("identificador", sa.String(100), nullable=False),
        sa.Column("ip", sa.String(64), nullable=True),
        sa.Column("fecha", FECHA, nullable=False),
    )
    op.create_index("ix_intentos_acceso_id", "intentos_acceso", ["id"])
    op.create_index("ix_intentos_acceso_identificador", "intentos_acceso", ["identificador"])
    op.create_index("ix_intentos_acceso_ip", "intentos_acceso", ["ip"])

    op.create_table(
        "registro_acciones",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("fecha", FECHA, nullable=False),
        sa.Column("usuario_id", sa.Integer(),
                  sa.ForeignKey("usuarios.id", ondelete="SET NULL"), nullable=True),
        sa.Column("modulo", sa.String(20), nullable=False),
        sa.Column("accion", sa.String(30), nullable=False),
        sa.Column("descripcion", sa.Text(), nullable=False),
        sa.Column("lector_id", sa.Integer(),
                  sa.ForeignKey("usuarios.id", ondelete="SET NULL"), nullable=True),
        sa.Column("biblio_id", sa.Integer(),
                  sa.ForeignKey("registros_bibliograficos.id", ondelete="SET NULL"),
                  nullable=True),
        sa.Column("item_id", sa.Integer(), sa.ForeignKey("items.id", ondelete="SET NULL"),
                  nullable=True),
        sa.Column("objeto_tipo", sa.String(30), nullable=True),
        sa.Column("objeto_id", sa.Integer(), nullable=True),
        sa.Column("datos", postgresql.JSONB(), nullable=True),
        sa.Column("ip", sa.String(64), nullable=True),
    )
    for columna in ("fecha", "usuario_id", "lector_id", "biblio_id", "item_id"):
        op.create_index(f"ix_registro_acciones_{columna}", "registro_acciones", [columna])
    op.create_index("ix_registro_acciones_modulo_fecha", "registro_acciones",
                    ["modulo", "fecha"])


def downgrade() -> None:
    # Las tablas que referencian a otras van primero; los índices caen con su tabla.
    for tabla in ("registro_acciones", "intentos_acceso", "sesiones_cerradas",
                  "ejecuciones_tarea", "configuraciones", "items",
                  "registros_bibliograficos", "usuarios"):
        op.drop_table(tabla)
    op.execute("DROP TEXT SEARCH CONFIGURATION IF EXISTS shelfie_es")
    # La extensión se deja: otra cosa en la base podría estar usándola.
