"use client"

import { useEffect, useState } from "react"
import Link from "next/link"

import { EstadoAvisoBadge } from "@/components/configuracion/avisos/cola-avisos"
import { apiGet } from "@/lib/api"
import type { Aviso } from "@/lib/types"

/** Últimos correos que recibió el lector (en su ficha de la intranet). */
export function AvisosUsuario({ carnet }: { carnet: string }) {
  const [avisos, setAvisos] = useState<Aviso[] | null>(null)

  useEffect(() => {
    apiGet<Aviso[]>(`/notices/queue?carnet=${encodeURIComponent(carnet)}`).then(setAvisos).catch(() => setAvisos([]))
  }, [carnet])

  if (!avisos || avisos.length === 0) return null
  return (
    <div className="rounded-lg border border-border bg-card shadow-papel">
      <div className="flex items-center justify-between border-b border-border px-6 py-4">
        <h3 className="font-semibold text-foreground">Avisos enviados</h3>
        <Link href="/configuracion/avisos" className="text-sm text-primary hover:underline">Cola de correos</Link>
      </div>
      <ul className="divide-y divide-border">
        {avisos.slice(0, 10).map((a) => (
          <li key={a.id} className="flex flex-wrap items-center justify-between gap-2 px-6 py-3 text-sm">
            <span className="min-w-0">
              <span className="font-medium text-foreground">{a.tipo}</span>
              <span className="block truncate text-muted-foreground">{a.asunto}</span>
            </span>
            <span className="flex items-center gap-2">
              <span className="tabular-nums text-muted-foreground">{a.enviado ?? a.creado}</span>
              <EstadoAvisoBadge estado={a.estado} />
            </span>
          </li>
        ))}
      </ul>
    </div>
  )
}
