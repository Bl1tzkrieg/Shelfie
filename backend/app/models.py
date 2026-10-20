from sqlalchemy import (Boolean, Column, Computed, DateTime, ForeignKey, Index, Integer, String,
                        Text, text)
from sqlalchemy.dialects.postgresql import JSONB, TSVECTOR
from app.core.tiempo import ahora
from app.database import Base


class Usuario(Base):
    """Un miembro del personal. El rol sale de `permisos` (ver app/core/permisos.py)."""
    __tablename__ = "usuarios"
    id = Column(Integer, primary_key=True, index=True)
    username = Column(String(50), unique=True, nullable=False)
    password_hash = Column(String(255), nullable=False)
    nombre = Column(String(100), nullable=False)
    apellido = Column(String(100), nullable=False)
    email = Column(String(100), nullable=True)
    activo = Column(Boolean, nullable=False, default=True, server_default=text("true"))
    permisos = Column(JSONB, nullable=False, default=list, server_default=text("'[]'::jsonb"))
    # La contraseña la puso otro (alta o restablecimiento por el administrador): al
    # entrar se pide elegir una propia.
    debe_cambiar_clave = Column(Boolean, nullable=False, default=False,
                                server_default=text("false"))
    fecha_creacion = Column(DateTime(timezone=True), nullable=False, default=ahora,
                            server_default=text("now()"))


# Texto que indexa la búsqueda. `shelfie_es` = español sin acentos (migración 0001_lite).
EXPRESION_BUSQUEDA = (
    "setweight(to_tsvector('shelfie_es'::regconfig, coalesce(titulo, '')), 'A') || "
    "setweight(to_tsvector('shelfie_es'::regconfig, coalesce(autor, '')), 'B') || "
    "setweight(to_tsvector('shelfie_es'::regconfig, coalesce(materia, '')), 'C') || "
    "setweight(to_tsvector('shelfie_es'::regconfig, coalesce(editorial, '')), 'C') || "
    "setweight(to_tsvector('simple'::regconfig, coalesce(isbn, '')), 'D') || "
    "setweight(to_tsvector('simple'::regconfig, coalesce(cota, '')), 'D')"
)


class RegistroBibliografico(Base):
    __tablename__ = "registros_bibliograficos"
    __table_args__ = (
        Index("ix_registros_busqueda", "busqueda", postgresql_using="gin"),
    )
    id = Column(Integer, primary_key=True, index=True)
    isbn = Column(String(20), nullable=True)
    titulo = Column(Text, nullable=False)
    autor = Column(Text, nullable=True)
    ano_publicacion = Column(Integer, nullable=True)
    materia = Column(String(100), nullable=True)
    editorial = Column(Text, nullable=True)
    # Cota del título (092 $a + $b), normalizada con core.signaturas.normalizar_cota.
    cota = Column(String(100), nullable=True)
    # Registro MARC21 (MARC-in-JSON). Es la fuente: las columnas de arriba se derivan
    # de él al guardar (app/services/marc.py).
    marc_json = Column(JSONB, nullable=False)
    plantilla = Column(String(10), nullable=False, default="BKS", server_default="BKS")
    # Lo calcula PostgreSQL; no se escribe desde la aplicación.
    busqueda = Column(TSVECTOR, Computed(EXPRESION_BUSQUEDA, persisted=True))
    creado_en = Column(DateTime(timezone=True), nullable=False, default=ahora,
                       server_default=text("now()"))
    actualizado_en = Column(DateTime(timezone=True), nullable=False, default=ahora,
                            onupdate=ahora, server_default=text("now()"))


class Item(Base):
    """Un ejemplar (952 de Koha). El código de barras es opcional, pero único si existe."""
    __tablename__ = "items"
    __table_args__ = (
        Index("ux_items_codigo_barras", "codigo_barras", unique=True,
              postgresql_where=text("codigo_barras IS NOT NULL")),
    )
    id = Column(Integer, primary_key=True, index=True)
    biblio_id = Column(Integer, ForeignKey("registros_bibliograficos.id", ondelete="CASCADE"),
                       nullable=False, index=True)
    codigo_barras = Column(String(50), nullable=True)          # 952 $p
    signatura_topografica = Column(String(100), nullable=True)  # 952 $o
    numero_copia = Column(String(20), nullable=True)            # 952 $t («c.1», «c.2»…)
    nota = Column(Text, nullable=True)                          # 952 $z
    creado_en = Column(DateTime(timezone=True), nullable=False, default=ahora,
                       server_default=text("now()"))


class Configuracion(Base):
    """Ajustes del sistema guardados como pares clave/valor JSON."""
    __tablename__ = "configuraciones"
    id = Column(Integer, primary_key=True, index=True)
    clave = Column(String(50), unique=True, nullable=False, index=True)
    valor = Column(JSONB, nullable=False)
    actualizado_en = Column(DateTime(timezone=True), default=ahora)


class EjecucionTarea(Base):
    """Registro de cada corrida de una tarea programada (cuándo, qué hizo, si falló)."""
    __tablename__ = "ejecuciones_tarea"
    id = Column(Integer, primary_key=True, index=True)
    tarea = Column(String(40), nullable=False, index=True)
    inicio = Column(DateTime(timezone=True), nullable=False, default=ahora)
    fin = Column(DateTime(timezone=True), nullable=True)
    ok = Column(Boolean, nullable=True)
    resultado = Column(JSONB, nullable=True)
    error = Column(Text, nullable=True)
    origen = Column(String(20), nullable=False, default="automatica",
                    server_default="automatica")  # automatica, manual, consola


class SesionCerrada(Base):
    """Tokens de sesión cerrados con «Salir»: dejan de valer aunque no hayan expirado.
    Se guardan hasta su vencimiento; la tarea de limpieza borra los vencidos."""
    __tablename__ = "sesiones_cerradas"
    jti = Column(String(32), primary_key=True)
    expira = Column(DateTime(timezone=True), nullable=False, index=True)


class IntentoAcceso(Base):
    """Intentos de entrar fallidos, para frenar a quien prueba contraseñas (FailedLoginAttempts)."""
    __tablename__ = "intentos_acceso"
    id = Column(Integer, primary_key=True, index=True)
    identificador = Column(String(100), nullable=False, index=True)
    ip = Column(String(64), nullable=True, index=True)
    fecha = Column(DateTime(timezone=True), nullable=False, default=ahora)


class RegistroAccion(Base):
    """Registro de acciones (action_logs de Koha): quién hizo qué, cuándo y sobre qué.

    `usuario_id` es quien actuó (NULL = el sistema, p. ej. una tarea programada).
    `lector_id` es el usuario del personal afectado (alta, rol, clave), y `biblio_id` e
    `item_id` el registro y el ejemplar, para ver el historial de una ficha. `datos`
    guarda el detalle (antes/después).
    """
    __tablename__ = "registro_acciones"
    __table_args__ = (
        Index("ix_registro_acciones_modulo_fecha", "modulo", "fecha"),
    )
    id = Column(Integer, primary_key=True)
    fecha = Column(DateTime(timezone=True), nullable=False, default=ahora, index=True)
    usuario_id = Column(Integer, ForeignKey("usuarios.id", ondelete="SET NULL"), nullable=True,
                        index=True)
    modulo = Column(String(20), nullable=False)
    accion = Column(String(30), nullable=False)
    descripcion = Column(Text, nullable=False)
    lector_id = Column(Integer, ForeignKey("usuarios.id", ondelete="SET NULL"), nullable=True,
                       index=True)
    biblio_id = Column(Integer, ForeignKey("registros_bibliograficos.id", ondelete="SET NULL"),
                       nullable=True, index=True)
    item_id = Column(Integer, ForeignKey("items.id", ondelete="SET NULL"), nullable=True,
                     index=True)
    objeto_tipo = Column(String(30), nullable=True)
    objeto_id = Column(Integer, nullable=True)
    datos = Column(JSONB, nullable=True)
    ip = Column(String(64), nullable=True)
