"""Fase 8: registro de acciones

- `registro_acciones`: quién hizo qué y cuándo (action_logs de Koha). Circulación,
  reservas, cobros, lectores y permisos, catálogo, configuración, sesiones,
  adquisiciones y seriadas. Lo que se registra se elige por módulo en Configuración.

Revision ID: 0015_registro_acciones
Revises: 0014_auditoria
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0015_registro_acciones"
down_revision: Union[str, None] = "0014_auditoria"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "registro_acciones",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("fecha", sa.DateTime(timezone=True), nullable=False),
        sa.Column("usuario_id", sa.Integer(),
                  sa.ForeignKey("usuarios.id", ondelete="SET NULL"), nullable=True),
        sa.Column("desde_opac", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("modulo", sa.String(length=20), nullable=False),
        sa.Column("accion", sa.String(length=30), nullable=False),
        sa.Column("descripcion", sa.Text(), nullable=False),
        sa.Column("lector_id", sa.Integer(),
                  sa.ForeignKey("usuarios.id", ondelete="SET NULL"), nullable=True),
        sa.Column("biblio_id", sa.Integer(),
                  sa.ForeignKey("registros_bibliograficos.id", ondelete="SET NULL"), nullable=True),
        sa.Column("item_id", sa.Integer(),
                  sa.ForeignKey("items.id", ondelete="SET NULL"), nullable=True),
        sa.Column("objeto_tipo", sa.String(length=30), nullable=True),
        sa.Column("objeto_id", sa.Integer(), nullable=True),
        sa.Column("datos", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("ip", sa.String(length=64), nullable=True),
        sa.Column("sede_id", sa.Integer(),
                  sa.ForeignKey("bibliotecas.id", ondelete="SET NULL"), nullable=True),
    )
    for columna in ("fecha", "usuario_id", "lector_id", "biblio_id", "item_id"):
        op.create_index(f"ix_registro_acciones_{columna}", "registro_acciones", [columna])
    op.create_index("ix_registro_acciones_modulo_fecha", "registro_acciones", ["modulo", "fecha"])


def downgrade() -> None:
    op.drop_index("ix_registro_acciones_modulo_fecha", table_name="registro_acciones")
    for columna in ("item_id", "biblio_id", "lector_id", "usuario_id", "fecha"):
        op.drop_index(f"ix_registro_acciones_{columna}", table_name="registro_acciones")
    op.drop_table("registro_acciones")
