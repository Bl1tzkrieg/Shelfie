"use client"

import { useState } from "react"
import { Check } from "lucide-react"

import type { FacetasCatalogo, ValorFaceta } from "@/lib/types"
import { cn } from "@/lib/utils"

/** Parámetro de la URL que controla cada grupo de facetas. */
export type ClaveFaceta = "disponible" | "tipo" | "materia" | "autor" | "decada"

const GRUPOS: { clave: ClaveFaceta; campo: keyof FacetasCatalogo; titulo: string }[] = [
  { clave: "disponible", campo: "disponibilidad", titulo: "Disponibilidad" },
  { clave: "tipo", campo: "tipos", titulo: "Tipo de material" },
  { clave: "materia", campo: "materias", titulo: "Materia" },
  { clave: "autor", campo: "autores", titulo: "Autor" },
  { clave: "decada", campo: "decadas", titulo: "Año de publicación" },
]

const VISIBLES = 5

interface FacetasBusquedaProps {
  facetas: FacetasCatalogo
  /** Valor elegido en cada grupo (tal como va en la URL). */
  seleccion: Partial<Record<ClaveFaceta, string>>
  onElegir: (clave: ClaveFaceta, valor: string | null) => void
}

/** "Refinar la búsqueda", como en Koha: cada valor dice cuántos títulos quedarían. */
export function FacetasBusqueda({ facetas, seleccion, onElegir }: FacetasBusquedaProps) {
  return (
    <div className="space-y-6">
      {GRUPOS.map(({ clave, campo, titulo }) => {
        const valores = facetas[campo].filter((v) => v.cantidad > 0)
        const elegido = seleccion[clave]
        if (valores.length === 0 && !elegido) return null
        return (
          <GrupoFaceta
            key={clave}
            titulo={titulo}
            valores={valores}
            elegido={elegido}
            onElegir={(v) => onElegir(clave, v)}
          />
        )
      })}
    </div>
  )
}

function GrupoFaceta({
  titulo,
  valores,
  elegido,
  onElegir,
}: {
  titulo: string
  valores: ValorFaceta[]
  elegido?: string
  onElegir: (valor: string | null) => void
}) {
  const [todos, setTodos] = useState(false)
  const lista = todos ? valores : valores.slice(0, VISIBLES)

  return (
    <section aria-label={titulo}>
      <h3 className="mb-2 text-xs font-semibold uppercase tracking-wide text-muted-foreground">
        {titulo}
      </h3>
      <ul className="space-y-0.5">
        {lista.map((v) => {
          const valor = String(v.valor)
          const activo = elegido === valor
          return (
            <li key={valor}>
              <button
                type="button"
                aria-pressed={activo}
                onClick={() => onElegir(activo ? null : valor)}
                className={cn(
                  "flex w-full items-center gap-2 rounded-md px-2 py-1.5 text-left text-sm transition-colors",
                  activo
                    ? "bg-primary/10 font-medium text-primary"
                    : "text-foreground hover:bg-muted"
                )}
              >
                <span className="flex h-4 w-4 shrink-0 items-center justify-center">
                  {activo && <Check className="h-3.5 w-3.5" />}
                </span>
                <span className="min-w-0 flex-1 truncate">{v.etiqueta ?? valor}</span>
                <span className="shrink-0 text-xs tabular-nums text-muted-foreground">
                  {v.cantidad}
                </span>
              </button>
            </li>
          )
        })}
      </ul>
      {valores.length > VISIBLES && (
        <button
          type="button"
          onClick={() => setTodos((t) => !t)}
          className="mt-1 px-2 text-sm text-primary hover:underline"
        >
          {todos ? "Ver menos" : `Ver ${valores.length - VISIBLES} más`}
        </button>
      )}
    </section>
  )
}
