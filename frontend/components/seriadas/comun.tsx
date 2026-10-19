import type { EstadoFasciculo } from "@/lib/types"
import { cn } from "@/lib/utils"

const ESTILO: Record<EstadoFasciculo, string> = {
  Esperado: "bg-secondary text-secondary-foreground",
  Recibido: "bg-primary/10 text-primary",
  Reclamado: "bg-accent/25 text-accent-foreground",
  Faltante: "bg-muted text-muted-foreground line-through",
}

export function EstadoFasciculoBadge({ estado, atraso }: { estado: EstadoFasciculo; atraso?: number | null }) {
  return (
    <span className={cn("inline-flex items-center gap-1 rounded-full px-2.5 py-0.5 text-xs font-medium",
                        atraso ? "bg-destructive/10 text-destructive" : ESTILO[estado])}>
      {atraso ? `${estado === "Reclamado" ? "Reclamado · " : ""}${atraso} d de atraso` : estado}
    </span>
  )
}

export function fechaIso(iso: string | null) {
  if (!iso) return "—"
  const [a, m, d] = iso.split("-")
  return `${d}/${m}/${a}`
}

