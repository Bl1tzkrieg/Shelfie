from datetime import date, datetime
from typing import Any, Dict, List, Optional

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


class ReturnResponse(BaseModel):
    mensaje: str
    multa_aplicada: float
    nuevo_estado_item: str


class RenewResponse(BaseModel):
    mensaje: str
    nueva_fecha_vencimiento: datetime
    renovaciones_realizadas: int
    renovaciones_restantes: int


# ==========================================
# CATÁLOGO
# ==========================================

class NuevoMaterialRequest(BaseModel):
    titulo: str = Field(min_length=1)
    autor: Optional[str] = None
    isbn: Optional[str] = None
    ano_publicacion: Optional[int] = None
    materia: Optional[str] = None
    codigo_barras: str = Field(min_length=1)
    signatura_topografica: Optional[str] = None
    tipo_item_codigo: str = "LIB"


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


class ReservaRequest(BaseModel):
    biblio_id: int
    nro_carnet: str


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

    class Config:
        from_attributes = True


class NuevoUsuarioRequest(BaseModel):
    nro_carnet: str = Field(min_length=1)
    nombre: str = Field(min_length=1)
    apellido: str = Field(min_length=1)
    email: EmailStr
    username: Optional[str] = None
    password: Optional[str] = None
    departamento: Optional[str] = None
    categoria_codigo: str = "EST"


class EditarUsuarioRequest(BaseModel):
    nombre: Optional[str] = None
    apellido: Optional[str] = None
    email: Optional[EmailStr] = None
    departamento: Optional[str] = None
    categoria_codigo: Optional[str] = None


class EstadoUsuarioRequest(BaseModel):
    activo: bool


# ==========================================
# AUTENTICACIÓN
# ==========================================

class LoginRequest(BaseModel):
    username: str
    password: str


class LoginResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    usuario: UserResponse


# ==========================================
# CONFIGURACIÓN
# ==========================================

class ConfiguracionResponse(BaseModel):
    institucion: Dict[str, Any]
    politicas_prestamo: Dict[str, Any]
    notificaciones: Dict[str, Any]


class ActualizarConfiguracionRequest(BaseModel):
    institucion: Optional[Dict[str, Any]] = None
    politicas_prestamo: Optional[Dict[str, Any]] = None
    notificaciones: Optional[Dict[str, Any]] = None


# ==========================================
# ADQUISICIONES
# ==========================================

class ProveedorRequest(BaseModel):
    nombre: str = Field(min_length=1)
    contacto: Optional[str] = None
    email: Optional[EmailStr] = None
    telefono: Optional[str] = None


class ProveedorResponse(BaseModel):
    id: int
    nombre: str
    contacto: Optional[str] = None
    email: Optional[str] = None
    telefono: Optional[str] = None
    activo: bool

    class Config:
        from_attributes = True


class LineaOrdenRequest(BaseModel):
    titulo: str = Field(min_length=1)
    autor: Optional[str] = None
    isbn: Optional[str] = None
    cantidad: int = Field(default=1, ge=1)
    precio_unitario: float = Field(default=0, ge=0)


class OrdenCompraRequest(BaseModel):
    proveedor_id: int
    observaciones: Optional[str] = None
    lineas: List[LineaOrdenRequest] = Field(min_length=1)


class LineaOrdenResponse(BaseModel):
    id: int
    titulo: str
    autor: Optional[str] = None
    isbn: Optional[str] = None
    cantidad: int
    precio_unitario: float

    class Config:
        from_attributes = True


class OrdenCompraResponse(BaseModel):
    id: int
    proveedor_id: Optional[int] = None
    proveedor_nombre: Optional[str] = None
    fecha_emision: datetime
    fecha_recepcion: Optional[datetime] = None
    estado: str
    observaciones: Optional[str] = None
    total: float
    lineas: List[LineaOrdenResponse] = []


# ==========================================
# PUBLICACIONES SERIADAS
# ==========================================

class SuscripcionRequest(BaseModel):
    titulo: str = Field(min_length=1)
    issn: Optional[str] = None
    proveedor_id: Optional[int] = None
    periodicidad: str = "Mensual"
    fecha_inicio: Optional[date] = None
    fecha_fin: Optional[date] = None


class SuscripcionResponse(BaseModel):
    id: int
    titulo: str
    issn: Optional[str] = None
    proveedor_id: Optional[int] = None
    periodicidad: str
    fecha_inicio: Optional[date] = None
    fecha_fin: Optional[date] = None
    estado: str
    fasciculos_recibidos: int
    fasciculos_esperados: int

    class Config:
        from_attributes = True


class FasciculoRequest(BaseModel):
    numero: str = Field(min_length=1)
    fecha_esperada: Optional[date] = None


class FasciculoResponse(BaseModel):
    id: int
    suscripcion_id: int
    numero: str
    fecha_esperada: Optional[date] = None
    fecha_recepcion: Optional[datetime] = None
    recibido: bool

    class Config:
        from_attributes = True


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
