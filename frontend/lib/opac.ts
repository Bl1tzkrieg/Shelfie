/** Tipos del OPAC (catálogo público y cuenta del lector). Espejo de app/services/opac.py y cuenta_opac.py. */

import type { FacetasCatalogo } from "@/lib/types"

export interface SedePublica {
  id: number
  codigo: string
  nombre: string
  direccion: string | null
  telefono: string | null
  email: string | null
}

export interface Biblioteca {
  nombre: string | null
  direccion: string | null
  telefono: string | null
  email: string | null
  sedes: SedePublica[]
}

/** Un título tal como aparece en una lista de resultados. */
export interface TituloPublico {
  id: string
  titulo: string
  autor: string | null
  isbn: string | null
  ano_publicacion: number | null
  materia: string | null
  ejemplares: number
  disponibles: number
  estado: string
  ubicaciones: string[]
}

export interface ResultadosOpac {
  query?: string
  total: number
  pagina: number
  paginas: number
  resultados: TituloPublico[]
  facetas: FacetasCatalogo
}

export interface EjemplarPublico {
  id: number
  sede_id: number | null
  sede: string
  signatura: string | null
  numeracion: string | null
  tipo: string | null
  codigo_barras: string
  estado: string
  disponible: boolean
}

export interface FichaPublica extends TituloPublico {
  subtitulo: string | null
  responsabilidad: string | null
  edicion: string | null
  lugar: string | null
  editorial: string | null
  descripcion_fisica: string | null
  serie: string | null
  issn: string | null
  periodicidad: string | null
  notas: string[]
  resumen: string | null
  materias: string[]
  otros_autores: string[]
  plantilla: string
  ejemplares_detalle: EjemplarPublico[]
  por_sede: { sede_id: number | null; sede: string; ejemplares: number; disponibles: number }[]
  reservas: number
  reservable: boolean
}

// --- Cuenta del lector ---------------------------------------------------------------------

export interface ResumenLector {
  carnet: string
  nombre: string
  apellido: string
  email: string
  categoria: string | null
  sede: string | null
  prestamos: number
  vencidos: number
  reservas: number
  para_retirar: number
  saldo: number
  umbral_bloqueo: number
  bloqueado: boolean
}

export interface PrestamoLector {
  id: number
  biblio_id: number
  titulo: string
  autor: string | null
  codigo_barras: string
  numeracion: string | null
  prestado: string
  vence: string
  vence_iso: string
  vencido: boolean
  dias_atraso: number
  renovaciones: number
  renovaciones_permitidas: number
  renovable: boolean
  motivo: string | null
  /** Multa por atraso que se cobra si se renueva ahora (0 si no está vencido). */
  cargo_al_renovar: number
  /** Si con ese cargo la deuda pasa del máximo y el lector queda bloqueado. */
  bloquearia: boolean
}

export type EstadoReserva = "Pendiente" | "EnTransito" | "EnEspera"

export interface ReservaLector {
  id: string
  biblioId: string
  title: string
  author: string | null
  priority: number
  status: EstadoReserva
  reservedOn: string
  pickupBranchId: number | null
  pickupBranch: string | null
  pickupBy: string | null
  suspended: boolean
  suspendedUntil: string | null
  notNeededAfter: string | null
}

export interface HistorialLector {
  id: number
  biblio_id: number
  titulo: string
  autor: string | null
  prestado: string
  devuelto: string
  perdido: boolean
}

export interface MultasLector {
  saldo: number
  umbral_bloqueo: number
  bloqueado: boolean
  movimientos: { id: number; tipo: string; monto: number; descripcion: string | null; fecha: string }[]
}

export type EstadoSugerencia = "Pendiente" | "Aceptada" | "Rechazada" | "Pedida"

export interface SugerenciaLector {
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
}

export interface ListaLector {
  id: number
  nombre: string
  publica: boolean
  cantidad: number
  creada: string
  /** Solo cuando se piden las listas para un título: si ya lo tiene. */
  contiene?: boolean
}

export interface ListaConTitulos extends ListaLector {
  propia: boolean
  autor: string | null
  titulos: TituloPublico[]
}

/** Movimientos de la cuenta en palabras del lector. */
export const TIPOS_MOVIMIENTO: Record<string, string> = {
  MULTA_ATRASO: "Multa por atraso",
  REPOSICION: "Reposición de material perdido",
  PAGO: "Pago",
  CONDONACION: "Condonación",
  REINTEGRO: "Reintegro",
  AJUSTE: "Ajuste",
}

export function formatoBs(monto: number) {
  return `Bs. ${monto.toLocaleString("es-VE", { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`
}

const MESES = ["ene", "feb", "mar", "abr", "may", "jun", "jul", "ago", "sep", "oct", "nov", "dic"]

/** "2026-10-09" → "09 oct 2026", el mismo formato que las fechas que arma el backend. */
export function fechaCorta(iso: string) {
  const [ano, mes, dia] = iso.split("-")
  const nombre = MESES[Number(mes) - 1]
  return nombre ? `${dia} ${nombre} ${ano}` : iso
}
