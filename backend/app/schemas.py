from typing import Annotated, Any, Dict, List, Literal, Optional

from pydantic import AfterValidator, BaseModel, ConfigDict, Field, StringConstraints, field_validator

from app.core import pg_dump


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
    # Solo para el administrador: el respaldo está atrasado o falló.
    alerta_respaldo: bool = False


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
    """Las claves anteriores (`codigo`, `tipo_item_koha`) se rechazan en vez de ignorarse."""
    model_config = ConfigDict(extra="forbid")
    nombre: Optional[TextoObligatorio] = None
    # 952 $a y $b. Hasta 10: Koha guarda el código de sede en varchar(10) y no importaría uno
    # más largo.
    codigo_sede: Optional[TextoObligatorio] = Field(default=None, max_length=10)
    # 952 $y. Hasta 10 por la misma razón; se exporta en mayúsculas.
    tipo_item: Optional[TextoObligatorio] = Field(default=None, max_length=10)
    # 003. Opcional (vacío = sin 003) y tal cual: los códigos MARC distinguen mayúsculas.
    codigo_organizacion: Optional[Annotated[str, StringConstraints(
        strip_whitespace=True, max_length=16)]] = None


class RespaldoRequest(BaseModel):
    """Solo lo editable: `ultimo` y `ultimo_ok` los escribe el respaldo, no el cliente.
    Un texto vacío borra el valor."""
    model_config = ConfigDict(extra="ignore")
    carpeta: Optional[str] = None
    pg_dump: Optional[str] = None

    @field_validator("pg_dump")
    @classmethod
    def _solo_pg_dump(cls, valor: Optional[str]) -> Optional[str]:
        """Corre como SYSTEM: solo un pg_dump local, fuera de las carpetas de usuario."""
        motivo = pg_dump.problema(valor)
        if motivo:
            raise ValueError(motivo)
        return valor


class ActualizarConfiguracionRequest(BaseModel):
    biblioteca: Optional[BibliotecaRequest] = None
    respaldo: Optional[RespaldoRequest] = None


# ==========================================
# FICHA SIMPLE DEL LIBRO (formulario ↔ MARC 21)
# ==========================================

# Un campo MARC no puede pasar de 9999 bytes en ISO 2709 (el directorio guarda su largo en
# 4 dígitos). 9000 deja lugar a indicadores, códigos y separadores. El formulario usa el mismo
# número como tope de caracteres (aproximado: una letra con tilde ocupa 2 bytes).
MAX_BYTES_TEXTO_LARGO = 9000


def cabe_en_iso2709(valor: Optional[str]) -> Optional[str]:
    """Un texto largo que va a un campo MARC: el tope es en bytes UTF-8, no en caracteres."""
    if valor is not None and len(valor.encode("utf-8")) > MAX_BYTES_TEXTO_LARGO:
        raise ValueError(f"Es demasiado largo: hasta {MAX_BYTES_TEXTO_LARGO} bytes "
                         "(unos 9000 caracteres; las letras con tilde cuentan doble)")
    return valor


TextoLargo = Annotated[Optional[str], AfterValidator(cabe_en_iso2709)]


class FichaLibro(BaseModel):
    """Los campos del formulario de catalogación simple. `services/ficha.py` la traduce a MARC."""

    cota: str = Field(max_length=100)  # registros_bibliograficos.cota
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

    @field_validator("descripcion", "notas")
    @classmethod
    def _cabe_en_iso2709(cls, valor: Optional[str]) -> Optional[str]:
        return cabe_en_iso2709(valor)

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
    nota_ejemplares: TextoLargo = None
    # Guardar aunque haya posibles duplicados (otra edición, otro libro con el mismo título).
    forzar: bool = False


class EjemplarRequest(BaseModel):
    """Alta o corrección de un ejemplar. Al editar solo cambia lo enviado (vacío = se borra)."""
    cota: Optional[str] = Field(default=None, max_length=100)
    codigo_barras: Optional[str] = Field(default=None, max_length=50)
    numero_copia: Optional[str] = Field(default=None, max_length=20)
    nota: TextoLargo = None
