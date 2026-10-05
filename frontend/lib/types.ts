/** Contratos que devuelve el backend, compartidos por las pantallas. */

export interface Categoria {
  codigo: string
  descripcion: string
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
}

export interface Ejemplar {
  id: string
  barcode: string
  location: string | null
  status: string
  dueDate: string | null
  borrowedBy: string | null
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
  let status: "active" | "suspended" | "inactive" = "active"
  if (!u.activo) status = "inactive"
  else if (u.saldo_multas > 0) status = "suspended"

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
    registeredDate: u.fecha_creacion
      ? new Date(u.fecha_creacion).toLocaleDateString("es-VE")
      : "—",
  }
}
