from typing import Annotated, Any, Dict, List, Literal, Optional

from pydantic import BaseModel, ConfigDict, Field, StringConstraints, field_validator


# ==========================================
# CATÁLOGO
# ==========================================

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


# ==========================================
# FICHA SIMPLE DEL LIBRO (formulario ↔ MARC 21)
# ==========================================

class FichaLibro(BaseModel):
    """Los campos del formulario de catalogación simple. `services/ficha.py` la traduce a MARC."""

    cota: str
    titulo: str
    subtitulo: Optional[str] = None
    mencion: Optional[str] = None
    autor: Optional[str] = None
    otros_autores: List[str] = []
    edicion: Optional[str] = None
    lugar: Optional[str] = None
    editorial: Optional[str] = None
    ano: Optional[int] = Field(default=None, ge=0, le=9999)
    paginas: Optional[str] = None
    ilustraciones: Optional[str] = None
    dimensiones: Optional[str] = None
    isbn: List[str] = []
    materias: List[str] = []
    descripcion: Optional[str] = None
    notas: Optional[str] = None

    @field_validator("cota", "titulo", mode="before")
    @classmethod
    def _obligatorio(cls, valor: Any) -> Any:
        valor = valor.strip() if isinstance(valor, str) else valor
        if not valor:
            raise ValueError("Es obligatorio")
        return valor

    @field_validator("subtitulo", "mencion", "autor", "edicion", "lugar", "editorial",
                     "paginas", "ilustraciones", "dimensiones", "descripcion", "notas",
                     mode="before")
    @classmethod
    def _opcional(cls, valor: Any) -> Any:
        if isinstance(valor, str):
            return valor.strip() or None
        return valor

    @field_validator("otros_autores", "isbn", "materias", mode="before")
    @classmethod
    def _lista(cls, valores: Any) -> Any:
        if valores is None:
            return []
        if isinstance(valores, list):
            limpios = [v.strip() if isinstance(v, str) else v for v in valores]
            return [v for v in limpios if v != ""]
        return valores


# ==========================================
# LIBROS (/api/v1/books)
# ==========================================

class NuevoLibroRequest(BaseModel):
    ficha: FichaLibro
    ejemplares: int = Field(default=1, ge=0, le=100)
    # La misma nota para todos los ejemplares creados (p. ej. «Donación»).
    nota_ejemplares: Optional[str] = None
    # Guardar aunque haya posibles duplicados (otra edición, otro libro con el mismo título).
    forzar: bool = False


class EjemplarRequest(BaseModel):
    """Alta o corrección de un ejemplar. Al editar solo cambia lo enviado (vacío = se borra)."""
    cota: Optional[str] = Field(default=None, max_length=100)
    codigo_barras: Optional[str] = Field(default=None, max_length=50)
    numero_copia: Optional[str] = Field(default=None, max_length=20)
    nota: Optional[str] = None
