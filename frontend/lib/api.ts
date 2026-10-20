/**
 * Origen del backend. Vacío (lo normal) = el mismo origen: en la instalación
 * FastAPI sirve la API y estas páginas exportadas en el mismo puerto.
 *
 * Para `npm run dev` contra uvicorn en :8000, `frontend/.env.local` define
 * NEXT_PUBLIC_API_URL=http://localhost:8000 (sin /api/v1); el backend ya admite
 * http://localhost:3000 en CORS_ORIGINS.
 */
const API_URL = `${process.env.NEXT_PUBLIC_API_URL ?? ""}/api/v1`

/**
 * Evento que se emite cuando el backend responde 401 fuera del login: la sesión
 * no existe o expiró. El proveedor de sesión lo escucha y manda al login.
 */
export const EVENTO_SESION_EXPIRADA = "shelfie:sesion-expirada"

function avisarSiSesionExpirada(status: number, path: string) {
  if (status !== 401 || typeof window === "undefined") return
  // Equivocarse de contraseña en el login o al cambiarla no es una sesión vencida.
  if (!path.startsWith("/auth/")) {
    window.dispatchEvent(new Event(EVENTO_SESION_EXPIRADA))
  }
}

/** Forma de cada error de validación (Pydantic, y los 422 de los servicios, p. ej. MARC). */
export interface ErrorValidacion {
  loc?: (string | number)[]
  msg: string
}

/** Error con el `detail` que devuelve FastAPI, listo para mostrarse en un toast. */
export class ApiError extends Error {
  status: number
  /** Errores con ubicación, para marcarlos junto a su campo en un formulario. */
  errores: ErrorValidacion[]

  constructor(message: string, status: number, errores: ErrorValidacion[] = []) {
    super(message)
    this.name = "ApiError"
    this.status = status
    this.errores = errores
  }
}

async function errorDeRespuesta(response: Response): Promise<ApiError> {
  try {
    const data: { detail?: unknown } = await response.json()
    const detail = data?.detail
    if (typeof detail === "string") return new ApiError(detail, response.status)
    if (Array.isArray(detail)) {
      const errores = detail as ErrorValidacion[]
      const mensaje = errores
        .map((e) => {
          const campo = Array.isArray(e.loc) ? e.loc[e.loc.length - 1] : null
          return campo && !e.msg.includes(String(campo)) ? `${campo}: ${e.msg}` : e.msg
        })
        .join(" · ")
      return new ApiError(mensaje, response.status, errores)
    }
  } catch {
    // respuesta sin cuerpo JSON
  }
  return new ApiError(`Error ${response.status}`, response.status)
}

export async function api<T = unknown>(
  path: string,
  options: RequestInit = {}
): Promise<T> {
  let response: Response
  try {
    response = await fetch(`${API_URL}${path}`, {
      cache: "no-store",
      // La sesión viaja en una cookie httpOnly: hay que enviarla en cada petición.
      credentials: "include",
      ...options,
      headers: {
        "Content-Type": "application/json",
        ...(options.headers || {}),
      },
    })
  } catch {
    throw new ApiError("No se pudo contactar el backend. ¿Está encendido?", 0)
  }

  if (!response.ok) {
    avisarSiSesionExpirada(response.status, path)
    throw await errorDeRespuesta(response)
  }

  if (response.status === 204) return undefined as T
  return (await response.json()) as T
}

export const apiGet = <T,>(path: string) => api<T>(path)

export const apiPost = <T,>(path: string, body?: unknown) =>
  api<T>(path, { method: "POST", body: JSON.stringify(body ?? {}) })

export const apiPut = <T,>(path: string, body: unknown) =>
  api<T>(path, { method: "PUT", body: JSON.stringify(body) })

export const apiPatch = <T,>(path: string, body: unknown) =>
  api<T>(path, { method: "PATCH", body: JSON.stringify(body) })

export const apiDelete = <T,>(path: string) => api<T>(path, { method: "DELETE" })

/** Envía un archivo tal cual como cuerpo de la petición (p. ej. una importación MARC). */
export async function apiUpload<T>(path: string, archivo: Blob): Promise<T> {
  return api<T>(path, {
    method: "POST",
    body: archivo,
    headers: { "Content-Type": "application/octet-stream" },
  })
}

/**
 * Descarga un archivo generado por el backend.
 *
 * Se hace vía blob en vez de apuntar un <a href> directo al endpoint para poder
 * mostrar el `detail` del error cuando la generación falla, en lugar de dejar al
 * navegador abrir una pestaña con el JSON del error.
 */
export async function apiDownload(path: string, fallbackName: string): Promise<void> {
  const response = await fetch(`${API_URL}${path}`, {
    cache: "no-store",
    credentials: "include",
  })
  if (!response.ok) {
    avisarSiSesionExpirada(response.status, path)
    throw await errorDeRespuesta(response)
  }

  // El nombre sugerido viene en Content-Disposition.
  const disposition = response.headers.get("Content-Disposition") || ""
  const match = disposition.match(/filename="?([^"]+)"?/)
  const nombre = match?.[1] || fallbackName

  const blob = await response.blob()
  const url = URL.createObjectURL(blob)
  const link = document.createElement("a")
  link.href = url
  link.download = nombre
  document.body.appendChild(link)
  link.click()
  link.remove()
  // Revocar en el mismo tick puede abortar la descarga en Firefox y Safari.
  setTimeout(() => URL.revokeObjectURL(url), 0)
}

/** Mensaje legible para cualquier error capturado en un handler. */
export function mensajeDeError(error: unknown): string {
  if (error instanceof ApiError) return error.message
  if (error instanceof Error) return error.message
  return "Ocurrió un error inesperado"
}
