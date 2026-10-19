"""Fase 7: avisos por correo y tareas programadas

- `avisos`: la cola de correos (message_queue de Koha). Cada aviso se arma con su
  plantilla al ocurrir el hecho y lo envía la tarea de la cola; `clave` impide
  encolar dos veces el mismo aviso.
- `tokens_clave`: enlaces de un solo uso para recuperar la contraseña (solo el hash).
- `ejecuciones_tarea`: cuándo corrió cada tarea programada y qué hizo.

Revision ID: 0013_avisos
Revises: 0012_listas_del_opac
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0013_avisos"
down_revision: Union[str, None] = "0012_listas_del_opac"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "avisos",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("codigo", sa.String(length=30), nullable=False),
        sa.Column("usuario_id", sa.Integer(), sa.ForeignKey("usuarios.id", ondelete="CASCADE"),
                  nullable=True),
        sa.Column("proveedor_id", sa.Integer(),
                  sa.ForeignKey("proveedores.id", ondelete="CASCADE"), nullable=True),
        sa.Column("destinatario", sa.String(length=200), nullable=False),
        sa.Column("asunto", sa.String(length=300), nullable=False),
        sa.Column("cuerpo", sa.Text(), nullable=False),
        sa.Column("estado", sa.String(length=20), nullable=False, server_default="Pendiente"),
        sa.Column("intentos", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("error", sa.Text(), nullable=True),
        sa.Column("clave", sa.String(length=120), nullable=True, unique=True),
        sa.Column("fecha_creacion", sa.DateTime(timezone=True), nullable=False,
                  server_default=sa.text("now()")),
        sa.Column("fecha_envio", sa.DateTime(timezone=True), nullable=True),
    )
    for columna in ("id", "codigo", "usuario_id", "estado"):
        op.create_index(f"ix_avisos_{columna}", "avisos", [columna])

    op.create_table(
        "tokens_clave",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("usuario_id", sa.Integer(), sa.ForeignKey("usuarios.id", ondelete="CASCADE"),
                  nullable=False),
        sa.Column("token_hash", sa.String(length=64), nullable=False, unique=True),
        sa.Column("fecha_creacion", sa.DateTime(timezone=True), nullable=False,
                  server_default=sa.text("now()")),
        sa.Column("expira", sa.DateTime(timezone=True), nullable=False),
        sa.Column("usado", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_tokens_clave_id", "tokens_clave", ["id"])
    op.create_index("ix_tokens_clave_usuario_id", "tokens_clave", ["usuario_id"])

    op.create_table(
        "ejecuciones_tarea",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("tarea", sa.String(length=40), nullable=False),
        sa.Column("inicio", sa.DateTime(timezone=True), nullable=False),
        sa.Column("fin", sa.DateTime(timezone=True), nullable=True),
        sa.Column("ok", sa.Boolean(), nullable=True),
        sa.Column("resultado", postgresql.JSONB(), nullable=True),
        sa.Column("error", sa.Text(), nullable=True),
        sa.Column("origen", sa.String(length=20), nullable=False, server_default="automatica"),
    )
    op.create_index("ix_ejecuciones_tarea_id", "ejecuciones_tarea", ["id"])
    op.create_index("ix_ejecuciones_tarea_tarea", "ejecuciones_tarea", ["tarea"])


def downgrade() -> None:
    op.drop_index("ix_ejecuciones_tarea_tarea", table_name="ejecuciones_tarea")
    op.drop_index("ix_ejecuciones_tarea_id", table_name="ejecuciones_tarea")
    op.drop_table("ejecuciones_tarea")
    op.drop_index("ix_tokens_clave_usuario_id", table_name="tokens_clave")
    op.drop_index("ix_tokens_clave_id", table_name="tokens_clave")
    op.drop_table("tokens_clave")
    for columna in ("estado", "usuario_id", "codigo", "id"):
        op.drop_index(f"ix_avisos_{columna}", table_name="avisos")
    op.drop_table("avisos")
