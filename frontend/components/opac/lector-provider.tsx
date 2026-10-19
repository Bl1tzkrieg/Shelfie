"use client"

import { createContext, useCallback, useContext, useEffect, useMemo, useState } from "react"

import { ApiError, apiGet, apiPost, EVENTO_SESION_OPAC_EXPIRADA, mensajeDeError } from "@/lib/api"
import type { ResumenLector } from "@/lib/opac"

type EstadoLector = {
  /** El lector con sesión en el OPAC, o null. Independiente de la sesión del personal. */
  lector: ResumenLector | null
  cargando: boolean
  /** No se pudo preguntar por la sesión (backend caído, red): no es lo mismo que no tenerla. */
  errorDeConexion: string | null
  entrar: (carnet: string, clave: string) => Promise<ResumenLector>
  salir: () => Promise<void>
  /** Vuelve a pedir el resumen (contadores de préstamos, reservas y deuda). */
  recargar: () => Promise<void>
}

const LectorContext = createContext<EstadoLector | null>(null)

export function LectorProvider({ children }: { children: React.ReactNode }) {
  const [lector, setLector] = useState<ResumenLector | null>(null)
  const [cargando, setCargando] = useState(true)
  const [errorDeConexion, setErrorDeConexion] = useState<string | null>(null)

  const recargar = useCallback(async () => {
    try {
      setLector(await apiGet<ResumenLector>("/opac/account"))
      setErrorDeConexion(null)
    } catch (error) {
      // Solo un 401 dice que no hay sesión. Con la red o el backend caídos se conserva
      // lo que había (la cabecera no pasa a «no identificado» por un fallo pasajero).
      if (error instanceof ApiError && error.status === 401) {
        setLector(null)
        setErrorDeConexion(null)
      } else {
        setErrorDeConexion(mensajeDeError(error))
      }
    }
  }, [])

  useEffect(() => {
    recargar().finally(() => setCargando(false))
  }, [recargar])

  useEffect(() => {
    const alExpirar = () => setLector(null)
    window.addEventListener(EVENTO_SESION_OPAC_EXPIRADA, alExpirar)
    return () => window.removeEventListener(EVENTO_SESION_OPAC_EXPIRADA, alExpirar)
  }, [])

  const entrar = useCallback(async (carnet: string, clave: string) => {
    const resumen = await apiPost<ResumenLector>("/opac/login", { username: carnet, password: clave })
    setLector(resumen)
    setErrorDeConexion(null)
    return resumen
  }, [])

  const salir = useCallback(async () => {
    try {
      await apiPost("/opac/logout")
    } finally {
      setLector(null)
    }
  }, [])

  const valor = useMemo(
    () => ({ lector, cargando, errorDeConexion, entrar, salir, recargar }),
    [lector, cargando, errorDeConexion, entrar, salir, recargar],
  )
  return <LectorContext.Provider value={valor}>{children}</LectorContext.Provider>
}

export function useLector(): EstadoLector {
  const contexto = useContext(LectorContext)
  if (!contexto) throw new Error("useLector debe usarse dentro de <LectorProvider>")
  return contexto
}

/** Ruta de entrada al OPAC que vuelve a la página actual. */
export function rutaDeEntrada(destino: string) {
  return destino && destino !== "/opac" ? `/opac/entrar?next=${encodeURIComponent(destino)}` : "/opac/entrar"
}

/** La página actual con su query string (?q=…), para volver a ella después de entrar. */
export function destinoActual(pathname: string) {
  return typeof window !== "undefined" && window.location.pathname === pathname
    ? pathname + window.location.search
    : pathname
}

// ¿Hubo navegación dentro del OPAC en esta pestaña? «Volver» usa el historial solo si sí:
// quien llegó por un enlace externo no debe salir del sitio.
let paginasVistas = 0
export function registrarPaginaVista() {
  paginasVistas += 1
}
export function vinoDesdeElOpac() {
  return paginasVistas > 1
}
