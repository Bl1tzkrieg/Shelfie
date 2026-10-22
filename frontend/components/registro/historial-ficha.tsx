"use client"

import { useEffect, useState } from "react"
import Link from "next/link"
import { History } from "lucide-react"

import { useSesion } from "@/components/auth/sesion-provider"
import { ListaAcciones } from "@/components/registro/lista-acciones"
import { apiGet } from "@/lib/api"
import type { PaginaRegistro } from "@/lib/types"

/**
 * Las últimas acciones sobre un miembro del personal o un libro, dentro de su ficha.
 * Solo para el administrador; los demás no ven la sección.
 */
export function HistorialFicha({ filtro, recarga = 0 }: {
  filtro: { usuario: string } | { biblio_id: number }
  /** Cambia cuando la ficha registró algo nuevo, para volver a pedir el historial. */
  recarga?: number
}) {
  const { tienePermiso } = useSesion()
  const permitido = tienePermiso("superbibliotecario")
  const [pagina, setPagina] = useState<PaginaRegistro | null>(null)
  const consulta = new URLSearchParams(
    Object.entries(filtro).map(([k, v]) => [k, String(v)])).toString()

  useEffect(() => {
    if (!permitido) return
    let vigente = true
    apiGet<PaginaRegistro>(`/logs?${consulta}&por_pagina=10`)
      .then((r) => vigente && setPagina(r))
      .catch(() => vigente && setPagina(null))
    return () => {
      vigente = false
    }
  }, [permitido, consulta, recarga])

  if (!permitido) return null
  return (
    <section aria-labelledby="historial-ficha" className="rounded-xl border border-border/80 bg-card shadow-papel">
      <div className="flex items-center justify-between border-b border-border px-6 py-4">
        <h3 id="historial-ficha" className="flex items-center gap-2 font-semibold text-foreground">
          <History className="h-4 w-4" aria-hidden />Historial de cambios
        </h3>
        {pagina && pagina.total > pagina.filas.length && (
          <Link href={`/registro/?${consulta}`} className="text-sm text-primary hover:underline">
            Ver las {pagina.total} acciones
          </Link>
        )}
      </div>
      {pagina ? <ListaAcciones filas={pagina.filas} compacta />
        : <p className="py-6 text-center text-sm text-muted-foreground">Cargando…</p>}
    </section>
  )
}
