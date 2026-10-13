"use client"

import { createContext, useCallback, useContext, useEffect, useMemo, useState } from "react"

import { apiGet, apiPost, EVENTO_SESION_OPAC_EXPIRADA } from "@/lib/api"
import type { ResumenLector } from "@/lib/opac"

type EstadoLector = {
  /** El lector con sesión en el OPAC, o null. Independiente de la sesión del personal. */
  lector: ResumenLector | null
  cargando: boolean
  entrar: (carnet: string, clave: string) => Promise<ResumenLector>
  salir: () => Promise<void>
  /** Vuelve a pedir el resumen (contadores de préstamos, reservas y deuda). */
  recargar: () => Promise<void>
}

const LectorContext = createContext<EstadoLector | null>(null)

export function LectorProvider({ children }: { children: React.ReactNode }) {
  const [lector, setLector] = useState<ResumenLector | null>(null)
  const [cargando, setCargando] = useState(true)

  const recargar = useCallback(async () => {
    try {
      setLector(await apiGet<ResumenLector>("/opac/account"))
    } catch {
      setLector(null)
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
    () => ({ lector, cargando, entrar, salir, recargar }),
    [lector, cargando, entrar, salir, recargar],
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
