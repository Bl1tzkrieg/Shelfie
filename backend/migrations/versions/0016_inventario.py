"""Fase 8: inventario

- `inventarios` y `inventario_lecturas`: pasadas de inventario por sede y tramo de
  signaturas, con cada código leído y su resultado (Inventory de Koha).
- `items.fecha_ultimo_inventario`: la última vez que se leyó el ejemplar (datelastseen).

Revision ID: 0016_inventario
Revises: 0015_registro_acciones
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0016_inventario"
down_revision: Union[str, None] = "0015_registro_acciones"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("items", sa.Column("fecha_ultimo_inventario", sa.DateTime(timezone=True),
                                     nullable=True))
    op.create_table(
        "inventarios",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("nombre", sa.String(length=120), nullable=False),
        sa.Column("biblioteca_id", sa.Integer(),
                  sa.ForeignKey("bibliotecas.id", ondelete="SET NULL"), nullable=True),
        sa.Column("tipo_item_id", sa.Integer(),
                  sa.ForeignKey("tipos_item.id", ondelete="SET NULL"), nullable=True),
        sa.Column("signatura_desde", sa.String(length=100), nullable=True),
        sa.Column("signatura_hasta", sa.String(length=100), nullable=True),
        sa.Column("devolver_prestados", sa.Boolean(), nullable=False,
                  server_default=sa.text("false")),
        sa.Column("estado", sa.String(length=20), nullable=False, server_default="Abierto"),
        sa.Column("creado_por_id", sa.Integer(),
                  sa.ForeignKey("usuarios.id", ondelete="SET NULL"), nullable=True),
        sa.Column("fecha_inicio", sa.DateTime(timezone=True), nullable=False),
        sa.Column("fecha_cierre", sa.DateTime(timezone=True), nullable=True),
        sa.Column("resumen", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
    )
    op.create_table(
        "inventario_lecturas",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("inventario_id", sa.Integer(),
                  sa.ForeignKey("inventarios.id", ondelete="CASCADE"), nullable=False),
        sa.Column("codigo_barras", sa.String(length=50), nullable=False),
        sa.Column("item_id", sa.Integer(), sa.ForeignKey("items.id", ondelete="SET NULL"),
                  nullable=True),
        sa.Column("resultado", sa.String(length=20), nullable=False),
        sa.Column("detalle", sa.Text(), nullable=True),
        sa.Column("usuario_id", sa.Integer(),
                  sa.ForeignKey("usuarios.id", ondelete="SET NULL"), nullable=True),
        sa.Column("fecha", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_inventario_lecturas_inventario_id", "inventario_lecturas",
                    ["inventario_id"])
    op.create_index("ix_inventario_lecturas_inventario_item", "inventario_lecturas",
                    ["inventario_id", "item_id"])


def downgrade() -> None:
    op.drop_index("ix_inventario_lecturas_inventario_item", table_name="inventario_lecturas")
    op.drop_index("ix_inventario_lecturas_inventario_id", table_name="inventario_lecturas")
    op.drop_table("inventario_lecturas")
    op.drop_table("inventarios")
    op.drop_column("items", "fecha_ultimo_inventario")
