"""Fase 5: adquisiciones al estilo de Koha

- `proveedores`: RIF, dirección, descuento habitual, días de entrega y notas.
- `presupuestos` (períodos) y `fondos`: de dónde sale el dinero de cada pedido.
- `ordenes_compra` pasan a ser pedidos (las "cestas" de Koha): Abierta → Cerrada
  (enviada al proveedor) → Recibida | Cancelada. Las órdenes viejas en
  "Pendiente" ya se habían emitido: pasan a Cerrada.
- `lineas_orden`: registro del catálogo, fondo, descuento, costo estimado,
  cantidad recibida y estado propio (Pendiente, Parcial, Recibida, Cancelada).
- `facturas` y `recepciones`: se recibe contra una factura del proveedor, en
  parciales, al costo real. Cada ejemplar recibido recuerda su recepción.
- `sugerencias` de compra del personal o de los lectores.

Revision ID: 0009_adquisiciones
Revises: 0008_reservas_y_traslados
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0009_adquisiciones"
down_revision: Union[str, None] = "0008_reservas_y_traslados"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

DINERO = sa.Numeric(precision=12, scale=2)


def upgrade() -> None:
    # --- Proveedores
    op.add_column("proveedores", sa.Column("rif", sa.String(length=20), nullable=True))
    op.add_column("proveedores", sa.Column("direccion", sa.Text(), nullable=True))
    op.add_column("proveedores", sa.Column("descuento", sa.Numeric(precision=5, scale=2),
                                           nullable=False, server_default="0"))
    op.add_column("proveedores", sa.Column("dias_entrega", sa.Integer(), nullable=True))
    op.add_column("proveedores", sa.Column("notas", sa.Text(), nullable=True))

    # --- Presupuestos y fondos
    op.create_table(
        "presupuestos",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("nombre", sa.String(length=100), nullable=False),
        sa.Column("fecha_inicio", sa.Date(), nullable=False),
        sa.Column("fecha_fin", sa.Date(), nullable=False),
        sa.Column("monto_total", DINERO, nullable=False),
        sa.Column("activo", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("bloqueado", sa.Boolean(), nullable=False, server_default=sa.text("false")),
    )
    op.create_index("ix_presupuestos_id", "presupuestos", ["id"])
    op.create_table(
        "fondos",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("presupuesto_id", sa.Integer(),
                  sa.ForeignKey("presupuestos.id", ondelete="CASCADE"), nullable=False),
        sa.Column("codigo", sa.String(length=20), nullable=False),
        sa.Column("nombre", sa.String(length=100), nullable=False),
        sa.Column("monto_asignado", DINERO, nullable=False),
        sa.Column("biblioteca_id", sa.Integer(), sa.ForeignKey("bibliotecas.id"), nullable=True),
        sa.Column("activo", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.UniqueConstraint("presupuesto_id", "codigo", name="uq_fondo_codigo_por_presupuesto"),
    )
    op.create_index("ix_fondos_id", "fondos", ["id"])
    op.create_index("ix_fondos_presupuesto_id", "fondos", ["presupuesto_id"])

    # --- Pedidos (cestas)
    op.add_column("ordenes_compra", sa.Column("nombre", sa.String(length=100), nullable=True))
    op.add_column("ordenes_compra", sa.Column("fecha_cierre", sa.DateTime(timezone=True),
                                              nullable=True))
    op.add_column("ordenes_compra", sa.Column("biblioteca_entrega_id", sa.Integer(),
                                              sa.ForeignKey("bibliotecas.id"), nullable=True))
    op.add_column("ordenes_compra", sa.Column("creado_por_id", sa.Integer(),
                                              sa.ForeignKey("usuarios.id"), nullable=True))
    op.execute("UPDATE ordenes_compra SET estado = 'Cerrada', fecha_cierre = fecha_emision "
               "WHERE estado = 'Pendiente' OR estado IS NULL")

    # --- Líneas
    op.add_column("lineas_orden", sa.Column("biblio_id", sa.Integer(),
                                            sa.ForeignKey("registros_bibliograficos.id",
                                                          ondelete="SET NULL"), nullable=True))
    op.add_column("lineas_orden", sa.Column("fondo_id", sa.Integer(),
                                            sa.ForeignKey("fondos.id"), nullable=True))
    op.add_column("lineas_orden", sa.Column("descuento", sa.Numeric(precision=5, scale=2),
                                            nullable=False, server_default="0"))
    op.add_column("lineas_orden", sa.Column("costo_estimado", sa.Numeric(precision=10, scale=2),
                                            nullable=True))
    op.add_column("lineas_orden", sa.Column("cantidad_recibida", sa.Integer(), nullable=False,
                                            server_default="0"))
    op.add_column("lineas_orden", sa.Column("estado", sa.String(length=20), nullable=False,
                                            server_default="Pendiente"))
    op.add_column("lineas_orden", sa.Column("notas", sa.Text(), nullable=True))
    op.execute("UPDATE lineas_orden SET costo_estimado = precio_unitario")
    op.alter_column("lineas_orden", "costo_estimado", nullable=False)
    # Las órdenes ya recibidas recibieron todo.
    op.execute("""
        UPDATE lineas_orden l SET cantidad_recibida = l.cantidad, estado = 'Recibida'
        FROM ordenes_compra o WHERE o.id = l.orden_id AND o.estado = 'Recibida'
    """)
    op.execute("""
        UPDATE lineas_orden l SET estado = 'Cancelada'
        FROM ordenes_compra o WHERE o.id = l.orden_id AND o.estado = 'Cancelada'
    """)
    # Las líneas recibidas por la versión anterior encuentran su registro por los
    # códigos de barras que esa versión les ponía (OC0001-L001-01…).
    op.execute("""
        UPDATE lineas_orden l SET biblio_id = i.biblio_id
        FROM items i
        WHERE i.codigo_barras LIKE 'OC' || lpad(l.orden_id::text, 4, '0') || '-L'
                                     || lpad(l.id::text, 3, '0') || '-%'
    """)

    # --- Facturas y recepciones
    op.create_table(
        "facturas",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("proveedor_id", sa.Integer(), sa.ForeignKey("proveedores.id"), nullable=False),
        sa.Column("numero", sa.String(length=50), nullable=False),
        sa.Column("fecha", sa.Date(), nullable=False),
        sa.Column("costo_envio", DINERO, nullable=False, server_default="0"),
        sa.Column("fondo_envio_id", sa.Integer(), sa.ForeignKey("fondos.id"), nullable=True),
        sa.Column("cerrada", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("fecha_cierre", sa.DateTime(timezone=True), nullable=True),
        sa.Column("notas", sa.Text(), nullable=True),
        sa.UniqueConstraint("proveedor_id", "numero", name="uq_factura_numero_por_proveedor"),
    )
    op.create_index("ix_facturas_id", "facturas", ["id"])
    op.create_table(
        "recepciones",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("linea_id", sa.Integer(), sa.ForeignKey("lineas_orden.id", ondelete="CASCADE"),
                  nullable=False),
        sa.Column("factura_id", sa.Integer(), sa.ForeignKey("facturas.id"), nullable=True),
        sa.Column("cantidad", sa.Integer(), nullable=False),
        sa.Column("costo_unitario", sa.Numeric(precision=10, scale=2), nullable=False),
        sa.Column("fecha", sa.DateTime(timezone=True), nullable=False,
                  server_default=sa.text("now()")),
        sa.Column("personal_id", sa.Integer(), sa.ForeignKey("usuarios.id"), nullable=True),
    )
    op.create_index("ix_recepciones_id", "recepciones", ["id"])
    op.create_index("ix_recepciones_linea_id", "recepciones", ["linea_id"])
    op.create_index("ix_recepciones_factura_id", "recepciones", ["factura_id"])
    op.add_column("items", sa.Column("recepcion_id", sa.Integer(),
                                     sa.ForeignKey("recepciones.id", ondelete="SET NULL"),
                                     nullable=True))

    # --- Sugerencias
    op.create_table(
        "sugerencias",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("titulo", sa.Text(), nullable=False),
        sa.Column("autor", sa.Text(), nullable=True),
        sa.Column("isbn", sa.String(length=20), nullable=True),
        sa.Column("editorial", sa.String(length=150), nullable=True),
        sa.Column("ano", sa.Integer(), nullable=True),
        sa.Column("nota", sa.Text(), nullable=True),
        sa.Column("usuario_id", sa.Integer(), sa.ForeignKey("usuarios.id"), nullable=True),
        sa.Column("estado", sa.String(length=20), nullable=False, server_default="Pendiente"),
        sa.Column("motivo", sa.Text(), nullable=True),
        sa.Column("fecha", sa.DateTime(timezone=True), nullable=False,
                  server_default=sa.text("now()")),
        sa.Column("gestionada_por_id", sa.Integer(), sa.ForeignKey("usuarios.id"), nullable=True),
        sa.Column("fecha_gestion", sa.DateTime(timezone=True), nullable=True),
        sa.Column("linea_id", sa.Integer(), sa.ForeignKey("lineas_orden.id", ondelete="SET NULL"),
                  nullable=True),
    )
    op.create_index("ix_sugerencias_id", "sugerencias", ["id"])
    op.create_index("ix_sugerencias_estado", "sugerencias", ["estado"])


def downgrade() -> None:
    op.drop_index("ix_sugerencias_estado", table_name="sugerencias")
    op.drop_index("ix_sugerencias_id", table_name="sugerencias")
    op.drop_table("sugerencias")
    op.drop_column("items", "recepcion_id")
    for indice in ("ix_recepciones_factura_id", "ix_recepciones_linea_id", "ix_recepciones_id"):
        op.drop_index(indice, table_name="recepciones")
    op.drop_table("recepciones")
    op.drop_index("ix_facturas_id", table_name="facturas")
    op.drop_table("facturas")

    for columna in ("notas", "estado", "cantidad_recibida", "costo_estimado", "descuento",
                    "fondo_id", "biblio_id"):
        op.drop_column("lineas_orden", columna)
    # La 0008 solo conoce Pendiente, Recibida y Cancelada.
    op.execute("UPDATE ordenes_compra SET estado = 'Pendiente' "
               "WHERE estado IN ('Abierta', 'Cerrada')")
    for columna in ("creado_por_id", "biblioteca_entrega_id", "fecha_cierre", "nombre"):
        op.drop_column("ordenes_compra", columna)

    op.drop_index("ix_fondos_presupuesto_id", table_name="fondos")
    op.drop_index("ix_fondos_id", table_name="fondos")
    op.drop_table("fondos")
    op.drop_index("ix_presupuestos_id", table_name="presupuestos")
    op.drop_table("presupuestos")

    for columna in ("notas", "dias_entrega", "descuento", "direccion", "rif"):
        op.drop_column("proveedores", columna)
