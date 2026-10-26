import Link from "next/link"
import { BookOpen } from "lucide-react"

import type { TituloPublico } from "@/lib/opac"
import { cn } from "@/lib/utils"

/** Disponibilidad en una línea: "2 de 3 disponibles" o "Todos prestados". */
export function Disponibilidad({ disponibles, ejemplares }: { disponibles: number; ejemplares: number }) {
  if (ejemplares === 0) {
    return <span className="text-sm text-muted-foreground">Sin ejemplares en la biblioteca</span>
  }
  return (
    <span className={cn("inline-flex items-center gap-1.5 text-sm", disponibles > 0 ? "text-primary" : "text-muted-foreground")}>
      <span aria-hidden className={cn("h-2 w-2 rounded-full", disponibles > 0 ? "bg-primary" : "bg-muted-foreground/50")} />
      {disponibles > 0
        ? `${disponibles} de ${ejemplares} disponible${disponibles === 1 ? "" : "s"}`
        : ejemplares === 1 ? "Prestado" : "Todos prestados"}
    </span>
  )
}

/** Un título en una lista de resultados (búsqueda, listas). */
export function TituloResultado({ titulo, acciones }: { titulo: TituloPublico; acciones?: React.ReactNode }) {
  const detalle = [titulo.autor, titulo.ano_publicacion].filter(Boolean).join(" · ")
  return (
    <li className="relative flex gap-4 overflow-hidden rounded-xl border border-border/80 bg-card p-4 pl-5 shadow-papel sm:p-5 sm:pl-6">
      {/* Lomo: una franja teal a la izquierda, como la etiqueta de un libro en el estante. */}
      <span aria-hidden className="absolute inset-y-0 left-0 w-1 bg-primary/25" />
      <div className="hidden h-20 w-14 shrink-0 items-center justify-center rounded bg-secondary sm:flex" aria-hidden>
        <BookOpen className="h-6 w-6 text-secondary-foreground/60" />
      </div>
      <div className="min-w-0 flex-1 space-y-1">
        <Link href={`/opac/registro/${titulo.id}`} className="font-medium text-foreground hover:text-primary hover:underline">
          {titulo.titulo}
        </Link>
        {detalle && <p className="text-sm text-muted-foreground">{detalle}</p>}
        <div className="flex flex-wrap items-center gap-x-4 gap-y-1">
          <Disponibilidad disponibles={titulo.disponibles} ejemplares={titulo.ejemplares} />
          {titulo.ubicaciones.length > 0 && (
            <span className="font-mono text-sm font-semibold tracking-tight text-primary">{titulo.ubicaciones.join(", ")}</span>
          )}
        </div>
      </div>
      {acciones && <div className="flex shrink-0 items-start">{acciones}</div>}
    </li>
  )
}
