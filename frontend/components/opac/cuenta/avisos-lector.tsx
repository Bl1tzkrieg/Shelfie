"use client"

import { useEffect, useState } from "react"
import { Loader2 } from "lucide-react"
import { toast } from "sonner"

import { apiGet, mensajeDeError } from "@/lib/api"

interface AvisoLector {
  id: number
  tipo: string
  asunto: string
  cuerpo: string
  estado: "Pendiente" | "Enviado" | "Fallido"
  creado: string
  enviado: string | null
}

/** Los correos que la biblioteca le mandó al lector, por si no le llegaron. */
export function AvisosLector() {
  const [avisos, setAvisos] = useState<AvisoLector[] | null>(null)

  useEffect(() => {
    apiGet<AvisoLector[]>("/opac/account/notices")
      .then(setAvisos)
      .catch((e) => toast.error("No se pudieron cargar tus avisos", { description: mensajeDeError(e) }))
  }, [])

  if (!avisos) return <Loader2 className="mx-auto my-8 h-5 w-5 animate-spin text-muted-foreground" />
  if (avisos.length === 0) {
    return <p className="py-8 text-center text-muted-foreground">La biblioteca todavía no te ha enviado avisos.</p>
  }
  return (
    <ul className="space-y-3">
      {avisos.map((a) => (
        <li key={a.id}>
          <details className="rounded-lg border border-border bg-card">
            <summary className="flex cursor-pointer flex-wrap items-baseline justify-between gap-x-4 gap-y-1 px-4 py-3">
              <span className="font-medium text-foreground">{a.asunto}</span>
              <span className="text-xs text-muted-foreground">
                {a.enviado ? `Enviado el ${a.enviado}` : a.estado === "Fallido" ? "No se pudo enviar" : "Por enviar"}
              </span>
            </summary>
            <pre className="whitespace-pre-wrap border-t px-4 py-3 font-sans text-sm text-foreground">{a.cuerpo}</pre>
          </details>
        </li>
      ))}
    </ul>
  )
}
