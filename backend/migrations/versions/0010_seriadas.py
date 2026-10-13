"""Fase 5: publicaciones seriadas al estilo de Koha

- `suscripciones`: registro del catálogo (SER), sede que recibe, tipo de ítem de los
  ejemplares y **patrón de predicción**: cada cuánto sale (unidad + cada N) y cómo se
  numera ("Vol. {X}, Núm. {Y}", con N números por volumen). Días de gracia para
  reclamar y notas. `periodicidad` (texto libre) se convierte al patrón.
- `fasciculos`: estado (Esperado, Recibido, Reclamado, Faltante), los contadores de
  volumen y número que generaron su rótulo, reclamos y el ejemplar creado al recibirlo.
- `items.enumeracion`: rótulo del fascículo en el ejemplar (952 $h de Koha).

Revision ID: 0010_seriadas
Revises: 0009_adquisiciones
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0010_seriadas"
down_revision: Union[str, None] = "0009_adquisiciones"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# periodicidad (texto) → (unidad, cada)
EQUIVALENCIAS = {
    "Diaria": ("dia", 1), "Semanal": ("semana", 1), "Quincenal": ("semana", 2),
    "Mensual": ("mes", 1), "Bimestral": ("mes", 2), "Trimestral": ("mes", 3),
    "Semestral": ("mes", 6), "Anual": ("anio", 1),
}


def upgrade() -> None:
    S = "suscripciones"
    op.add_column(S, sa.Column("biblio_id", sa.Integer(),
                               sa.ForeignKey("registros_bibliograficos.id", ondelete="SET NULL"),
                               nullable=True))
    op.add_column(S, sa.Column("biblioteca_id", sa.Integer(), sa.ForeignKey("bibliotecas.id"),
                               nullable=True))
    op.add_column(S, sa.Column("tipo_item_id", sa.Integer(), sa.ForeignKey("tipos_item.id"),
                               nullable=True))
    op.add_column(S, sa.Column("crear_ejemplares", sa.Boolean(), nullable=False,
                               server_default=sa.text("true")))
    op.add_column(S, sa.Column("frecuencia_unidad", sa.String(length=10), nullable=False,
                               server_default="mes"))
    op.add_column(S, sa.Column("frecuencia_cada", sa.Integer(), nullable=False,
                               server_default="1"))
    op.add_column(S, sa.Column("numeracion", sa.String(length=100), nullable=False,
                               server_default="Núm. {Y}"))
    op.add_column(S, sa.Column("numeros_por_volumen", sa.Integer(), nullable=True))
    op.add_column(S, sa.Column("dias_gracia", sa.Integer(), nullable=False, server_default="15"))
    op.add_column(S, sa.Column("notas", sa.Text(), nullable=True))
    for texto, (unidad, cada) in EQUIVALENCIAS.items():
        op.execute(sa.text(f"UPDATE {S} SET frecuencia_unidad = :u, frecuencia_cada = :c "
                           "WHERE periodicidad = :p").bindparams(u=unidad, c=cada, p=texto))
    op.drop_column(S, "periodicidad")

    F = "fasciculos"
    op.add_column(F, sa.Column("estado", sa.String(length=20), nullable=False,
                               server_default="Esperado"))
    op.add_column(F, sa.Column("volumen", sa.Integer(), nullable=True))
    op.add_column(F, sa.Column("secuencia", sa.Integer(), nullable=True))
    op.add_column(F, sa.Column("reclamos", sa.Integer(), nullable=False, server_default="0"))
    op.add_column(F, sa.Column("fecha_reclamo", sa.DateTime(timezone=True), nullable=True))
    op.add_column(F, sa.Column("notas", sa.Text(), nullable=True))
    op.add_column(F, sa.Column("item_id", sa.Integer(),
                               sa.ForeignKey("items.id", ondelete="SET NULL"), nullable=True))
    op.execute(f"UPDATE {F} SET estado = 'Recibido' WHERE recibido")
    op.create_index("ix_fasciculos_suscripcion_id", F, ["suscripcion_id"])
    op.create_index("ix_fasciculos_estado", F, ["estado"])

    op.add_column("items", sa.Column("enumeracion", sa.String(length=100), nullable=True))


def downgrade() -> None:
    op.drop_column("items", "enumeracion")
    F = "fasciculos"
    op.drop_index("ix_fasciculos_estado", table_name=F)
    op.drop_index("ix_fasciculos_suscripcion_id", table_name=F)
    for columna in ("item_id", "notas", "fecha_reclamo", "reclamos", "secuencia", "volumen",
                    "estado"):
        op.drop_column(F, columna)

    S = "suscripciones"
    op.add_column(S, sa.Column("periodicidad", sa.String(length=20), nullable=False,
                               server_default="Mensual"))
    for texto, (unidad, cada) in EQUIVALENCIAS.items():
        op.execute(sa.text(f"UPDATE {S} SET periodicidad = :p "
                           "WHERE frecuencia_unidad = :u AND frecuencia_cada = :c")
                   .bindparams(u=unidad, c=cada, p=texto))
    for columna in ("notas", "dias_gracia", "numeros_por_volumen", "numeracion",
                    "frecuencia_cada", "frecuencia_unidad", "crear_ejemplares", "tipo_item_id",
                    "biblioteca_id", "biblio_id"):
        op.drop_column(S, columna)
