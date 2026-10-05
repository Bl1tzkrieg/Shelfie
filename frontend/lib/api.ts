const API_URL = process.env.NEXT_PUBLIC_API_URL

/** Error con el `detail` que devuelve FastAPI, listo para mostrarse en un toast. */
export class ApiError extends Error {
  status: number

  constructor(message: string, status: number) {
    super(message)
    this.name = "ApiError"
    this.status = status
  }
}

/** Forma de cada error de validación que devuelve Pydantic. */
interface ErrorValidacion {
  loc?: (string | number)[]
  msg: string
}

async function extraerMensaje(response: Response): Promise<string> {
  try {
    const data: { detail?: unknown } = await response.json()
    const detail = data?.detail
    if (typeof detail === "string") return detail
    // Los errores de validación de Pydantic llegan como lista de objetos.
    if (Array.isArray(detail)) {
      return (detail as ErrorValidacion[])
        .map((e) => {
          const campo = Array.isArray(e.loc) ? e.loc[e.loc.length - 1] : null
          return campo ? `${campo}: ${e.msg}` : e.msg
        })
        .join(" · ")
    }
  } catch {
    // respuesta sin cuerpo JSON
  }
  return `Error ${response.status}`
}

export async function api<T = unknown>(
  path: string,
  options: RequestInit = {}
): Promise<T> {
  if (!API_URL) {
    throw new ApiError(
      "Falta NEXT_PUBLIC_API_URL. Crea frontend/.env.local (ver .env.example).",
      0
    )
  }

  let response: Response
  try {
    response = await fetch(`${API_URL}${path}`, {
      cache: "no-store",
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
    throw new ApiError(await extraerMensaje(response), response.status)
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

/**
 * Descarga un archivo generado por el backend.
 *
 * Se hace vía blob en vez de apuntar un <a href> directo al endpoint para poder
 * mostrar el `detail` del error cuando la generación falla, en lugar de dejar al
 * navegador abrir una pestaña con el JSON del error.
 */
export async function apiDownload(path: string, fallbackName: string): Promise<void> {
  if (!API_URL) {
    throw new ApiError("Falta NEXT_PUBLIC_API_URL.", 0)
  }

  const response = await fetch(`${API_URL}${path}`, { cache: "no-store" })
  if (!response.ok) {
    throw new ApiError(await extraerMensaje(response), response.status)
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
  URL.revokeObjectURL(url)
}

/** Mensaje legible para cualquier error capturado en un handler. */
export function mensajeDeError(error: unknown): string {
  if (error instanceof ApiError) return error.message
  if (error instanceof Error) return error.message
  return "Ocurrió un error inesperado"
}
