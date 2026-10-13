from sqlalchemy import (Boolean, Column, Computed, Date, DateTime, ForeignKey, Index, Integer,
                        Numeric, String, Text, UniqueConstraint, text)
from sqlalchemy.dialects.postgresql import JSONB, TSVECTOR
from sqlalchemy.orm import relationship
from app.core.tiempo import ahora
from app.database import Base

class Biblioteca(Base):
    __tablename__ = "bibliotecas"
    id = Column(Integer, primary_key=True, index=True)
    codigo = Column(String(10), unique=True, nullable=False)
    nombre = Column(String(100), nullable=False)
    direccion = Column(Text, nullable=True)
    telefono = Column(String(50), nullable=True)
    email = Column(String(100), nullable=True)
    # Se pueden retirar reservas aquí ("pickup location" de Koha).
    punto_retiro = Column(Boolean, nullable=False, default=True, server_default=text("true"))

class CategoriaUsuario(Base):
    __tablename__ = "categorias_usuario"
    id = Column(Integer, primary_key=True, index=True)
    codigo = Column(String(10), unique=True, nullable=False)
    descripcion = Column(String(50), nullable=False)
    # Las políticas de préstamo de cada categoría viven en ReglaCirculacion.

class Usuario(Base):
    __tablename__ = "usuarios"
    id = Column(Integer, primary_key=True, index=True)
    nro_carnet = Column(String(50), unique=True, nullable=False, index=True)
    username = Column(String(50), unique=True, nullable=False)
    password_hash = Column(String(255), nullable=False)
    nombre = Column(String(100), nullable=False)
    apellido = Column(String(100), nullable=False)
    email = Column(String(100), nullable=False, unique=True)
    categoria_id = Column(Integer, ForeignKey("categorias_usuario.id"))
    departamento = Column(String(100), nullable=True)
    saldo_multas = Column(Numeric(10, 2), default=0.00)
    activo = Column(Boolean, default=True)
    fecha_creacion = Column(DateTime(timezone=True), default=ahora)
    # Personal de la biblioteca (acceso a la intranet) y sus permisos por módulo.
    biblioteca_id = Column(Integer, ForeignKey("bibliotecas.id"), nullable=True)  # sede de inscripción
    es_personal = Column(Boolean, nullable=False, default=False, server_default=text("false"))
    permisos = Column(JSONB, nullable=False, default=list, server_default=text("'[]'::jsonb"))

# Texto que indexa la búsqueda. `shelfie_es` = español sin acentos (migración 0006).
EXPRESION_BUSQUEDA = (
    "setweight(to_tsvector('shelfie_es'::regconfig, coalesce(titulo, '')), 'A') || "
    "setweight(to_tsvector('shelfie_es'::regconfig, coalesce(autor, '')), 'B') || "
    "setweight(to_tsvector('shelfie_es'::regconfig, coalesce(materia, '')), 'C') || "
    "setweight(to_tsvector('simple'::regconfig, coalesce(isbn, '')), 'D')"
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
    # Registro MARC21 (MARC-in-JSON). Es la fuente: titulo, autor, materia, año e ISBN
    # se derivan de él al guardar (app/services/marc.py).
    marc_json = Column(JSONB, nullable=False)
    plantilla = Column(String(10), nullable=False, default="BKS", server_default="BKS")
    # Lo calcula PostgreSQL; no se escribe desde la aplicación.
    busqueda = Column(TSVECTOR, Computed(EXPRESION_BUSQUEDA, persisted=True))

class TipoItem(Base):
    __tablename__ = "tipos_item"
    id = Column(Integer, primary_key=True, index=True)
    codigo = Column(String(10), unique=True, nullable=False, index=True)
    descripcion = Column(String(100), nullable=False)
    es_prestable = Column(Boolean, default=True)

class Item(Base):
    __tablename__ = "items"
    id = Column(Integer, primary_key=True, index=True)
    biblio_id = Column(Integer, ForeignKey("registros_bibliograficos.id", ondelete="CASCADE"))
    codigo_barras = Column(String(50), unique=True, nullable=False, index=True)
    tipo_item_id = Column(Integer, ForeignKey("tipos_item.id"))
    signatura_topografica = Column(String(100), nullable=True)  # Clasificación Dewey/LC
    # Disponible, Prestado, Reservado (apartado para una reserva en espera), Perdido,
    # EnTransito (viaja entre sedes; ver Traslado)
    estado = Column(String(20), default="Disponible")
    biblioteca_propia_id = Column(Integer, ForeignKey("bibliotecas.id"), nullable=True)
    biblioteca_actual_id = Column(Integer, ForeignKey("bibliotecas.id"), nullable=True)
    precio_reposicion = Column(Numeric(10, 2), nullable=True)
    # Recepción de adquisiciones que lo dio de alta (si vino de un pedido).
    recepcion_id = Column(Integer, ForeignKey("recepciones.id", ondelete="SET NULL"), nullable=True)
    # Rótulo del fascículo cuando el ejemplar es un número de una seriada (952 $h).
    enumeracion = Column(String(100), nullable=True)

class Prestamo(Base):
    __tablename__ = "prestamos"
    id = Column(Integer, primary_key=True, index=True)
    item_id = Column(Integer, ForeignKey("items.id"))
    usuario_id = Column(Integer, ForeignKey("usuarios.id"))
    fecha_prestamo = Column(DateTime(timezone=True), default=ahora)
    fecha_vencimiento = Column(DateTime(timezone=True), nullable=False)
    fecha_devolucion = Column(DateTime(timezone=True), nullable=True)
    renovaciones_realizadas = Column(Integer, default=0)
    # Quién del personal registró el préstamo y la devolución.
    personal_prestamo_id = Column(Integer, ForeignKey("usuarios.id"), nullable=True)
    personal_devolucion_id = Column(Integer, ForeignKey("usuarios.id"), nullable=True)
    biblioteca_id = Column(Integer, ForeignKey("bibliotecas.id"), nullable=True)
    # El préstamo terminó con el ejemplar declarado perdido (aunque luego aparezca).
    perdido = Column(Boolean, nullable=False, default=False, server_default=text("false"))

class Reserva(Base):
    """Reserva de un título (hold). Ciclo: Pendiente → [EnTransito →] EnEspera → Cumplida.

    Mientras está activa puede pasar a Cancelada, y a Expirada si el lector no
    retira el ejemplar a tiempo o si vence su fecha límite estando pendiente.
    """
    __tablename__ = "reservas"
    id = Column(Integer, primary_key=True, index=True)
    biblio_id = Column(Integer, ForeignKey("registros_bibliograficos.id"))
    usuario_id = Column(Integer, ForeignKey("usuarios.id"))
    prioridad = Column(Integer, nullable=False)  # turno entre las pendientes (1 = siguiente)
    estado = Column(String(20), default="Pendiente")
    fecha_reserva = Column(DateTime(timezone=True), default=ahora, server_default=text("now()"))
    biblioteca_retiro_id = Column(Integer, ForeignKey("bibliotecas.id"), nullable=True)
    # Ejemplar apartado cuando la reserva pasa a EnEspera.
    item_id = Column(Integer, ForeignKey("items.id"), nullable=True)
    fecha_en_espera = Column(DateTime(timezone=True), nullable=True)
    fecha_expiracion = Column(DateTime(timezone=True), nullable=True)
    fecha_cierre = Column(DateTime(timezone=True), nullable=True)
    # Suspendida: conserva su turno pero no recibe ejemplares. Sin fecha, hasta reanudarla.
    suspendida = Column(Boolean, nullable=False, default=False, server_default=text("false"))
    suspendida_hasta = Column(Date, nullable=True)
    # El lector ya no lo necesita después de esta fecha (expira si sigue pendiente).
    fecha_limite = Column(Date, nullable=True)
    notas = Column(Text, nullable=True)


class Traslado(Base):
    """Un ejemplar que viaja entre sedes. Solicitado → Enviado → Recibido | Cancelado.

    Motivo: `reserva` (va a la sede de retiro), `retorno` (vuelve a su sede propia)
    o `manual` (lo pidió el personal).
    """
    __tablename__ = "traslados"
    id = Column(Integer, primary_key=True, index=True)
    item_id = Column(Integer, ForeignKey("items.id", ondelete="CASCADE"), nullable=False,
                     index=True)
    desde_id = Column(Integer, ForeignKey("bibliotecas.id"), nullable=False)
    hacia_id = Column(Integer, ForeignKey("bibliotecas.id"), nullable=False)
    motivo = Column(String(20), nullable=False)
    estado = Column(String(20), nullable=False, index=True)
    reserva_id = Column(Integer, ForeignKey("reservas.id", ondelete="SET NULL"), nullable=True)
    comentario = Column(Text, nullable=True)
    fecha_solicitud = Column(DateTime(timezone=True), nullable=False, default=ahora,
                             server_default=text("now()"))
    fecha_envio = Column(DateTime(timezone=True), nullable=True)
    fecha_recepcion = Column(DateTime(timezone=True), nullable=True)
    fecha_cancelacion = Column(DateTime(timezone=True), nullable=True)
    personal_envio_id = Column(Integer, ForeignKey("usuarios.id"), nullable=True)
    personal_recepcion_id = Column(Integer, ForeignKey("usuarios.id"), nullable=True)


class ReglaCirculacion(Base):
    """Política de préstamo para una combinación categoría × tipo de ítem × sede.

    NULL en una dimensión significa "cualquiera". Se aplica la regla más
    específica que coincida (ver app/services/reglas.py), como en Koha.
    """
    __tablename__ = "reglas_circulacion"
    __table_args__ = (
        UniqueConstraint("categoria_id", "tipo_item_id", "biblioteca_id",
                         name="uq_regla_combinacion", postgresql_nulls_not_distinct=True),
    )
    id = Column(Integer, primary_key=True, index=True)
    categoria_id = Column(Integer, ForeignKey("categorias_usuario.id", ondelete="CASCADE"),
                          nullable=True)
    tipo_item_id = Column(Integer, ForeignKey("tipos_item.id", ondelete="CASCADE"), nullable=True)
    biblioteca_id = Column(Integer, ForeignKey("bibliotecas.id", ondelete="CASCADE"), nullable=True)
    prestable = Column(Boolean, nullable=False, default=True)
    dias_prestamo = Column(Integer, nullable=False)
    max_prestamos = Column(Integer, nullable=False)
    max_renovaciones = Column(Integer, nullable=False)
    multa_por_dia = Column(Numeric(10, 2), nullable=False)
    multa_maxima = Column(Numeric(10, 2), nullable=True)  # tope por préstamo; NULL = sin tope
    dias_gracia = Column(Integer, nullable=False, default=0)
    max_reservas = Column(Integer, nullable=False, default=5)


class Feriado(Base):
    """Día cerrado puntual. Los días cerrados de cada semana van en Configuración."""
    __tablename__ = "feriados"
    id = Column(Integer, primary_key=True, index=True)
    fecha = Column(Date, nullable=False, unique=True)
    descripcion = Column(String(150), nullable=False)


class MovimientoCuenta(Base):
    """Libro de la cuenta del lector (accountlines de Koha).

    Débitos con monto positivo (multas, reposiciones), créditos con monto
    negativo (pagos, condonaciones). El saldo es la suma; `usuarios.saldo_multas`
    guarda una copia para consultas rápidas.
    """
    __tablename__ = "movimientos_cuenta"
    id = Column(Integer, primary_key=True, index=True)
    usuario_id = Column(Integer, ForeignKey("usuarios.id"), nullable=False, index=True)
    # Débitos: MULTA_ATRASO, REPOSICION, AJUSTE. Créditos: PAGO, CONDONACION, REINTEGRO
    tipo = Column(String(20), nullable=False)
    monto = Column(Numeric(10, 2), nullable=False)
    prestamo_id = Column(Integer, ForeignKey("prestamos.id"), nullable=True)
    descripcion = Column(Text, nullable=True)
    fecha = Column(DateTime(timezone=True), nullable=False, default=ahora)
    personal_id = Column(Integer, ForeignKey("usuarios.id"), nullable=True)
    # Crédito aplicado a un débito concreto (p. ej. condonar una reposición).
    cargo_id = Column(Integer, ForeignKey("movimientos_cuenta.id", ondelete="SET NULL"),
                      nullable=True, index=True)


class Configuracion(Base):
    """Ajustes del sistema guardados como pares clave/valor JSON."""
    __tablename__ = "configuraciones"
    __table_args__ = {'extend_existing': True}
    id = Column(Integer, primary_key=True, index=True)
    clave = Column(String(50), unique=True, nullable=False, index=True)
    valor = Column(JSONB, nullable=False)
    actualizado_en = Column(DateTime(timezone=True), default=ahora)


# ==========================================
# MÓDULO DE ADQUISICIONES
# ==========================================

class Proveedor(Base):
    __tablename__ = "proveedores"
    id = Column(Integer, primary_key=True, index=True)
    nombre = Column(String(150), nullable=False)
    contacto = Column(String(150), nullable=True)
    email = Column(String(100), nullable=True)
    telefono = Column(String(30), nullable=True)
    activo = Column(Boolean, default=True)
    rif = Column(String(20), nullable=True)
    direccion = Column(Text, nullable=True)
    # Descuento habitual (%) que se propone en cada línea nueva.
    descuento = Column(Numeric(5, 2), nullable=False, default=0, server_default="0")
    # Días que suele tardar en entregar: pasado ese plazo, el pedido está atrasado.
    dias_entrega = Column(Integer, nullable=True)
    notas = Column(Text, nullable=True)


class Presupuesto(Base):
    """Período presupuestario (budget de Koha). Se reparte en fondos."""
    __tablename__ = "presupuestos"
    id = Column(Integer, primary_key=True, index=True)
    nombre = Column(String(100), nullable=False)
    fecha_inicio = Column(Date, nullable=False)
    fecha_fin = Column(Date, nullable=False)
    monto_total = Column(Numeric(12, 2), nullable=False)
    # Solo los fondos de presupuestos activos aceptan pedidos nuevos.
    activo = Column(Boolean, nullable=False, default=True, server_default=text("true"))
    # Bloqueado: ya no se modifican montos ni fondos (cierre del ejercicio).
    bloqueado = Column(Boolean, nullable=False, default=False, server_default=text("false"))


class Fondo(Base):
    """Fondo de un presupuesto (fund de Koha). Lo comprometido y gastado se calcula."""
    __tablename__ = "fondos"
    __table_args__ = (
        UniqueConstraint("presupuesto_id", "codigo", name="uq_fondo_codigo_por_presupuesto"),
    )
    id = Column(Integer, primary_key=True, index=True)
    presupuesto_id = Column(Integer, ForeignKey("presupuestos.id", ondelete="CASCADE"),
                            nullable=False, index=True)
    codigo = Column(String(20), nullable=False)
    nombre = Column(String(100), nullable=False)
    monto_asignado = Column(Numeric(12, 2), nullable=False)
    biblioteca_id = Column(Integer, ForeignKey("bibliotecas.id"), nullable=True)
    activo = Column(Boolean, nullable=False, default=True, server_default=text("true"))


class OrdenCompra(Base):
    """Pedido a un proveedor (la "cesta" de Koha).

    Abierta (se arma) → Cerrada (enviada al proveedor; se recibe) → Recibida, o Cancelada.
    """
    __tablename__ = "ordenes_compra"
    id = Column(Integer, primary_key=True, index=True)
    proveedor_id = Column(Integer, ForeignKey("proveedores.id"))
    nombre = Column(String(100), nullable=True)
    fecha_emision = Column(DateTime(timezone=True), default=ahora)
    fecha_cierre = Column(DateTime(timezone=True), nullable=True)
    fecha_recepcion = Column(DateTime(timezone=True), nullable=True)
    estado = Column(String(20), default="Abierta")
    observaciones = Column(Text, nullable=True)
    biblioteca_entrega_id = Column(Integer, ForeignKey("bibliotecas.id"), nullable=True)
    creado_por_id = Column(Integer, ForeignKey("usuarios.id"), nullable=True)


class LineaOrden(Base):
    """Un título pedido. Pendiente → Parcial → Recibida, o Cancelada."""
    __tablename__ = "lineas_orden"
    id = Column(Integer, primary_key=True, index=True)
    orden_id = Column(Integer, ForeignKey("ordenes_compra.id", ondelete="CASCADE"))
    # El registro se crea al pedir (como en Koha): así se puede reservar lo que viene.
    biblio_id = Column(Integer, ForeignKey("registros_bibliograficos.id", ondelete="SET NULL"),
                       nullable=True)
    fondo_id = Column(Integer, ForeignKey("fondos.id"), nullable=True)
    titulo = Column(Text, nullable=False)
    autor = Column(Text, nullable=True)
    isbn = Column(String(20), nullable=True)
    cantidad = Column(Integer, nullable=False, default=1)
    # Precio de lista; el costo estimado ya lleva el descuento y es lo que se compromete.
    precio_unitario = Column(Numeric(10, 2), nullable=False, default=0)
    descuento = Column(Numeric(5, 2), nullable=False, default=0, server_default="0")
    costo_estimado = Column(Numeric(10, 2), nullable=False)
    cantidad_recibida = Column(Integer, nullable=False, default=0, server_default="0")
    estado = Column(String(20), nullable=False, default="Pendiente", server_default="Pendiente")
    notas = Column(Text, nullable=True)


class Factura(Base):
    """Factura del proveedor. Lo recibido contra ella es lo gastado de cada fondo."""
    __tablename__ = "facturas"
    __table_args__ = (
        UniqueConstraint("proveedor_id", "numero", name="uq_factura_numero_por_proveedor"),
    )
    id = Column(Integer, primary_key=True, index=True)
    proveedor_id = Column(Integer, ForeignKey("proveedores.id"), nullable=False)
    numero = Column(String(50), nullable=False)
    fecha = Column(Date, nullable=False)
    costo_envio = Column(Numeric(12, 2), nullable=False, default=0, server_default="0")
    fondo_envio_id = Column(Integer, ForeignKey("fondos.id"), nullable=True)
    cerrada = Column(Boolean, nullable=False, default=False, server_default=text("false"))
    fecha_cierre = Column(DateTime(timezone=True), nullable=True)
    notas = Column(Text, nullable=True)


class Recepcion(Base):
    """Unidades de una línea recibidas en una factura, a su costo real."""
    __tablename__ = "recepciones"
    id = Column(Integer, primary_key=True, index=True)
    linea_id = Column(Integer, ForeignKey("lineas_orden.id", ondelete="CASCADE"), nullable=False,
                      index=True)
    factura_id = Column(Integer, ForeignKey("facturas.id"), nullable=True, index=True)
    cantidad = Column(Integer, nullable=False)
    costo_unitario = Column(Numeric(10, 2), nullable=False)
    fecha = Column(DateTime(timezone=True), nullable=False, default=ahora,
                   server_default=text("now()"))
    personal_id = Column(Integer, ForeignKey("usuarios.id"), nullable=True)


class Sugerencia(Base):
    """Sugerencia de compra. Pendiente → Aceptada | Rechazada → Pedida."""
    __tablename__ = "sugerencias"
    id = Column(Integer, primary_key=True, index=True)
    titulo = Column(Text, nullable=False)
    autor = Column(Text, nullable=True)
    isbn = Column(String(20), nullable=True)
    editorial = Column(String(150), nullable=True)
    ano = Column(Integer, nullable=True)
    nota = Column(Text, nullable=True)
    usuario_id = Column(Integer, ForeignKey("usuarios.id"), nullable=True)
    estado = Column(String(20), nullable=False, default="Pendiente", server_default="Pendiente",
                    index=True)
    motivo = Column(Text, nullable=True)
    fecha = Column(DateTime(timezone=True), nullable=False, default=ahora,
                   server_default=text("now()"))
    gestionada_por_id = Column(Integer, ForeignKey("usuarios.id"), nullable=True)
    fecha_gestion = Column(DateTime(timezone=True), nullable=True)
    linea_id = Column(Integer, ForeignKey("lineas_orden.id", ondelete="SET NULL"), nullable=True)


# ==========================================
# MÓDULO DE PUBLICACIONES SERIADAS
# ==========================================

class Suscripcion(Base):
    """Suscripción a una publicación seriada, con su patrón de predicción.

    Cada `frecuencia_cada` unidades (dia, semana, mes, anio) sale un número rotulado con
    `numeracion`: {X} volumen, {Y} número, {ANO} año y {MES} mes. Con `numeros_por_volumen`,
    al pasar ese número Y vuelve a 1 y X sube. Unidad `irregular`: se cargan a mano.
    """
    __tablename__ = "suscripciones"
    id = Column(Integer, primary_key=True, index=True)
    biblio_id = Column(Integer, ForeignKey("registros_bibliograficos.id", ondelete="SET NULL"),
                       nullable=True)
    titulo = Column(Text, nullable=False)
    issn = Column(String(20), nullable=True)
    proveedor_id = Column(Integer, ForeignKey("proveedores.id"), nullable=True)
    biblioteca_id = Column(Integer, ForeignKey("bibliotecas.id"), nullable=True)
    tipo_item_id = Column(Integer, ForeignKey("tipos_item.id"), nullable=True)
    # Al recibir un fascículo se da de alta su ejemplar.
    crear_ejemplares = Column(Boolean, nullable=False, default=True, server_default=text("true"))
    frecuencia_unidad = Column(String(10), nullable=False, default="mes", server_default="mes")
    frecuencia_cada = Column(Integer, nullable=False, default=1, server_default="1")
    numeracion = Column(String(100), nullable=False, default="Núm. {Y}", server_default="Núm. {Y}")
    numeros_por_volumen = Column(Integer, nullable=True)
    fecha_inicio = Column(Date, nullable=True)
    fecha_fin = Column(Date, nullable=True)
    # Días después de la fecha esperada en que un fascículo pasa a estar atrasado.
    dias_gracia = Column(Integer, nullable=False, default=15, server_default="15")
    # Activa, Vencida, Cancelada
    estado = Column(String(20), default="Activa")
    notas = Column(Text, nullable=True)


class Fasciculo(Base):
    """Un número de la publicación. Esperado → Recibido | Reclamado → Recibido | Faltante."""
    __tablename__ = "fasciculos"
    id = Column(Integer, primary_key=True, index=True)
    suscripcion_id = Column(Integer, ForeignKey("suscripciones.id", ondelete="CASCADE"),
                            index=True)
    numero = Column(String(50), nullable=False)
    fecha_esperada = Column(Date, nullable=True)
    fecha_recepcion = Column(DateTime(timezone=True), nullable=True)
    recibido = Column(Boolean, default=False)
    estado = Column(String(20), nullable=False, default="Esperado", server_default="Esperado",
                    index=True)
    # Contadores que produjeron el rótulo: de ellos se predice el siguiente.
    volumen = Column(Integer, nullable=True)
    secuencia = Column(Integer, nullable=True)
    reclamos = Column(Integer, nullable=False, default=0, server_default="0")
    fecha_reclamo = Column(DateTime(timezone=True), nullable=True)
    notas = Column(Text, nullable=True)
    item_id = Column(Integer, ForeignKey("items.id", ondelete="SET NULL"), nullable=True)


class Lista(Base):
    """Lista de títulos de un lector (las "listas" del OPAC de Koha). Pública o privada."""
    __tablename__ = "listas"
    id = Column(Integer, primary_key=True, index=True)
    usuario_id = Column(Integer, ForeignKey("usuarios.id", ondelete="CASCADE"), nullable=False,
                        index=True)
    nombre = Column(String(100), nullable=False)
    publica = Column(Boolean, nullable=False, default=False, server_default=text("false"))
    fecha_creacion = Column(DateTime(timezone=True), nullable=False, default=ahora,
                            server_default=text("now()"))


class ListaRegistro(Base):
    __tablename__ = "listas_registros"
    lista_id = Column(Integer, ForeignKey("listas.id", ondelete="CASCADE"), primary_key=True)
    biblio_id = Column(Integer, ForeignKey("registros_bibliograficos.id", ondelete="CASCADE"),
                       primary_key=True)
    fecha = Column(DateTime(timezone=True), nullable=False, default=ahora,
                   server_default=text("now()"))
