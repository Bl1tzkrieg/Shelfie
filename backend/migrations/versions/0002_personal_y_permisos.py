"""Personal y permisos (Fase 2)

Marca qué usuarios son personal de la biblioteca, guarda sus permisos por módulo
y registra quién del personal hizo cada préstamo y cada devolución.

personal y permisos

Revision ID: 0002_personal
Revises: 0001_base
Create Date: 2026-10-06 11:08:58.522309

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = '0002_personal'
down_revision: Union[str, None] = '0001_base'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('prestamos', sa.Column('personal_prestamo_id', sa.Integer(), nullable=True))
    op.add_column('prestamos', sa.Column('personal_devolucion_id', sa.Integer(), nullable=True))
    op.create_foreign_key('fk_prestamos_personal_prestamo', 'prestamos', 'usuarios', ['personal_prestamo_id'], ['id'])
    op.create_foreign_key('fk_prestamos_personal_devolucion', 'prestamos', 'usuarios', ['personal_devolucion_id'], ['id'])
    op.add_column('usuarios', sa.Column('es_personal', sa.Boolean(), server_default=sa.text('false'), nullable=False))
    op.add_column('usuarios', sa.Column('permisos', postgresql.JSONB(astext_type=sa.Text()), server_default=sa.text("'[]'::jsonb"), nullable=False))


def downgrade() -> None:
    op.drop_column('usuarios', 'permisos')
    op.drop_column('usuarios', 'es_personal')
    op.drop_constraint('fk_prestamos_personal_devolucion', 'prestamos', type_='foreignkey')
    op.drop_constraint('fk_prestamos_personal_prestamo', 'prestamos', type_='foreignkey')
    op.drop_column('prestamos', 'personal_devolucion_id')
    op.drop_column('prestamos', 'personal_prestamo_id')
