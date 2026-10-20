/** Contratos que devuelve el backend (backend/app/schemas.py), compartidos por las pantallas. */

/** Permisos del personal (espejo de app/core/permisos.py). */
export type Permiso = "catalogo" | "superbibliotecario"

/** El rol es la forma simple de asignar permisos: cada uno equivale a un permiso. */
export type Rol = "administrador" | "catalogador"

export const NOMBRE_ROL: Record<Rol, string> = {
  administrador: "Administrador",
  catalogador: "Catalogador",
}

/** Nombre legible de cada permiso: el del rol que lo da. */
export const NOMBRE_PERMISO: Record<Permiso, string> = {
  catalogo: NOMBRE_ROL.catalogador,
  superbibliotecario: NOMBRE_ROL.administrador,
}

/** Un miembro del personal (GET /staff). */
export interface Personal {
  id: number
  username: string
  nombre: string
  apellido: string
  rol: Rol
  activo: boolean
  debe_cambiar_clave: boolean
}

/** Quien inició sesión (GET /auth/me). */
export interface Sesion extends Personal {
  permisos: Permiso[]
  /** Solo para el administrador: el respaldo está atrasado o falló. */
  alerta_respaldo: boolean
}

export interface EstadoRespaldo {
  ultimo: {
    fecha: string
    ok: boolean
    mensaje: string | null
    tamano?: number | null
    /** Respaldo correcto (base.dump bueno) con algo incompleto en el catálogo. */
    aviso?: string | null
  } | null
  ultimo_ok: string | null
  alerta: boolean
  motivo: string | null
}

/** GET /settings. Sin sesión solo llega el nombre de la biblioteca. */
export interface Configuracion {
  biblioteca: {
    nombre: string
    /** 952 $a/$b de la exportación a Koha. */
    codigo?: string
    /** 952 $y: tipo de ítem de Koha. */
    tipo_item_koha?: string
  }
  respaldo?: {
    carpeta: string | null
    pg_dump: string | null
  } & Partial<EstadoRespaldo>
}

export interface SystemInfo {
  version: string
  ultima_actualizacion: string | null
  total_registros: number
  total_ejemplares: number
  total_usuarios: number
}

// --- MARC ---------------------------------------------------------------------------

/** MARC-in-JSON: un campo de control ("008": "…") o de datos con indicadores y subcampos. */
export type CampoMarcDatos = {
  ind1: string
  ind2: string
  subfields: Record<string, string>[]
}
export type RegistroMarc = {
  leader: string
  fields: Record<string, string | CampoMarcDatos>[]
}

export interface DefinicionSubcampo {
  codigo: string
  nombre: string
  repetible: boolean
  obligatorio: boolean
}

export interface OpcionIndicador {
  valor: string
  nombre: string
}

export interface DefinicionCampo {
  tag: string
  nombre: string
  repetible: boolean
  obligatorio: boolean
  visible: boolean
  control: boolean
  ind1: OpcionIndicador[]
  ind2: OpcionIndicador[]
  ind1_defecto: string
  ind2_defecto: string
  subcampos: DefinicionSubcampo[]
}

export interface PlantillaMarc {
  codigo: string
  nombre: string
  descripcion: string
  lider: string
  bloques: Record<string, string>
  campos: DefinicionCampo[]
}

export type ResumenPlantilla = Pick<PlantillaMarc, "codigo" | "nombre" | "descripcion">

export interface RegistroMarcGuardado {
  id: string
  plantilla: string
  marc: RegistroMarc
  texto: string
  titulo: string
  autor: string | null
  materia: string | null
  ano_publicacion: number | null
  isbn: string | null
}

export interface ResultadoImportacion {
  formato: "marc" | "marcxml"
  aplicado: boolean
  total: number
  nuevos: number
  reemplazados: number
  omitidos: number
  con_errores: number
  ejemplares: number
  /** Avisos de toda la importación (p. ej. lo que se ignora de otro sistema). */
  mensajes: string[]
  registros: {
    n: number
    titulo: string
    autor: string | null
    isbn: string | null
    plantilla: string
    accion: "nuevo" | "reemplazar" | "omitir" | "error"
    registro_id: number | null
    ejemplares: number
    mensajes: string[]
  }[]
}

// --- Registro de acciones -----------------------------------------------------------

export interface AccionRegistrada {
  id: number
  fecha: string
  fecha_iso: string
  modulo: string
  accion: string
  accion_nombre: string
  descripcion: string
  actor: string
  actor_username: string | null
  /** El miembro del personal afectado (p. ej. a quien se le restableció la clave). */
  usuario_afectado: string | null
  usuario_afectado_username: string | null
  biblio_id: number | null
  titulo: string | null
  codigo_barras: string | null
  datos: Record<string, unknown> | null
  ip: string | null
}

export interface PaginaRegistro {
  total: number
  pagina: number
  paginas: number
  filas: AccionRegistrada[]
}

export interface AjustesRegistro {
  modulos: Record<string, boolean>
  dias_retencion: number
  /** Módulo → qué se registra en él. */
  descripciones: Record<string, string>
  /** Acción → nombre legible. */
  acciones: Record<string, string>
}

/** Una fila de GET /buscar: lo justo para reconocer el libro y llegar a su estante. */
export interface ResultadoBusqueda {
  id: number
  /** Null si el registro no tiene cota todavía. */
  cota: string | null
  titulo: string
  subtitulo: string | null
  autor: string | null
  edicion: string | null
  editorial: string | null
  ano: number | null
  ejemplares: number
}

export interface PaginaBusqueda {
  total: number
  pagina: number
  resultados: ResultadoBusqueda[]
}

export type CampoBusqueda = "todo" | "titulo" | "autor" | "materia" | "cota" | "isbn" | "editorial"

/** Los campos de la ficha catalográfica simple (GET /buscar/{id}). */
export interface FichaLibro {
  cota: string
  titulo: string
  subtitulo: string | null
  mencion: string | null
  autor: string | null
  otros_autores: string[]
  edicion: string | null
  lugar: string | null
  editorial: string | null
  ano: number | null
  paginas: string | null
  ilustraciones: string | null
  dimensiones: string | null
  isbn: string[]
  materias: string[]
  descripcion: string | null
  notas: string | null
}

/** Un ejemplar tal como lo ve el público: sin código de barras. */
export interface EjemplarPublico {
  cota: string | null
  numero_copia: string | null
  nota: string | null
}

export interface FichaPublica {
  ficha: FichaLibro
  ejemplares: EjemplarPublico[]
}

// --- Libros (/books: ingreso, edición y lista del catalogador) ----------------------

/** Un ejemplar como lo ve el catalogador: con su código de barras. */
export interface EjemplarLibro {
  id: number
  cota: string | null
  codigo_barras: string | null
  numero_copia: string | null
  nota: string | null
}

/** GET/PUT /books/{id}, y la respuesta del alta y de los cambios de ejemplares. */
export interface LibroCatalogo {
  id: number
  /** En un registro importado sin 092 o sin 245 $a, la cota o el título llegan vacíos. */
  ficha: FichaLibro
  ejemplares: EjemplarLibro[]
  creado_en: string | null
  actualizado_en: string | null
}

/** POST /books. */
export interface NuevoLibro {
  ficha: FichaLibro
  ejemplares: number
  nota_ejemplares: string | null
  forzar: boolean
}

/** Un libro que puede ser el mismo (409 POSIBLE_DUPLICADO). */
export interface CoincidenciaDuplicado {
  id: number
  titulo: string
  autor: string | null
  cota: string | null
}

/** Una fila de GET /books, en el orden del estante. */
export interface FilaLibro {
  id: number
  cota: string | null
  titulo: string
  autor: string | null
  ano: number | null
  editorial: string | null
  ejemplares: number
}

export interface PaginaLibros {
  total: number
  pagina: number
  por_pagina: number
  paginas: number
  resultados: FilaLibro[]
}
