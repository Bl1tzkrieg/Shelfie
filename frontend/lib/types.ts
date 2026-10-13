/** Contratos que devuelve el backend, compartidos por las pantallas. */

export interface Categoria {
  codigo: string
  descripcion: string
}

/** Permisos por módulo del personal (espejo de app/core/permisos.py). */
export type Permiso =
  | "circulacion"
  | "catalogo"
  | "lectores"
  | "reportes"
  | "configuracion"
  | "adquisiciones"
  | "seriadas"
  | "superbibliotecario"

/** Nombre legible de cada permiso, para la interfaz. */
export const NOMBRE_PERMISO: Record<Permiso, string> = {
  circulacion: "Circulación",
  catalogo: "Catalogación",
  lectores: "Lectores",
  reportes: "Reportes",
  configuracion: "Configuración",
  adquisiciones: "Adquisiciones",
  seriadas: "Publicaciones seriadas",
  superbibliotecario: "Superbibliotecario (acceso total)",
}

export interface CatalogoPermisos {
  permisos: { codigo: Permiso; descripcion: string }[]
  perfiles: { codigo: string; nombre: string; permisos: Permiso[] }[]
}

export interface ApiUser {
  nro_carnet: string
  nombre: string
  apellido: string
  email: string
  activo: boolean
  saldo_multas: number
  departamento: string | null
  fecha_creacion: string | null
  categoria: Categoria | null
  prestamos_activos_count: number
  total_prestamos_count: number
  es_personal: boolean
  permisos: Permiso[]
  bloqueado_por_deuda: boolean
  /** Sede de inscripción; para el personal, su sede de trabajo por defecto. */
  biblioteca_id: number | null
}

export interface ApiLoan {
  id: string
  bookTitle: string
  bookCode: string
  userName: string
  userId: string
  userType: "student" | "teacher" | "staff"
  loanDate: string
  dueDate: string
  returnDate: string | null
  renewals: number
  status: "active" | "overdue" | "returned"
  /** Préstamo cerrado porque el ejemplar se declaró perdido. */
  lost?: boolean
  /** Perdido y todavía sin aparecer: se puede registrar que volvió. */
  recoverable?: boolean
  /** Tope de renovaciones según la regla de circulación de este préstamo. */
  renewalsAllowed?: number | null
}

export interface MovimientoCuenta {
  id: number
  tipo: "MULTA_ATRASO" | "REPOSICION" | "PAGO" | "CONDONACION" | "AJUSTE" | "REINTEGRO"
  monto: number
  descripcion: string | null
  fecha: string
  prestamo_id: number | null
  /** El cargo al que se aplicó este crédito (condonación dirigida). */
  cargo_id: number | null
}

/** Débito al que todavía se le puede aplicar una condonación. */
export interface CargoPendiente {
  id: number
  tipo: MovimientoCuenta["tipo"]
  descripcion: string | null
  fecha: string
  monto: number
  pendiente: number
}

export interface EstadoCuenta {
  saldo: number
  umbral_bloqueo: number
  bloqueado: boolean
  movimientos: MovimientoCuenta[]
  cargos: CargoPendiente[]
}

/** Qué hacer con el ejemplar después de pasarlo por el mostrador de devolución. */
export type AccionDevolucion = "espera" | "transito" | "retorno" | "disponible"

export interface ResultadoDevolucion {
  mensaje: string
  multa_aplicada: number
  nuevo_estado_item: string
  accion: AccionDevolucion
  reserva: {
    lector: string
    carnet: string
    /** Solo si ya quedó en el estante de reservas; en tránsito, el plazo corre al llegar. */
    retirar_hasta: string | null
    sede_retiro: string | null
  } | null
  traslado: { id: number; hacia: string | null; motivo: MotivoTraslado; enviado: boolean } | null
  /** El ejemplar estaba declarado perdido y apareció. */
  recuperado: boolean
  /** Monto de la reposición que se acreditó al lector, y a quién. */
  reintegro: number
  lector_reintegro: string | null
}

export interface Ejemplar {
  id: string
  barcode: string
  location: string | null
  status: string
  dueDate: string | null
  borrowedBy: string | null
  /** Numeración del fascículo si es un número de una seriada (Vol. 3, Núm. 2). */
  enumeration: string | null
  /** Sede donde está ahora y sede a la que pertenece. */
  branch: string | null
  homeBranch: string | null
  /** Destino, si viaja entre sedes. */
  transitTo: string | null
}

export interface DashboardStats {
  totalItems: number
  totalUsers: number
  activeLoans: number
  overdueLoans: number
}

export interface ReporteDisponible {
  id: string
  title: string
  description: string
  lastGenerated: string | null
  rows: number
}

export interface Configuracion {
  institucion: {
    nombre: string
    codigo: string
    direccion: string
    telefono: string
    email: string
  }
  politicas_prestamo: {
    dias_estudiante: number
    dias_docente: number
    dias_personal: number
    max_estudiante: number
    max_docente: number
    max_personal: number
    renovaciones_permitidas: number
    multa_por_dia: number
  }
  notificaciones: {
    recordatorio_dias_antes: number
    canal: string
  }
  circulacion: {
    umbral_bloqueo: number
    dias_retiro_reserva: number
    precio_reposicion: number
    retorno_a_sede_propia: boolean
  }
}

/** Regla de circulación. Un id de dimensión en null significa "todas". */
export interface ReglaCirculacion {
  id: number
  categoria_id: number | null
  categoria: string
  tipo_item_id: number | null
  tipo_item: string
  biblioteca_id: number | null
  biblioteca: string
  prestable: boolean
  dias_prestamo: number
  max_prestamos: number
  max_renovaciones: number
  multa_por_dia: number
  multa_maxima: number | null
  dias_gracia: number
  max_reservas: number
}

export type DatosRegla = Omit<ReglaCirculacion, "id" | "categoria" | "tipo_item" | "biblioteca">

export interface OpcionDimension {
  id: number
  codigo: string
  nombre: string
}

export interface OpcionesRegla {
  categorias: OpcionDimension[]
  tipos_item: OpcionDimension[]
  bibliotecas: OpcionDimension[]
}

export interface Feriado {
  id: number
  /** AAAA-MM-DD */
  fecha: string
  descripcion: string
}

export interface CalendarioBiblioteca {
  /** 0 = lunes … 6 = domingo */
  dias_cerrados: number[]
  dias_cerrados_nombres: string[]
  feriados: Feriado[]
}

export interface SystemInfo {
  version: string
  ultima_actualizacion: string | null
  total_registros: number
  total_ejemplares: number
  total_usuarios: number
  total_prestamos: number
}

/** Mapea el usuario de la API a la forma que consume UserTable. */
export function mapUsuario(u: ApiUser) {
  // "inactive" = cuenta suspendida por el personal; "suspended" = bloqueada porque la
  // deuda supera el umbral configurado (una deuda menor no bloquea).
  let status: "active" | "suspended" | "inactive" = "active"
  if (!u.activo) status = "inactive"
  else if (u.bloqueado_por_deuda) status = "suspended"

  const codigo = u.categoria?.codigo?.toLowerCase() || ""
  let type: "student" | "teacher" | "staff" = "student"
  if (codigo === "doc" || codigo === "docente") type = "teacher"
  else if (codigo === "adm" || codigo === "staff") type = "staff"

  return {
    id: u.nro_carnet,
    name: `${u.nombre} ${u.apellido}`,
    email: u.email,
    type,
    department: u.departamento || "Sin asignar",
    status,
    activeLoans: u.prestamos_activos_count,
    totalLoans: u.total_prestamos_count,
    esPersonal: u.es_personal,
    registeredDate: u.fecha_creacion
      ? new Date(u.fecha_creacion).toLocaleDateString("es-VE")
      : "—",
  }
}

/** Un valor de faceta con cuántos títulos quedarían al elegirlo. */
export interface ValorFaceta {
  valor: string | number
  etiqueta: string | null
  cantidad: number
}

export interface FacetasCatalogo {
  disponibilidad: ValorFaceta[]
  tipos: ValorFaceta[]
  materias: ValorFaceta[]
  autores: ValorFaceta[]
  decadas: ValorFaceta[]
}

export type OrdenBusqueda = "relevancia" | "titulo" | "ano_desc" | "ano_asc"

export interface BusquedaCatalogo<T> {
  total: number
  pagina: number
  por_pagina: number
  paginas: number
  orden: OrdenBusqueda
  resultados: T[]
  facetas: FacetasCatalogo
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

// --- Sedes, reservas y traslados (Fase 5) -------------------------------------------

export interface Sede {
  id: number
  codigo: string
  nombre: string
  direccion: string | null
  telefono: string | null
  email: string | null
  /** Se pueden retirar reservas aquí. */
  punto_retiro: boolean
  /** Solo con `?con_uso=true`. */
  ejemplares?: number
  lectores?: number
}

export type EstadoReserva =
  | "Pendiente"
  | "EnTransito"
  | "EnEspera"
  | "Cumplida"
  | "Cancelada"
  | "Expirada"

export interface ReservaGestion {
  id: string
  biblioId: string
  title: string
  author: string | null
  userName: string
  userId: string
  priority: number
  status: EstadoReserva
  reservedOn: string | null
  itemBarcode: string | null
  callNumber: string | null
  pickupBranchId: number | null
  pickupBranch: string | null
  pickupBy: string | null
  waitingSince: string | null
  daysWaiting: number | null
  expiresToday: boolean
  suspended: boolean
  /** ISO (aaaa-mm-dd). */
  suspendedUntil: string | null
  notNeededAfter: string | null
  notes: string | null
  transitFromId: number | null
  transitFrom: string | null
  transitSent: boolean
  closedOn: string | null
}

export interface TituloPorSacar {
  biblioId: string
  title: string
  author: string | null
  holds: number
  toPull: number
  firstPatron: string
  firstPatronId: string
  pickupBranch: string | null
  reservedOn: string | null
  items: { barcode: string; callNumber: string | null; branch: string | null }[]
}

export type MotivoTraslado = "reserva" | "retorno" | "manual"
export type EstadoTraslado = "Solicitado" | "Enviado" | "Recibido" | "Cancelado"
export type VistaTraslados = "por_enviar" | "por_recibir" | "enviados" | "historial"

export interface Traslado {
  id: number
  barcode: string
  title: string
  callNumber: string | null
  fromId: number
  from: string | null
  toId: number
  to: string | null
  reason: MotivoTraslado
  status: EstadoTraslado
  patron: string | null
  patronId: string | null
  holdActive: boolean
  comment: string | null
  requestedOn: string | null
  sentOn: string | null
  receivedOn: string | null
  cancelledOn: string | null
  daysInTransit: number | null
}

export interface ResumenTraslados {
  sede_id: number | null
  por_enviar: number
  por_recibir: number
  enviados: number
}

// --- Adquisiciones (Fase 5) ----------------------------------------------------------

export interface Proveedor {
  id: number
  nombre: string
  contacto: string | null
  email: string | null
  telefono: string | null
  rif: string | null
  direccion: string | null
  /** Descuento habitual (%) que se propone en cada línea. */
  descuento: number
  /** Días que suele tardar en entregar; pasado ese plazo, el pedido está atrasado. */
  dias_entrega: number | null
  notas: string | null
  activo: boolean
  pedidos_vivos?: number
  facturas_abiertas?: number
}

export interface Fondo {
  id: number
  presupuesto_id: number
  presupuesto?: string
  codigo: string
  nombre: string
  biblioteca_id: number | null
  biblioteca?: string | null
  activo: boolean
  utilizable?: boolean
  asignado: number
  comprometido: number
  gastado: number
  disponible: number
}

export interface Presupuesto {
  id: number
  nombre: string
  fecha_inicio: string
  fecha_fin: string
  monto_total: number
  activo: boolean
  bloqueado: boolean
  asignado: number
  sin_asignar: number
  comprometido: number
  gastado: number
  fondos: Fondo[]
}

export type EstadoPedido = "Abierta" | "Cerrada" | "Recibida" | "Cancelada"
export type EstadoLinea = "Pendiente" | "Parcial" | "Recibida" | "Cancelada"

export interface LineaPedido {
  id: number
  orden_id: number
  biblio_id: number | null
  titulo: string
  autor: string | null
  isbn: string | null
  cantidad: number
  cantidad_recibida: number
  pendiente: number
  precio_unitario: number
  descuento: number
  costo_estimado: number
  total_estimado: number
  total_recibido: number
  fondo_id: number | null
  fondo: string | null
  estado: EstadoLinea
  notas: string | null
  /** Solo en "por recibir". */
  orden?: string
  biblioteca_entrega_id?: number | null
}

export interface Pedido {
  id: number
  nombre: string
  proveedor_id: number
  proveedor_nombre: string | null
  estado: EstadoPedido
  observaciones: string | null
  biblioteca_entrega_id: number | null
  biblioteca_entrega: string | null
  fecha_emision: string
  fecha_cierre: string | null
  fecha_recepcion: string | null
  titulos: number
  ejemplares: number
  recibidos: number
  total: number
  total_recibido: number
  dias_atraso: number | null
  lineas?: LineaPedido[]
}

export interface PedidoAtrasado {
  orden_id: number
  nombre: string
  proveedor_id: number
  proveedor_nombre: string
  proveedor_email: string | null
  fecha_cierre: string
  dias_atraso: number
  lineas: { id: number; titulo: string; isbn: string | null; pendiente: number }[]
}

export interface RecepcionFactura {
  id: number
  linea_id: number
  orden_id: number
  orden: string
  titulo: string
  biblio_id: number | null
  fondo: string | null
  cantidad: number
  costo_unitario: number
  costo_estimado: number
  total: number
  fecha: string
  ejemplares: string[]
}

export interface Factura {
  id: number
  proveedor_id: number
  proveedor_nombre: string | null
  numero: string
  fecha: string
  costo_envio: number
  fondo_envio_id: number | null
  fondo_envio: string | null
  cerrada: boolean
  fecha_cierre: string | null
  notas: string | null
  unidades: number
  subtotal: number
  total: number
  recepciones?: RecepcionFactura[]
}

export interface ResultadoRecepcion {
  recepcion_id: number
  linea_id: number
  biblio_id: number
  cantidad: number
  estado_linea: EstadoLinea
  estado_pedido: EstadoPedido
  ejemplares: ({ codigo_barras: string } & Pick<ResultadoDevolucion, "accion" | "reserva" | "traslado">)[]
}

export type EstadoSugerencia = "Pendiente" | "Aceptada" | "Rechazada" | "Pedida"

export interface Sugerencia {
  id: number
  titulo: string
  autor: string | null
  isbn: string | null
  editorial: string | null
  ano: number | null
  nota: string | null
  estado: EstadoSugerencia
  motivo: string | null
  fecha: string
  lector: string | null
  carnet: string | null
  gestionada_por: string | null
  fecha_gestion: string | null
  orden_id: number | null
  en_catalogo_id: number | null
}

export interface ResumenAdquisiciones {
  pedidos_abiertos: number
  pedidos_por_recibir: number
  pedidos_atrasados: number
  facturas_abiertas: number
  sugerencias_pendientes: number
  fondos: Fondo[]
}

// --- Seriadas (Fase 5) ---------------------------------------------------------------

export type UnidadFrecuencia = "dia" | "semana" | "mes" | "anio" | "irregular"
export type EstadoFasciculo = "Esperado" | "Recibido" | "Reclamado" | "Faltante"

export interface Fasciculo {
  id: number
  suscripcion_id: number
  numero: string
  fecha_esperada: string | null
  fecha_recepcion: string | null
  estado: EstadoFasciculo
  recibido: boolean
  /** Días pasados la fecha esperada más los de gracia; null si no está atrasado. */
  dias_atraso: number | null
  reclamos: number
  fecha_reclamo: string | null
  notas: string | null
  codigo_barras: string | null
  /** Solo en los listados generales (por recibir, atrasados). */
  titulo?: string
  issn?: string | null
  proveedor_nombre?: string | null
  proveedor_email?: string | null
}

export interface Suscripcion {
  id: number
  biblio_id: number | null
  titulo: string
  issn: string | null
  proveedor_id: number | null
  proveedor_nombre: string | null
  proveedor_email: string | null
  biblioteca_id: number | null
  biblioteca: string | null
  tipo_item_id: number | null
  crear_ejemplares: boolean
  frecuencia_unidad: UnidadFrecuencia
  frecuencia_cada: number
  periodicidad: string
  numeracion: string
  numeros_por_volumen: number | null
  fecha_inicio: string | null
  fecha_fin: string | null
  dias_gracia: number
  estado: "Activa" | "Vencida" | "Cancelada"
  notas: string | null
  fasciculos_recibidos: number
  fasciculos_esperados: number
  fasciculos_atrasados: number
  proximo: { id: number; numero: string; fecha_esperada: string | null } | null
  por_vencer: boolean
  fasciculos?: Fasciculo[]
}

export interface FasciculoPredicho {
  numero: string
  fecha_esperada: string
  volumen: number
  secuencia: number
}
