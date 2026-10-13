"""Fase 5: sedes, gestión de reservas y traslados entre sedes

- `bibliotecas` gana datos de contacto y `punto_retiro` (si se pueden retirar
  reservas allí, como el "pickup location" de Koha).
- `reservas` gana suspensión (con fecha de reanudación opcional), fecha límite
  ("ya no lo necesito después de…") y notas. Suma el estado EnTransito.
- `traslados`: movimiento de un ejemplar entre sedes, por una reserva, por el
  retorno a su sede propia o a mano. Solicitado → Enviado → Recibido | Cancelado.

Revision ID: 0008_reservas_y_traslados
Revises: 0007_marc
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0008_reservas_y_traslados"
down_revision: Union[str, None] = "0007_marc"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("bibliotecas", sa.Column("direccion", sa.Text(), nullable=True))
    op.add_column("bibliotecas", sa.Column("telefono", sa.String(length=50), nullable=True))
    op.add_column("bibliotecas", sa.Column("email", sa.String(length=100), nullable=True))
    op.add_column("bibliotecas", sa.Column("punto_retiro", sa.Boolean(), nullable=False,
                                           server_default=sa.text("true")))

    op.add_column("reservas", sa.Column("suspendida", sa.Boolean(), nullable=False,
                                        server_default=sa.text("false")))
    op.add_column("reservas", sa.Column("suspendida_hasta", sa.Date(), nullable=True))
    op.add_column("reservas", sa.Column("fecha_limite", sa.Date(), nullable=True))
    op.add_column("reservas", sa.Column("notas", sa.Text(), nullable=True))

    op.create_table(
        "traslados",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("item_id", sa.Integer(), sa.ForeignKey("items.id", ondelete="CASCADE"),
                  nullable=False),
        sa.Column("desde_id", sa.Integer(), sa.ForeignKey("bibliotecas.id"), nullable=False),
        sa.Column("hacia_id", sa.Integer(), sa.ForeignKey("bibliotecas.id"), nullable=False),
        sa.Column("motivo", sa.String(length=20), nullable=False),
        sa.Column("estado", sa.String(length=20), nullable=False),
        sa.Column("reserva_id", sa.Integer(), sa.ForeignKey("reservas.id", ondelete="SET NULL"),
                  nullable=True),
        sa.Column("comentario", sa.Text(), nullable=True),
        sa.Column("fecha_solicitud", sa.DateTime(timezone=True), nullable=False,
                  server_default=sa.text("now()")),
        sa.Column("fecha_envio", sa.DateTime(timezone=True), nullable=True),
        sa.Column("fecha_recepcion", sa.DateTime(timezone=True), nullable=True),
        sa.Column("fecha_cancelacion", sa.DateTime(timezone=True), nullable=True),
        sa.Column("personal_envio_id", sa.Integer(), sa.ForeignKey("usuarios.id"), nullable=True),
        sa.Column("personal_recepcion_id", sa.Integer(), sa.ForeignKey("usuarios.id"),
                  nullable=True),
    )
    op.create_index("ix_traslados_id", "traslados", ["id"])
    op.create_index("ix_traslados_item_id", "traslados", ["item_id"])
    op.create_index("ix_traslados_estado", "traslados", ["estado"])


def downgrade() -> None:
    op.drop_index("ix_traslados_estado", table_name="traslados")
    op.drop_index("ix_traslados_item_id", table_name="traslados")
    op.drop_index("ix_traslados_id", table_name="traslados")
    op.drop_table("traslados")
    # Lo que estaba en camino vuelve a la cola o al estante: la 0007 no conoce el tránsito.
    op.execute("UPDATE reservas SET estado = 'Pendiente', item_id = NULL "
               "WHERE estado = 'EnTransito'")
    op.execute("UPDATE items SET estado = 'Disponible' WHERE estado = 'EnTransito'")
    for columna in ("notas", "fecha_limite", "suspendida_hasta", "suspendida"):
        op.drop_column("reservas", columna)
    for columna in ("punto_retiro", "email", "telefono", "direccion"):
        op.drop_column("bibliotecas", columna)
