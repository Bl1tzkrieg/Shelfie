"use client"

import { createContext, useCallback, useContext, useEffect, useMemo, useState } from "react"

import { useSesion } from "@/components/auth/sesion-provider"
import { apiGet } from "@/lib/api"
import { EVENTO_SEDE, fijarSedeEfectiva, guardarSede, leerSede } from "@/lib/sede"
import type { Sede } from "@/lib/types"

type EstadoSedes = {
  sedes: Sede[]
  /** Sede de trabajo efectiva: la elegida en este navegador, la del usuario o la primera. */
  sedeId: number | null
  sede: Sede | null
  cambiarSede: (id: number) => void
  recargarSedes: () => Promise<void>
}

const SedeContext = createContext<EstadoSedes | null>(null)

export function SedeProvider({ children }: { children: React.ReactNode }) {
  const { usuario } = useSesion()
  const [sedes, setSedes] = useState<Sede[]>([])
  // Se lee al montar: el proveedor solo existe en el navegador (componente cliente).
  const [elegida, setElegida] = useState<number | null>(() => leerSede())

  const recargarSedes = useCallback(async () => {
    try {
      setSedes(await apiGet<Sede[]>("/settings/branches"))
    } catch {
      setSedes([])
    }
  }, [])

  useEffect(() => {
    if (!usuario) return
    recargarSedes()
  }, [usuario, recargarSedes])

  useEffect(() => {
    // Otra pestaña cambió la sede, o esta misma desde el selector.
    const sincronizar = () => setElegida(leerSede())
    window.addEventListener(EVENTO_SEDE, sincronizar)
    window.addEventListener("storage", sincronizar)
    return () => {
      window.removeEventListener(EVENTO_SEDE, sincronizar)
      window.removeEventListener("storage", sincronizar)
    }
  }, [])

  const sedeId = useMemo(() => {
    if (sedes.length === 0) return null
    const existe = (id: number | null | undefined) => id != null && sedes.some((s) => s.id === id)
    if (existe(elegida)) return elegida
    if (existe(usuario?.biblioteca_id)) return usuario!.biblioteca_id
    // El mismo respaldo que el backend (sedes.primera): la de menor id, no la primera por nombre.
    return Math.min(...sedes.map((s) => s.id))
  }, [sedes, elegida, usuario])

  useEffect(() => {
    fijarSedeEfectiva(sedeId)
  }, [sedeId])

  useEffect(() => {
    // Una sede guardada que ya no existe no debe seguir viajando en las peticiones.
    if (sedes.length > 0 && elegida !== null && !sedes.some((s) => s.id === elegida)) {
      guardarSede(null)
    }
  }, [sedes, elegida])

  const cambiarSede = useCallback((id: number) => guardarSede(id), [])

  const valor = useMemo(
    () => ({
      sedes,
      sedeId,
      sede: sedes.find((s) => s.id === sedeId) ?? null,
      cambiarSede,
      recargarSedes,
    }),
    [sedes, sedeId, cambiarSede, recargarSedes],
  )

  return <SedeContext.Provider value={valor}>{children}</SedeContext.Provider>
}

export function useSedes(): EstadoSedes {
  const contexto = useContext(SedeContext)
  if (!contexto) throw new Error("useSedes debe usarse dentro de <SedeProvider>")
  return contexto
}
