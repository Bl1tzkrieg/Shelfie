"""Fechas con zona horaria (Fase 3)

Las columnas de fecha/hora pasan de TIMESTAMP a TIMESTAMPTZ. Hasta ahora la
aplicación guardaba UTC sin zona, así que los valores existentes se
reinterpretan explícitamente como UTC: no cambia ningún instante.

Revision ID: 0003_zona_horaria
Revises: 0002_personal
"""
from typing import Sequence, Union

from alembic import op

revision: str = "0003_zona_horaria"
down_revision: Union[str, None] = "0002_personal"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

COLUMNAS = [
    ("usuarios", "fecha_creacion"),
    ("prestamos", "fecha_prestamo"),
    ("prestamos", "fecha_vencimiento"),
    ("prestamos", "fecha_devolucion"),
    ("configuraciones", "actualizado_en"),
    ("ordenes_compra", "fecha_emision"),
    ("ordenes_compra", "fecha_recepcion"),
    ("fasciculos", "fecha_recepcion"),
]


def upgrade() -> None:
    for tabla, columna in COLUMNAS:
        op.execute(
            f'ALTER TABLE {tabla} ALTER COLUMN {columna} TYPE TIMESTAMPTZ '
            f"USING {columna} AT TIME ZONE 'UTC'"
        )


def downgrade() -> None:
    for tabla, columna in COLUMNAS:
        op.execute(
            f'ALTER TABLE {tabla} ALTER COLUMN {columna} TYPE TIMESTAMP '
            f"USING {columna} AT TIME ZONE 'UTC'"
        )
