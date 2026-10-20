"use client"

import { useEffect, useState } from "react"
import Link from "next/link"
import { AlertTriangle } from "lucide-react"

import { useSesion } from "@/components/auth/sesion-provider"
import { apiGet } from "@/lib/api"
import type { EstadoRespaldo } from "@/lib/types"

/**
 * Aviso rojo para el administrador cuando el respaldo está atrasado o falló. Lee
 * `alerta_respaldo` de la sesión (se actualiza tras cada respaldo) y pide el motivo
 * ("El último respaldo es de hace N días / falló: …") a /settings/backup.
 */
export function AvisoRespaldo() {
  const { usuario } = useSesion()
  const alerta = !!usuario?.alerta_respaldo
  const [motivo, setMotivo] = useState<string | null>(null)

  useEffect(() => {
    if (!alerta) return
    let vigente = true
    apiGet<EstadoRespaldo>("/settings/backup")
      .then((e) => vigente && setMotivo(e.motivo))
      .catch(() => vigente && setMotivo(null))
    return () => {
      vigente = false
    }
  }, [alerta, usuario])

  if (!alerta) return null
  return (
    <div role="alert"
         className="flex flex-wrap items-center gap-x-3 gap-y-1 border-b border-destructive/30 bg-destructive/10 px-4 py-2 text-sm text-destructive sm:px-6">
      <AlertTriangle className="h-4 w-4 shrink-0" aria-hidden />
      <span className="min-w-0 flex-1 font-medium">
        {motivo ?? "Revisa el respaldo de la biblioteca."}
      </span>
      <Link href="/configuracion" className="shrink-0 font-semibold underline underline-offset-2">
        Ir a Configuración
      </Link>
    </div>
  )
}
