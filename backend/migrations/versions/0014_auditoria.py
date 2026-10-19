"""Correcciones de la auditoría (octubre 2026)

- Índices únicos parciales: un ejemplar no puede tener dos préstamos abiertos, ni
  apartarse para dos reservas a la vez. Si la base ya tiene casos así, la migración se
  detiene y los lista para corregirlos a mano antes de seguir.
- `usuarios.debe_cambiar_clave`: la contraseña la puso otro (alta, restablecimiento) y al
  entrar se pide elegir una propia.
- `intentos_acceso`: intentos fallidos de entrar, para frenar a quien prueba contraseñas.
- `sesiones_cerradas`: tokens cerrados con «Salir», que ya no valen aunque no hayan vencido.

Revision ID: 0014_auditoria
Revises: 0013_avisos
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0014_auditoria"
down_revision: Union[str, None] = "0013_avisos"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_PRESTAMOS_DOBLES = """
    SELECT i.codigo_barras, count(*) FROM prestamos p JOIN items i ON i.id = p.item_id
    WHERE p.fecha_devolucion IS NULL GROUP BY i.codigo_barras HAVING count(*) > 1
"""
_RESERVAS_DOBLES = """
    SELECT i.codigo_barras, count(*) FROM reservas r JOIN items i ON i.id = r.item_id
    WHERE r.estado IN ('EnEspera', 'EnTransito') GROUP BY i.codigo_barras HAVING count(*) > 1
"""


def _verificar(consulta: str, que: str) -> None:
    filas = op.get_bind().execute(sa.text(consulta)).fetchall()
    if filas:
        lista = ", ".join(f"{codigo} ({n})" for codigo, n in filas)
        raise RuntimeError(
            f"Hay ejemplares con {que}: {lista}. Corrígelos (devuelve o cancela los "
            "duplicados) y vuelve a correr `alembic upgrade head`.")


def upgrade() -> None:
    _verificar(_PRESTAMOS_DOBLES, "más de un préstamo abierto")
    _verificar(_RESERVAS_DOBLES, "más de una reserva apartada")
    op.create_index("ux_prestamos_item_abierto", "prestamos", ["item_id"], unique=True,
                    postgresql_where=sa.text("fecha_devolucion IS NULL"))
    op.create_index("ux_reservas_item_asignado", "reservas", ["item_id"], unique=True,
                    postgresql_where=sa.text(
                        "item_id IS NOT NULL AND estado IN ('EnEspera', 'EnTransito')"))

    op.add_column("usuarios", sa.Column("debe_cambiar_clave", sa.Boolean(), nullable=False,
                                        server_default=sa.text("false")))

    op.create_table(
        "intentos_acceso",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("identificador", sa.String(length=100), nullable=False),
        sa.Column("ip", sa.String(length=64), nullable=True),
        sa.Column("fecha", sa.DateTime(timezone=True), nullable=False),
    )
    for columna in ("id", "identificador", "ip"):
        op.create_index(f"ix_intentos_acceso_{columna}", "intentos_acceso", [columna])

    op.create_table(
        "sesiones_cerradas",
        sa.Column("jti", sa.String(length=32), primary_key=True),
        sa.Column("expira", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_sesiones_cerradas_expira", "sesiones_cerradas", ["expira"])


def downgrade() -> None:
    op.drop_index("ix_sesiones_cerradas_expira", table_name="sesiones_cerradas")
    op.drop_table("sesiones_cerradas")
    for columna in ("ip", "identificador", "id"):
        op.drop_index(f"ix_intentos_acceso_{columna}", table_name="intentos_acceso")
    op.drop_table("intentos_acceso")
    op.drop_column("usuarios", "debe_cambiar_clave")
    op.drop_index("ux_reservas_item_asignado", table_name="reservas")
    op.drop_index("ux_prestamos_item_abierto", table_name="prestamos")
