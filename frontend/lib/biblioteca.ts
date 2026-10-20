"use client"

import { useEffect, useState } from "react"

import { apiGet } from "@/lib/api"
import type { Configuracion } from "@/lib/types"

// El nombre de la biblioteca casi nunca cambia: se pide una vez por pestaña y no en cada
// navegación (el encabezado y la barra lateral se vuelven a montar con cada página).
let nombreEnMemoria: string | null | undefined

/** Tras cambiar el nombre en Configuración, el próximo encabezado lo vuelve a pedir. */
export function olvidarNombreBiblioteca() {
  nombreEnMemoria = undefined
}

/** El nombre de la biblioteca (GET /settings, público), o null mientras llega o si falla. */
export function useNombreBiblioteca(): string | null {
  const [nombre, setNombre] = useState<string | null>(nombreEnMemoria ?? null)

  useEffect(() => {
    if (nombreEnMemoria !== undefined) return
    let vigente = true
    apiGet<Configuracion>("/settings")
      .then((c) => {
        nombreEnMemoria = c.biblioteca.nombre
        if (vigente) setNombre(nombreEnMemoria)
      })
      .catch(() => {
        if (vigente) setNombre(null)
      })
    return () => {
      vigente = false
    }
  }, [])

  return nombre
}
