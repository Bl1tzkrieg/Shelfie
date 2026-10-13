"""Condonaciones que apuntan a un cargo concreto

`movimientos_cuenta.cargo_id`: el débito (multa, reposición) al que se aplica un
crédito. Así, si se condona la reposición de un ejemplar perdido y después aparece,
el reintegro descuenta lo condonado (antes se acreditaba completo).

Revision ID: 0011_cargo_de_movimiento
Revises: 0010_seriadas
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0011_cargo_de_movimiento"
down_revision: Union[str, None] = "0010_seriadas"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("movimientos_cuenta", sa.Column(
        "cargo_id", sa.Integer(), sa.ForeignKey("movimientos_cuenta.id", ondelete="SET NULL"),
        nullable=True))
    op.create_index("ix_movimientos_cuenta_cargo_id", "movimientos_cuenta", ["cargo_id"])


def downgrade() -> None:
    op.drop_index("ix_movimientos_cuenta_cargo_id", table_name="movimientos_cuenta")
    op.drop_column("movimientos_cuenta", "cargo_id")
