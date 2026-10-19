"""Núcleo de circulación (Fase 3)

- Sede por defecto y sede en ejemplares, préstamos, reservas y lectores.
- Reglas de circulación (categoría × tipo de ítem × sede), creadas a partir de
  lo que hoy dicen `categorias_usuario` y la configuración.
- Calendario de feriados.
- Ciclo completo de reservas (fechas, ejemplar apartado, expiración).
- Cuentas del lector: `movimientos_cuenta` reemplaza a `multas`. Las multas
  existentes se migran como débitos y, si `usuarios.saldo_multas` no coincidía
  con ellas, la diferencia queda como un AJUSTE para no perder ningún saldo.

Nota: `multas` se elimina a mano porque migrations/env.py ignora las tablas que
no están en models.py (para no tocar tablas ajenas) y por eso autogenerate no
detecta su eliminación.

Revision ID: 0004_nucleo_circulacion
Revises: 0003_zona_horaria
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0004_nucleo_circulacion"
down_revision: Union[str, None] = "0003_zona_horaria"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

RENOVACIONES_POR_DEFECTO = 2
MULTA_POR_DEFECTO = 1.5


def _crear_esquema() -> None:
    op.create_table(
        "feriados",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("fecha", sa.Date(), nullable=False),
        sa.Column("descripcion", sa.String(length=150), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("fecha"),
    )
    op.create_index(op.f("ix_feriados_id"), "feriados", ["id"], unique=False)

    op.create_table(
        "reglas_circulacion",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("categoria_id", sa.Integer(), nullable=True),
        sa.Column("tipo_item_id", sa.Integer(), nullable=True),
        sa.Column("biblioteca_id", sa.Integer(), nullable=True),
        sa.Column("prestable", sa.Boolean(), nullable=False),
        sa.Column("dias_prestamo", sa.Integer(), nullable=False),
        sa.Column("max_prestamos", sa.Integer(), nullable=False),
        sa.Column("max_renovaciones", sa.Integer(), nullable=False),
        sa.Column("multa_por_dia", sa.Numeric(precision=10, scale=2), nullable=False),
        sa.Column("multa_maxima", sa.Numeric(precision=10, scale=2), nullable=True),
        sa.Column("dias_gracia", sa.Integer(), nullable=False),
        sa.Column("max_reservas", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(["biblioteca_id"], ["bibliotecas.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["categoria_id"], ["categorias_usuario.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["tipo_item_id"], ["tipos_item.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("categoria_id", "tipo_item_id", "biblioteca_id",
                            name="uq_regla_combinacion", postgresql_nulls_not_distinct=True),
    )
    op.create_index(op.f("ix_reglas_circulacion_id"), "reglas_circulacion", ["id"], unique=False)

    op.create_table(
        "movimientos_cuenta",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("usuario_id", sa.Integer(), nullable=False),
        sa.Column("tipo", sa.String(length=20), nullable=False),
        sa.Column("monto", sa.Numeric(precision=10, scale=2), nullable=False),
        sa.Column("prestamo_id", sa.Integer(), nullable=True),
        sa.Column("descripcion", sa.Text(), nullable=True),
        sa.Column("fecha", sa.DateTime(timezone=True), nullable=False),
        sa.Column("personal_id", sa.Integer(), nullable=True),
        sa.ForeignKeyConstraint(["personal_id"], ["usuarios.id"]),
        sa.ForeignKeyConstraint(["prestamo_id"], ["prestamos.id"]),
        sa.ForeignKeyConstraint(["usuario_id"], ["usuarios.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_movimientos_cuenta_id"), "movimientos_cuenta", ["id"], unique=False)
    op.create_index(op.f("ix_movimientos_cuenta_usuario_id"), "movimientos_cuenta",
                    ["usuario_id"], unique=False)

    op.add_column("items", sa.Column("biblioteca_propia_id", sa.Integer(), nullable=True))
    op.add_column("items", sa.Column("biblioteca_actual_id", sa.Integer(), nullable=True))
    op.add_column("items", sa.Column("precio_reposicion", sa.Numeric(precision=10, scale=2),
                                     nullable=True))
    op.create_foreign_key("fk_items_biblioteca_propia", "items", "bibliotecas",
                          ["biblioteca_propia_id"], ["id"])
    op.create_foreign_key("fk_items_biblioteca_actual", "items", "bibliotecas",
                          ["biblioteca_actual_id"], ["id"])

    op.add_column("prestamos", sa.Column("biblioteca_id", sa.Integer(), nullable=True))
    op.create_foreign_key("fk_prestamos_biblioteca", "prestamos", "bibliotecas",
                          ["biblioteca_id"], ["id"])

    op.add_column("reservas", sa.Column("fecha_reserva", sa.DateTime(timezone=True),
                                        server_default=sa.text("now()"), nullable=True))
    op.add_column("reservas", sa.Column("biblioteca_retiro_id", sa.Integer(), nullable=True))
    op.add_column("reservas", sa.Column("item_id", sa.Integer(), nullable=True))
    op.add_column("reservas", sa.Column("fecha_en_espera", sa.DateTime(timezone=True), nullable=True))
    op.add_column("reservas", sa.Column("fecha_expiracion", sa.DateTime(timezone=True), nullable=True))
    op.add_column("reservas", sa.Column("fecha_cierre", sa.DateTime(timezone=True), nullable=True))
    op.create_foreign_key("fk_reservas_item", "reservas", "items", ["item_id"], ["id"])
    op.create_foreign_key("fk_reservas_biblioteca_retiro", "reservas", "bibliotecas",
                          ["biblioteca_retiro_id"], ["id"])

    op.add_column("usuarios", sa.Column("biblioteca_id", sa.Integer(), nullable=True))
    op.create_foreign_key("fk_usuarios_biblioteca", "usuarios", "bibliotecas",
                          ["biblioteca_id"], ["id"])


def _migrar_datos() -> None:
    conexion = op.get_bind()

    # 1. Sede por defecto: la primera existente o una nueva "Biblioteca Principal".
    sede = conexion.execute(sa.text("SELECT id FROM bibliotecas ORDER BY id LIMIT 1")).scalar()
    if sede is None:
        sede = conexion.execute(sa.text(
            "INSERT INTO bibliotecas (codigo, nombre) VALUES ('PRINC', 'Biblioteca Principal') "
            "RETURNING id")).scalar()
    conexion.execute(sa.text(
        "UPDATE items SET biblioteca_propia_id = :s, biblioteca_actual_id = :s"), {"s": sede})
    conexion.execute(sa.text("UPDATE prestamos SET biblioteca_id = :s"), {"s": sede})
    conexion.execute(sa.text("UPDATE usuarios SET biblioteca_id = :s"), {"s": sede})
    conexion.execute(sa.text("UPDATE reservas SET biblioteca_retiro_id = :s"), {"s": sede})

    # 2. Reglas: una por categoría (con sus días/tope/multa) y una general.
    politicas = conexion.execute(sa.text(
        "SELECT valor FROM configuraciones WHERE clave = 'politicas_prestamo'")).scalar() or {}
    renovaciones = int(politicas.get("renovaciones_permitidas", RENOVACIONES_POR_DEFECTO))
    multa_general = float(politicas.get("multa_por_dia", MULTA_POR_DEFECTO))

    conexion.execute(sa.text("""
        INSERT INTO reglas_circulacion
            (categoria_id, tipo_item_id, biblioteca_id, prestable, dias_prestamo, max_prestamos,
             max_renovaciones, multa_por_dia, multa_maxima, dias_gracia, max_reservas)
        VALUES (NULL, NULL, NULL, true, 7, 3, :r, :m, NULL, 0, 5)
    """), {"r": renovaciones, "m": multa_general})
    conexion.execute(sa.text("""
        INSERT INTO reglas_circulacion
            (categoria_id, tipo_item_id, biblioteca_id, prestable, dias_prestamo, max_prestamos,
             max_renovaciones, multa_por_dia, multa_maxima, dias_gracia, max_reservas)
        SELECT id, NULL, NULL, true, dias_prestamo, max_prestamos, :r, multa_por_dia, NULL, 0, 5
        FROM categorias_usuario
    """), {"r": renovaciones})
    # Tipos de ítem marcados como no prestables: regla explícita que lo impide.
    conexion.execute(sa.text("""
        INSERT INTO reglas_circulacion
            (categoria_id, tipo_item_id, biblioteca_id, prestable, dias_prestamo, max_prestamos,
             max_renovaciones, multa_por_dia, multa_maxima, dias_gracia, max_reservas)
        SELECT NULL, id, NULL, false, 0, 0, 0, 0, NULL, 0, 0
        FROM tipos_item WHERE es_prestable = false
    """))

    # 3. Reservas: estados del nuevo ciclo y fecha de reserva aproximada.
    conexion.execute(sa.text(
        "UPDATE reservas SET estado = 'Cumplida' WHERE estado = 'Completada'"))
    conexion.execute(sa.text(
        "UPDATE reservas SET fecha_cierre = now() WHERE estado IN ('Cumplida', 'Cancelada')"))

    # 4. Cuentas: multas → débitos; diferencias de saldo → ajuste.
    conexion.execute(sa.text("""
        INSERT INTO movimientos_cuenta (usuario_id, tipo, monto, prestamo_id, descripcion, fecha)
        SELECT usuario_id, 'MULTA_ATRASO', monto, prestamo_id,
               'Multa por atraso (migrada)', now()
        FROM multas WHERE usuario_id IS NOT NULL
    """))
    conexion.execute(sa.text("""
        INSERT INTO movimientos_cuenta (usuario_id, tipo, monto, descripcion, fecha)
        SELECT u.id, 'AJUSTE', COALESCE(u.saldo_multas, 0) - COALESCE(m.total, 0),
               'Saldo previo a la Fase 3 sin detalle de origen', now()
        FROM usuarios u
        LEFT JOIN (SELECT usuario_id, SUM(monto) AS total FROM multas GROUP BY usuario_id) m
               ON m.usuario_id = u.id
        WHERE COALESCE(u.saldo_multas, 0) <> COALESCE(m.total, 0)
    """))
    op.drop_table("multas")


def upgrade() -> None:
    _crear_esquema()
    _migrar_datos()


def downgrade() -> None:
    # Se reconstruye `multas` con los débitos por atraso. Pagos y condonaciones no
    # tienen equivalente en el esquema anterior: el saldo de cada lector se conserva
    # en usuarios.saldo_multas, que es lo que el esquema anterior consultaba.
    op.create_table(
        "multas",
        sa.Column("id", sa.Integer(), primary_key=True, index=True),
        sa.Column("prestamo_id", sa.Integer(), sa.ForeignKey("prestamos.id")),
        sa.Column("usuario_id", sa.Integer(), sa.ForeignKey("usuarios.id")),
        sa.Column("monto", sa.Numeric(10, 2), nullable=False),
        sa.Column("estado_pago", sa.String(20), server_default="Pendiente"),
    )
    op.execute("""
        INSERT INTO multas (prestamo_id, usuario_id, monto)
        SELECT prestamo_id, usuario_id, monto FROM movimientos_cuenta WHERE tipo = 'MULTA_ATRASO'
    """)
    op.execute("UPDATE reservas SET estado = 'Completada' WHERE estado = 'Cumplida'")
    # El esquema anterior no conoce «EnEspera» ni «Expirada»: la apartada vuelve a pendiente
    # y la expirada queda cancelada.
    op.execute("UPDATE reservas SET estado = 'Pendiente' WHERE estado = 'EnEspera'")
    op.execute("UPDATE reservas SET estado = 'Cancelada' WHERE estado = 'Expirada'")

    op.drop_constraint("fk_usuarios_biblioteca", "usuarios", type_="foreignkey")
    op.drop_column("usuarios", "biblioteca_id")
    op.drop_constraint("fk_reservas_biblioteca_retiro", "reservas", type_="foreignkey")
    op.drop_constraint("fk_reservas_item", "reservas", type_="foreignkey")
    for columna in ("fecha_cierre", "fecha_expiracion", "fecha_en_espera", "item_id",
                    "biblioteca_retiro_id", "fecha_reserva"):
        op.drop_column("reservas", columna)
    op.drop_constraint("fk_prestamos_biblioteca", "prestamos", type_="foreignkey")
    op.drop_column("prestamos", "biblioteca_id")
    op.drop_constraint("fk_items_biblioteca_actual", "items", type_="foreignkey")
    op.drop_constraint("fk_items_biblioteca_propia", "items", type_="foreignkey")
    for columna in ("precio_reposicion", "biblioteca_actual_id", "biblioteca_propia_id"):
        op.drop_column("items", columna)
    op.drop_index(op.f("ix_movimientos_cuenta_usuario_id"), table_name="movimientos_cuenta")
    op.drop_index(op.f("ix_movimientos_cuenta_id"), table_name="movimientos_cuenta")
    op.drop_table("movimientos_cuenta")
    op.drop_index(op.f("ix_reglas_circulacion_id"), table_name="reglas_circulacion")
    op.drop_table("reglas_circulacion")
    op.drop_index(op.f("ix_feriados_id"), table_name="feriados")
    op.drop_table("feriados")
