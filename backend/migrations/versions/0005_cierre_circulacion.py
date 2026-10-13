"""Cierre de la Fase 3: columnas obsoletas y préstamos perdidos

- `categorias_usuario` pierde `max_prestamos`, `dias_prestamo` y `multa_por_dia`:
  desde la 0004 esas políticas viven en `reglas_circulacion` y nadie las lee.
- `prestamos.perdido` marca el préstamo que terminó en pérdida. Antes se deducía
  del estado actual del ejemplar, que cambia si aparece y vuelve a prestarse.
  Se rellena con los préstamos que tienen un cargo de REPOSICION.

Al bajar, las columnas de la categoría se recuperan desde su regla propia (o la
general si no tiene).

Revision ID: 0005_cierre_circulacion
Revises: 0004_nucleo_circulacion
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0005_cierre_circulacion"
down_revision: Union[str, None] = "0004_nucleo_circulacion"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

COLUMNAS_OBSOLETAS = ("max_prestamos", "dias_prestamo", "multa_por_dia")


def upgrade() -> None:
    op.add_column("prestamos", sa.Column("perdido", sa.Boolean(), nullable=False,
                                         server_default=sa.text("false")))
    op.execute("""
        UPDATE prestamos SET perdido = true
        WHERE id IN (SELECT prestamo_id FROM movimientos_cuenta
                     WHERE tipo = 'REPOSICION' AND prestamo_id IS NOT NULL)
    """)
    for columna in COLUMNAS_OBSOLETAS:
        op.drop_column("categorias_usuario", columna)


def downgrade() -> None:
    op.add_column("categorias_usuario", sa.Column("max_prestamos", sa.Integer(), nullable=True))
    op.add_column("categorias_usuario", sa.Column("dias_prestamo", sa.Integer(), nullable=True))
    op.add_column("categorias_usuario",
                  sa.Column("multa_por_dia", sa.Numeric(precision=10, scale=2), nullable=True))
    op.execute("""
        UPDATE categorias_usuario c SET
            max_prestamos = COALESCE(propia.max_prestamos, general.max_prestamos, 3),
            dias_prestamo = COALESCE(propia.dias_prestamo, general.dias_prestamo, 7),
            multa_por_dia = COALESCE(propia.multa_por_dia, general.multa_por_dia, 1.5)
        FROM categorias_usuario c2
        LEFT JOIN reglas_circulacion propia
               ON propia.categoria_id = c2.id AND propia.tipo_item_id IS NULL
              AND propia.biblioteca_id IS NULL
        LEFT JOIN reglas_circulacion general
               ON general.categoria_id IS NULL AND general.tipo_item_id IS NULL
              AND general.biblioteca_id IS NULL
        WHERE c2.id = c.id
    """)
    for columna in COLUMNAS_OBSOLETAS:
        op.alter_column("categorias_usuario", columna, nullable=False)
    op.drop_column("prestamos", "perdido")
