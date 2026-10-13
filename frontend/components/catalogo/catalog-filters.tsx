"use client"

import { Search, Filter, Grid3X3, List, Loader2 } from "lucide-react"

import { Input } from "@/components/ui/input"
import { Button } from "@/components/ui/button"
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select"
import type { OrdenBusqueda } from "@/lib/types"
import { cn } from "@/lib/utils"

export const NOMBRE_ORDEN: Record<OrdenBusqueda, string> = {
  relevancia: "Más relevantes",
  titulo: "Título (A–Z)",
  ano_desc: "Más recientes",
  ano_asc: "Más antiguos",
}

interface CatalogFiltersProps {
  texto: string
  onTextoChange: (texto: string) => void
  buscando: boolean
  orden: OrdenBusqueda
  onOrdenChange: (orden: OrdenBusqueda) => void
  viewMode: "grid" | "list"
  onViewModeChange: (mode: "grid" | "list") => void
  /** Solo en pantallas angostas, donde las facetas van plegadas. */
  facetasAbiertas: boolean
  onFacetasToggle: () => void
  filtrosActivos: number
}

/** Barra de búsqueda del catálogo: texto, orden y vista. Las facetas van aparte. */
export function CatalogFilters({
  texto,
  onTextoChange,
  buscando,
  orden,
  onOrdenChange,
  viewMode,
  onViewModeChange,
  facetasAbiertas,
  onFacetasToggle,
  filtrosActivos,
}: CatalogFiltersProps) {
  return (
    <div className="flex flex-col gap-3 sm:flex-row">
      <div className="relative flex-1">
        {buscando ? (
          <Loader2 className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 animate-spin text-muted-foreground" />
        ) : (
          <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
        )}
        <Input
          type="search"
          aria-label="Buscar en el catálogo"
          placeholder="Título, autor, materia, ISBN o código de barras…"
          className="pl-10"
          value={texto}
          onChange={(e) => onTextoChange(e.target.value)}
        />
      </div>
      <div className="flex gap-2">
        <Button
          variant="outline"
          onClick={onFacetasToggle}
          className={cn("lg:hidden", facetasAbiertas && "bg-secondary")}
          aria-expanded={facetasAbiertas}
        >
          <Filter className="mr-2 h-4 w-4" />
          Filtros
          {filtrosActivos > 0 && (
            <span className="ml-2 rounded-full bg-primary px-1.5 text-xs text-primary-foreground">
              {filtrosActivos}
            </span>
          )}
        </Button>
        <Select value={orden} onValueChange={(v) => onOrdenChange(v as OrdenBusqueda)}>
          <SelectTrigger className="w-44" aria-label="Ordenar resultados">
            <SelectValue />
          </SelectTrigger>
          <SelectContent>
            {(Object.keys(NOMBRE_ORDEN) as OrdenBusqueda[]).map((o) => (
              <SelectItem key={o} value={o}>
                {NOMBRE_ORDEN[o]}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
        <div className="flex rounded-lg border border-border">
          <Button
            variant="ghost"
            size="icon"
            onClick={() => onViewModeChange("grid")}
            className={cn("rounded-r-none", viewMode === "grid" && "bg-secondary")}
            aria-label="Vista de cuadrícula"
            aria-pressed={viewMode === "grid"}
          >
            <Grid3X3 className="h-4 w-4" />
          </Button>
          <Button
            variant="ghost"
            size="icon"
            onClick={() => onViewModeChange("list")}
            className={cn("rounded-l-none", viewMode === "list" && "bg-secondary")}
            aria-label="Vista de lista"
            aria-pressed={viewMode === "list"}
          >
            <List className="h-4 w-4" />
          </Button>
        </div>
      </div>
    </div>
  )
}
