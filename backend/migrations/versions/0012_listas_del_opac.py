"""Fase 6: listas de los lectores en el OPAC

- `listas`: nombre, dueño (lector) y si es pública (cualquiera la ve con el enlace).
- `listas_registros`: los títulos de cada lista.

Revision ID: 0012_listas_del_opac
Revises: 0011_cargo_de_movimiento
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0012_listas_del_opac"
down_revision: Union[str, None] = "0011_cargo_de_movimiento"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "listas",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("usuario_id", sa.Integer(),
                  sa.ForeignKey("usuarios.id", ondelete="CASCADE"), nullable=False),
        sa.Column("nombre", sa.String(length=100), nullable=False),
        sa.Column("publica", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("fecha_creacion", sa.DateTime(timezone=True), nullable=False,
                  server_default=sa.text("now()")),
    )
    op.create_index("ix_listas_id", "listas", ["id"])
    op.create_index("ix_listas_usuario_id", "listas", ["usuario_id"])
    op.create_table(
        "listas_registros",
        sa.Column("lista_id", sa.Integer(), sa.ForeignKey("listas.id", ondelete="CASCADE"),
                  primary_key=True),
        sa.Column("biblio_id", sa.Integer(),
                  sa.ForeignKey("registros_bibliograficos.id", ondelete="CASCADE"),
                  primary_key=True),
        sa.Column("fecha", sa.DateTime(timezone=True), nullable=False,
                  server_default=sa.text("now()")),
    )


def downgrade() -> None:
    op.drop_table("listas_registros")
    op.drop_index("ix_listas_usuario_id", table_name="listas")
    op.drop_index("ix_listas_id", table_name="listas")
    op.drop_table("listas")
