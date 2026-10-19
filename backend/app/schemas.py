from datetime import date, datetime
from typing import Any, Dict, List, Literal, Optional, Union

from pydantic import BaseModel, EmailStr, Field


# ==========================================
# CIRCULACIÓN
# ==========================================

class CheckoutRequest(BaseModel):
    codigo_barras: str
    nro_carnet: str


class CheckinRequest(BaseModel):
    codigo_barras: str


class RenewRequest(BaseModel):
    prestamo_id: int


class PrestamoResponse(BaseModel):
    id: int
    item_id: int
    usuario_id: int
    fecha_prestamo: datetime
    fecha_vencimiento: datetime
    fecha_devolucion: Optional[datetime] = None

    class Config:
        from_attributes = True


class ReservaApartada(BaseModel):
    lector: str
    carnet: str
    # Solo si ya está en el estante de reservas; en tránsito el plazo corre al llegar.
    retirar_hasta: Optional[str] = None
    sede_retiro: Optional[str] = None


class TrasladoAbierto(BaseModel):
    id: int
    hacia: Optional[str] = None
    motivo: str          # reserva | retorno | manual
    enviado: bool


class ReturnResponse(BaseModel):
    mensaje: str
    multa_aplicada: float
    nuevo_estado_item: str
    # Qué hacer con el ejemplar: espera | transito | retorno | disponible
    accion: str = "disponible"
    reserva: Optional[ReservaApartada] = None
    traslado: Optional[TrasladoAbierto] = None
    # Al aparecer un ejemplar declarado perdido: lo que se acreditó y a quién.
    recuperado: bool = False
    reintegro: float = 0.0
    lector_reintegro: Optional[str] = None


class RenewResponse(BaseModel):
    mensaje: str
    nueva_fecha_vencimiento: datetime
    renovaciones_realizadas: int
    renovaciones_restantes: int
    multa_aplicada: float = 0


# ==========================================
# CATÁLOGO
# ==========================================

class NuevoMaterialRequest(BaseModel):
    titulo: str = Field(min_length=1)
    autor: Optional[str] = None
    isbn: Optional[str] = None
    ano_publicacion: Optional[int] = Field(default=None, ge=0, le=9999)
    materia: Optional[str] = None
    codigo_barras: str = Field(min_length=1)
    signatura_topografica: Optional[str] = None
    tipo_item_codigo: str = "LIB"
    precio_reposicion: Optional[float] = Field(default=None, ge=0)


class MaterialResponse(BaseModel):
    id: str
    title: str
    author: str
    year: Optional[int] = None
    category: str
    type: str
    isbn: str
    location: Optional[str] = None
    copies: int
    available: int
    availableBarcode: Optional[str] = None
    holds: int = 0


class RegistroMarcRequest(BaseModel):
    plantilla: Literal["BKS", "SER", "TES", "ERE"] = "BKS"
    # MARC-in-JSON: {"leader": "...", "fields": [{"245": {"ind1", "ind2", "subfields"}}]}
    marc: Dict[str, Any]
    # El ISBN ya está en otro registro y se guarda igual (otra edición, otra copia catalogada).
    permitir_duplicado: bool = False


class RegistroMarcResponse(BaseModel):
    id: str
    plantilla: str
    marc: Dict[str, Any]
    texto: str
    titulo: str
    autor: Optional[str] = None
    materia: Optional[str] = None
    ano_publicacion: Optional[int] = None
    isbn: Optional[str] = None


class NuevoEjemplarRequest(BaseModel):
    codigo_barras: str = Field(min_length=1)
    tipo_item_codigo: str = "LIB"
    signatura_topografica: Optional[str] = None
    precio_reposicion: Optional[float] = Field(default=None, ge=0)


class EditarEjemplarRequest(BaseModel):
    """Corrección de un ejemplar; solo cambia lo enviado."""
    codigo_barras: Optional[str] = Field(default=None, min_length=1, max_length=50)
    tipo_item_codigo: Optional[str] = None
    signatura_topografica: Optional[str] = Field(default=None, max_length=100)
    enumeracion: Optional[str] = Field(default=None, max_length=100)
    precio_reposicion: Optional[float] = Field(default=None, ge=0)
    biblioteca_propia_id: Optional[int] = None
    # Retirado: dado de baja sin borrarlo (conserva el historial). Los demás estados
    # los maneja la circulación.
    estado: Optional[Literal["Disponible", "Retirado"]] = None


class ValorFaceta(BaseModel):
    valor: Union[str, int]
    etiqueta: Optional[str] = None
    cantidad: int


class Facetas(BaseModel):
    disponibilidad: List[ValorFaceta]
    tipos: List[ValorFaceta]
    materias: List[ValorFaceta]
    autores: List[ValorFaceta]
    decadas: List[ValorFaceta]


class BusquedaCatalogoResponse(BaseModel):
    total: int
    pagina: int
    por_pagina: int
    paginas: int
    orden: str
    resultados: List[MaterialResponse]
    facetas: Facetas


class ReservaRequest(BaseModel):
    biblio_id: int
    nro_carnet: str
    biblioteca_retiro_id: Optional[int] = None
    fecha_limite: Optional[date] = None
    notas: Optional[str] = Field(default=None, max_length=500)


class ModificarReservaRequest(BaseModel):
    """Solo se cambia lo enviado. `suspendida_hasta` vacío = suspendida hasta reanudarla."""
    prioridad: Optional[int] = Field(default=None, ge=1)
    biblioteca_retiro_id: Optional[int] = None
    suspendida: Optional[bool] = None
    suspendida_hasta: Optional[date] = None
    fecha_limite: Optional[date] = None
    notas: Optional[str] = Field(default=None, max_length=500)


class TrasladoRequest(BaseModel):
    codigo_barras: str = Field(min_length=1)
    hacia_id: int
    comentario: Optional[str] = Field(default=None, max_length=500)


class SedeRequest(BaseModel):
    codigo: Optional[str] = None
    nombre: Optional[str] = None
    direccion: Optional[str] = None
    telefono: Optional[str] = None
    email: Optional[str] = None
    punto_retiro: Optional[bool] = None


class ReservaResponse(BaseModel):
    mensaje: str
    reserva_id: int
    prioridad: int


# ==========================================
# USUARIOS
# ==========================================

class CategoriaSchema(BaseModel):
    codigo: str
    descripcion: str

    class Config:
        from_attributes = True


class UserResponse(BaseModel):
    nro_carnet: str
    nombre: str
    apellido: str
    email: str
    activo: bool
    saldo_multas: float
    departamento: Optional[str] = None
    fecha_creacion: Optional[datetime] = None
    categoria: Optional[CategoriaSchema] = None
    prestamos_activos_count: int
    total_prestamos_count: int
    es_personal: bool = False
    permisos: List[str] = []
    debe_cambiar_clave: bool = False
    bloqueado_por_deuda: bool = False
    # Sede de inscripción (para el personal, su sede de trabajo por defecto).
    biblioteca_id: Optional[int] = None

    class Config:
        from_attributes = True


class NuevoUsuarioRequest(BaseModel):
    nro_carnet: str = Field(min_length=1, max_length=50)
    nombre: str = Field(min_length=1, max_length=100)
    apellido: str = Field(min_length=1, max_length=100)
    email: EmailStr
    username: Optional[str] = Field(default=None, max_length=50)
    password: Optional[str] = Field(default=None, max_length=128)
    departamento: Optional[str] = Field(default=None, max_length=100)
    categoria_codigo: str = "EST"
    # Sede de inscripción: de ahí salen su sede de retiro y la sede de trabajo del personal.
    biblioteca_id: Optional[int] = None


class EditarUsuarioRequest(BaseModel):
    nombre: Optional[str] = Field(default=None, max_length=100)
    apellido: Optional[str] = Field(default=None, max_length=100)
    email: Optional[EmailStr] = None
    departamento: Optional[str] = Field(default=None, max_length=100)
    categoria_codigo: Optional[str] = None
    biblioteca_id: Optional[int] = None


class EstadoUsuarioRequest(BaseModel):
    activo: bool


# ==========================================
# AUTENTICACIÓN
# ==========================================

class CambiarClaveRequest(BaseModel):
    actual: str = Field(min_length=1)
    nueva: str = Field(min_length=1, max_length=128)


class RestablecerClaveRequest(BaseModel):
    nueva: str = Field(min_length=1, max_length=128)


class LoginRequest(BaseModel):
    username: str
    password: str


class LoginResponse(BaseModel):
    """El token NO viaja en el cuerpo: queda en una cookie httpOnly."""
    usuario: UserResponse


class AsignarPermisosRequest(BaseModel):
    es_personal: bool
    permisos: List[str] = []


class PermisoInfo(BaseModel):
    codigo: str
    descripcion: str


class PerfilInfo(BaseModel):
    codigo: str
    nombre: str
    permisos: List[str]


class CatalogoPermisosResponse(BaseModel):
    permisos: List[PermisoInfo]
    perfiles: List[PerfilInfo]


# ==========================================
# CONFIGURACIÓN
# ==========================================

class ConfiguracionResponse(BaseModel):
    institucion: Dict[str, Any]
    politicas_prestamo: Dict[str, Any]
    notificaciones: Dict[str, Any]
    circulacion: Dict[str, Any] = {}
    calendario: Dict[str, Any] = {}


class AjustesCirculacionRequest(BaseModel):
    """Valores comunes a todas las reglas; los omitidos no cambian."""
    umbral_bloqueo: Optional[float] = Field(default=None, ge=0)
    dias_retiro_reserva: Optional[int] = Field(default=None, ge=1)
    precio_reposicion: Optional[float] = Field(default=None, ge=0)
    retorno_a_sede_propia: Optional[bool] = None
    perdonar_mora_al_perder: Optional[bool] = None


class PoliticasPrestamoRequest(BaseModel):
    """Lo que se escribe en las reglas de circulación; los omitidos no cambian."""
    dias_estudiante: Optional[int] = Field(default=None, ge=1, le=3650)
    dias_docente: Optional[int] = Field(default=None, ge=1, le=3650)
    dias_personal: Optional[int] = Field(default=None, ge=1, le=3650)
    max_estudiante: Optional[int] = Field(default=None, ge=0, le=1000)
    max_docente: Optional[int] = Field(default=None, ge=0, le=1000)
    max_personal: Optional[int] = Field(default=None, ge=0, le=1000)
    renovaciones_permitidas: Optional[int] = Field(default=None, ge=0, le=100)
    multa_por_dia: Optional[float] = Field(default=None, ge=0)


class ActualizarConfiguracionRequest(BaseModel):
    institucion: Optional[Dict[str, Any]] = None
    politicas_prestamo: Optional[PoliticasPrestamoRequest] = None
    notificaciones: Optional[Dict[str, Any]] = None
    circulacion: Optional[AjustesCirculacionRequest] = None


# ==========================================
# CUENTAS DEL LECTOR
# ==========================================

class PagoRequest(BaseModel):
    monto: float = Field(gt=0)
    descripcion: Optional[str] = None
    # El cargo al que se aplica. Vacío: a los cargos más viejos primero.
    cargo_id: Optional[int] = None


class CondonacionRequest(BaseModel):
    monto: float = Field(gt=0)
    motivo: str = Field(min_length=3)
    # El cargo al que se aplica (multa o reposición). Vacío: a la deuda en general.
    cargo_id: Optional[int] = None


class MovimientoCuentaResponse(BaseModel):
    id: int
    tipo: str
    monto: float
    descripcion: Optional[str] = None
    fecha: str
    prestamo_id: Optional[int] = None
    cargo_id: Optional[int] = None


class CargoPendienteResponse(BaseModel):
    id: int
    tipo: str
    descripcion: Optional[str] = None
    fecha: str
    monto: float
    pagado: float = 0
    condonado: float = 0
    pendiente: float


class EstadoCuentaResponse(BaseModel):
    saldo: float
    umbral_bloqueo: float
    bloqueado: bool
    movimientos: List[MovimientoCuentaResponse]
    cargos: List[CargoPendienteResponse] = []


# ==========================================
# REGLAS DE CIRCULACIÓN Y CALENDARIO
# ==========================================

class ReglaRequest(BaseModel):
    """Combinación (NULL = todas) y políticas que se le aplican."""
    categoria_id: Optional[int] = None
    tipo_item_id: Optional[int] = None
    biblioteca_id: Optional[int] = None
    prestable: bool = True
    dias_prestamo: int = Field(ge=0)
    max_prestamos: int = Field(ge=0)
    max_renovaciones: int = Field(ge=0)
    multa_por_dia: float = Field(ge=0)
    multa_maxima: Optional[float] = Field(default=None, ge=0)
    dias_gracia: int = Field(default=0, ge=0)
    max_reservas: int = Field(default=5, ge=0)


class ReglaResponse(ReglaRequest):
    id: int
    categoria: str
    tipo_item: str
    biblioteca: str


class OpcionDimension(BaseModel):
    id: int
    codigo: str
    nombre: str


class OpcionesReglaResponse(BaseModel):
    categorias: List[OpcionDimension]
    tipos_item: List[OpcionDimension]
    bibliotecas: List[OpcionDimension]


class FeriadoRequest(BaseModel):
    fecha: date
    descripcion: str = Field(min_length=1, max_length=150)


class DiasCerradosRequest(BaseModel):
    dias: List[int]


class FeriadoResponse(BaseModel):
    id: int
    fecha: date
    descripcion: str


class CalendarioResponse(BaseModel):
    dias_cerrados: List[int]
    dias_cerrados_nombres: List[str]
    feriados: List[FeriadoResponse]


# ==========================================
# ADQUISICIONES
# ==========================================

class ProveedorRequest(BaseModel):
    """Alta y edición: en la edición solo cambia lo enviado."""
    nombre: Optional[str] = None
    contacto: Optional[str] = None
    email: Optional[EmailStr] = None
    telefono: Optional[str] = None
    rif: Optional[str] = Field(default=None, max_length=20)
    direccion: Optional[str] = None
    descuento: Optional[float] = Field(default=None, ge=0, le=100)
    dias_entrega: Optional[int] = Field(default=None, ge=0)
    notas: Optional[str] = None
    activo: Optional[bool] = None


class PresupuestoRequest(BaseModel):
    nombre: Optional[str] = None
    fecha_inicio: Optional[date] = None
    fecha_fin: Optional[date] = None
    monto_total: Optional[float] = Field(default=None, ge=0)
    activo: Optional[bool] = None
    bloqueado: Optional[bool] = None


class FondoRequest(BaseModel):
    codigo: Optional[str] = Field(default=None, max_length=20)
    nombre: Optional[str] = Field(default=None, max_length=100)
    monto_asignado: Optional[float] = Field(default=None, ge=0)
    biblioteca_id: Optional[int] = None
    activo: Optional[bool] = None


class LineaOrdenRequest(BaseModel):
    """Un registro existente (`biblio_id`) o los datos de uno nuevo (título, autor, ISBN)."""
    biblio_id: Optional[int] = None
    titulo: Optional[str] = None
    autor: Optional[str] = None
    isbn: Optional[str] = None
    cantidad: Optional[int] = Field(default=None, ge=1)
    precio_unitario: Optional[float] = Field(default=None, ge=0)
    descuento: Optional[float] = Field(default=None, ge=0, le=100)
    fondo_id: Optional[int] = None
    notas: Optional[str] = None


class OrdenCompraRequest(BaseModel):
    proveedor_id: int
    nombre: Optional[str] = Field(default=None, max_length=100)
    observaciones: Optional[str] = None
    biblioteca_entrega_id: Optional[int] = None
    lineas: List[LineaOrdenRequest] = []


class EditarOrdenRequest(BaseModel):
    nombre: Optional[str] = Field(default=None, max_length=100)
    observaciones: Optional[str] = None
    biblioteca_entrega_id: Optional[int] = None


class FacturaRequest(BaseModel):
    proveedor_id: Optional[int] = None
    numero: Optional[str] = Field(default=None, max_length=50)
    fecha: Optional[date] = None
    costo_envio: Optional[float] = Field(default=None, ge=0)
    fondo_envio_id: Optional[int] = None
    notas: Optional[str] = None


class RecepcionRequest(BaseModel):
    linea_id: int
    cantidad: Optional[int] = Field(default=None, ge=1)
    costo_unitario: Optional[float] = Field(default=None, ge=0)
    tipo_item_codigo: Optional[str] = None
    biblioteca_id: Optional[int] = None
    signatura: Optional[str] = None
    # Vacío: se generan (OC0001-L001-01…).
    codigos_barras: Optional[List[str]] = None


class SugerenciaRequest(BaseModel):
    titulo: str = Field(min_length=1)
    autor: Optional[str] = None
    isbn: Optional[str] = Field(default=None, max_length=20)
    editorial: Optional[str] = Field(default=None, max_length=150)
    ano: Optional[int] = Field(default=None, ge=0, le=9999)
    nota: Optional[str] = None
    # A nombre de un lector; vacío, a nombre de quien la registra.
    nro_carnet: Optional[str] = None


class DecisionSugerenciaRequest(BaseModel):
    motivo: Optional[str] = None


class PedirSugerenciaRequest(BaseModel):
    orden_id: int
    cantidad: Optional[int] = Field(default=None, ge=1)
    precio_unitario: Optional[float] = Field(default=None, ge=0)
    descuento: Optional[float] = Field(default=None, ge=0, le=100)
    fondo_id: Optional[int] = None


# ==========================================
# PUBLICACIONES SERIADAS
# ==========================================

class SuscripcionRequest(BaseModel):
    """Un registro existente (`biblio_id`) o título e ISSN para crear uno SER."""
    biblio_id: Optional[int] = None
    titulo: Optional[str] = None
    issn: Optional[str] = Field(default=None, max_length=20)
    proveedor_id: Optional[int] = None
    biblioteca_id: Optional[int] = None
    tipo_item_codigo: Optional[str] = None
    crear_ejemplares: Optional[bool] = None
    frecuencia_unidad: Optional[str] = None
    frecuencia_cada: Optional[int] = Field(default=None, ge=1)
    numeracion: Optional[str] = Field(default=None, max_length=100)
    numeros_por_volumen: Optional[int] = Field(default=None, ge=1)
    volumen_inicial: Optional[int] = Field(default=None, ge=0)
    numero_inicial: Optional[int] = Field(default=None, ge=0)
    fecha_inicio: Optional[date] = None
    primer_fasciculo: Optional[date] = None
    fecha_fin: Optional[date] = None
    dias_gracia: Optional[int] = Field(default=None, ge=0)
    notas: Optional[str] = None


class PrediccionRequest(BaseModel):
    frecuencia_unidad: str = "mes"
    frecuencia_cada: int = Field(default=1, ge=1)
    numeracion: str = "Núm. {Y}"
    numeros_por_volumen: Optional[int] = Field(default=None, ge=1)
    volumen_inicial: int = Field(default=1, ge=0)
    numero_inicial: int = Field(default=1, ge=0)
    primer_fasciculo: date
    cantidad: int = Field(default=12, ge=1, le=60)


class RenovarSuscripcionRequest(BaseModel):
    fecha_fin: Optional[date] = None


class FasciculoRequest(BaseModel):
    numero: str = Field(min_length=1)
    fecha_esperada: Optional[date] = None
    notas: Optional[str] = None


class RecibirFasciculoRequest(BaseModel):
    """Sin `crear_ejemplar`, se usa lo que diga la suscripción."""
    crear_ejemplar: Optional[bool] = None
    codigo_barras: Optional[str] = None
    signatura: Optional[str] = None
    notas: Optional[str] = None


class NotaRequest(BaseModel):
    notas: Optional[str] = None


# ==========================================
# REPORTES
# ==========================================

class SystemStatsResponse(BaseModel):
    total_items: int
    total_users: int
    loans_this_month: int
    growth_percentage: str


class ReporteDisponible(BaseModel):
    id: str
    title: str
    description: str
    lastGenerated: Optional[str] = None
    rows: int


# --- OPAC: cuenta del lector ------------------------------------------------------------

class ReservaOpacRequest(BaseModel):
    biblio_id: int
    biblioteca_retiro_id: Optional[int] = None
    fecha_limite: Optional[date] = None
    notas: Optional[str] = Field(default=None, max_length=500)


class RenovarOpacRequest(BaseModel):
    """El lector acepta que se cobre el atraso de un préstamo vencido al renovarlo."""
    aceptar_cargo: bool = False


class ModificarReservaOpacRequest(BaseModel):
    """Lo que el propio lector puede cambiar de una reserva pendiente."""
    biblioteca_retiro_id: Optional[int] = None
    suspendida: Optional[bool] = None
    suspendida_hasta: Optional[date] = None


class SugerenciaOpacRequest(BaseModel):
    titulo: str = Field(min_length=1, max_length=500)
    autor: Optional[str] = Field(default=None, max_length=300)
    isbn: Optional[str] = Field(default=None, max_length=20)
    editorial: Optional[str] = Field(default=None, max_length=150)
    ano: Optional[int] = Field(default=None, ge=0, le=9999)
    nota: Optional[str] = Field(default=None, max_length=1000)


class ListaRequest(BaseModel):
    nombre: str = Field(min_length=1, max_length=100)
    publica: bool = False


class EditarListaRequest(BaseModel):
    nombre: Optional[str] = Field(default=None, min_length=1, max_length=100)
    publica: Optional[bool] = None


class ListaRegistroRequest(BaseModel):
    biblio_id: int



# --- Avisos (Fase 7) ------------------------------------------------------------------------

class RecuperarClaveRequest(BaseModel):
    identificador: str = Field(min_length=1, max_length=100)


class RestablecerConEnlaceRequest(BaseModel):
    token: str = Field(min_length=10, max_length=200)
    nueva: str = Field(min_length=1, max_length=128)


class PlantillaAvisoRequest(BaseModel):
    asunto: Optional[str] = Field(default=None, max_length=300)
    cuerpo: Optional[str] = Field(default=None, max_length=5000)
    activo: Optional[bool] = None
    restablecer: bool = False


class VistaPreviaAvisoRequest(BaseModel):
    asunto: Optional[str] = Field(default=None, max_length=300)
    cuerpo: Optional[str] = Field(default=None, max_length=5000)


class AjustesAvisosRequest(BaseModel):
    recordatorio_dias_antes: Optional[int] = Field(default=None, ge=0, le=30)
    dias_vencido: Optional[List[int]] = None
    reclamos_automaticos: Optional[bool] = None
    dias_entre_reclamos: Optional[int] = Field(default=None, ge=1, le=120)


class CorreoPruebaRequest(BaseModel):
    destinatario: EmailStr
