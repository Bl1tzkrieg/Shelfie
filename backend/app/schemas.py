from typing import Annotated, Any, Dict, List, Literal, Optional, Union

from pydantic import BaseModel, ConfigDict, Field, StringConstraints


# ==========================================
# CATÁLOGO
# ==========================================

class NuevoMaterialRequest(BaseModel):
    titulo: str = Field(min_length=1)
    autor: Optional[str] = None
    isbn: Optional[str] = None
    ano_publicacion: Optional[int] = Field(default=None, ge=0, le=9999)
    materia: Optional[str] = None
    # Opcional: si viene, no puede repetirse.
    codigo_barras: Optional[str] = Field(default=None, max_length=50)
    signatura_topografica: Optional[str] = Field(default=None, max_length=100)


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
    codigo_barras: Optional[str] = Field(default=None, max_length=50)
    signatura_topografica: Optional[str] = Field(default=None, max_length=100)
    numero_copia: Optional[str] = Field(default=None, max_length=20)
    nota: Optional[str] = None


class EditarEjemplarRequest(BaseModel):
    """Corrección de un ejemplar; solo cambia lo enviado (vacío = se borra el dato)."""
    codigo_barras: Optional[str] = Field(default=None, max_length=50)
    signatura_topografica: Optional[str] = Field(default=None, max_length=100)
    numero_copia: Optional[str] = Field(default=None, max_length=20)
    nota: Optional[str] = None


class ValorFaceta(BaseModel):
    valor: Union[str, int]
    etiqueta: Optional[str] = None
    cantidad: int


class Facetas(BaseModel):
    disponibilidad: List[ValorFaceta]
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


# ==========================================
# PERSONAL
# ==========================================

Rol = Literal["administrador", "catalogador"]


class UserResponse(BaseModel):
    id: int
    username: str
    nombre: str
    apellido: str
    rol: Rol
    activo: bool
    debe_cambiar_clave: bool = False


class SesionResponse(UserResponse):
    """Quién entró, con sus permisos (para mostrar u ocultar opciones)."""
    permisos: List[str] = []


class NuevoPersonalRequest(BaseModel):
    username: str = Field(min_length=1, max_length=50)
    nombre: str = Field(min_length=1, max_length=100)
    apellido: str = Field(min_length=1, max_length=100)
    rol: Rol
    clave_temporal: str = Field(min_length=1, max_length=128)


class RolRequest(BaseModel):
    rol: Rol


class EstadoRequest(BaseModel):
    activo: bool


class ClaveTemporalRequest(BaseModel):
    clave_temporal: str = Field(min_length=1, max_length=128)


# ==========================================
# AUTENTICACIÓN
# ==========================================

class CambiarClaveRequest(BaseModel):
    actual: str = Field(min_length=1)
    nueva: str = Field(min_length=1, max_length=128)


class LoginRequest(BaseModel):
    username: str
    password: str


class LoginResponse(BaseModel):
    """El token NO viaja en el cuerpo: queda en una cookie httpOnly."""
    usuario: SesionResponse


# ==========================================
# CONFIGURACIÓN
# ==========================================

class ConfiguracionResponse(BaseModel):
    """Lo que se devuelve depende de quién pregunta: sin sesión solo `biblioteca.nombre`;
    el catalogador ve `biblioteca`; el administrador, además, `respaldo`."""
    biblioteca: Dict[str, Any]
    respaldo: Optional[Dict[str, Any]] = None


TextoObligatorio = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1)]


class BibliotecaRequest(BaseModel):
    nombre: Optional[TextoObligatorio] = None
    codigo: Optional[TextoObligatorio] = Field(default=None, max_length=16)
    tipo_item_koha: Optional[TextoObligatorio] = Field(default=None, max_length=10)


class RespaldoRequest(BaseModel):
    """Solo lo editable: `ultimo` y `ultimo_ok` los escribe el respaldo, no el cliente.
    Un texto vacío borra el valor."""
    model_config = ConfigDict(extra="ignore")
    carpeta: Optional[str] = None
    pg_dump: Optional[str] = None


class ActualizarConfiguracionRequest(BaseModel):
    biblioteca: Optional[BibliotecaRequest] = None
    respaldo: Optional[RespaldoRequest] = None
