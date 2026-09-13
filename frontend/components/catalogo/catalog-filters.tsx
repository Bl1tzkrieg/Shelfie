"use client"

import { useState } from "react"
import { Search, Filter, Grid3X3, List, X } from "lucide-react"

import { Input } from "@/components/ui/input"
import { Button } from "@/components/ui/button"
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select"
import { cn } from "@/lib/utils"

export interface CatalogFilterState {
  categoria: string
  tipo: string
  disponibilidad: string
  ano: string
}

export const FILTROS_VACIOS: CatalogFilterState = {
  categoria: "all",
  tipo: "all",
  disponibilidad: "all",
  ano: "all",
}

export const RANGOS_ANO: Record<string, [number, number]> = {
  "2024-2026": [2024, 2026],
  "2020-2023": [2020, 2023],
  "2015-2019": [2015, 2019],
  "2010-2014": [2010, 2014],
  older: [0, 2009],
}

interface CatalogFiltersProps {
  viewMode: "grid" | "list"
  onViewModeChange: (mode: "grid" | "list") => void
  searchQuery: string
  onSearchChange: (query: string) => void
  filtros: CatalogFilterState
  onFiltrosChange: (filtros: CatalogFilterState) => void
  /** Opciones derivadas del catálogo real, no hardcodeadas. */
  categorias: string[]
  tipos: string[]
}

export function CatalogFilters({
  viewMode,
  onViewModeChange,
  searchQuery,
  onSearchChange,
  filtros,
  onFiltrosChange,
  categorias,
  tipos,
}: CatalogFiltersProps) {
  const [showFilters, setShowFilters] = useState(false)

  const activos = Object.values(filtros).filter((v) => v !== "all").length

  function set(campo: keyof CatalogFilterState, valor: string) {
    onFiltrosChange({ ...filtros, [campo]: valor })
  }

  return (
    <div className="space-y-4">
      <div className="flex flex-col gap-3 sm:flex-row">
        <div className="relative flex-1">
          <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
          <Input
            type="search"
            placeholder="Buscar por título, autor, ISBN, materia..."
            className="pl-10"
            value={searchQuery}
            onChange={(e) => onSearchChange(e.target.value)}
          />
        </div>
        <div className="flex gap-2">
          <Button
            variant="outline"
            onClick={() => setShowFilters(!showFilters)}
            className={cn(showFilters && "bg-secondary")}
          >
            <Filter className="mr-2 h-4 w-4" />
            Filtros
            {activos > 0 && (
              <span className="ml-2 rounded-full bg-primary px-1.5 text-xs text-primary-foreground">
                {activos}
              </span>
            )}
          </Button>
          <div className="flex rounded-lg border border-border">
            <Button
              variant="ghost"
              size="icon"
              onClick={() => onViewModeChange("grid")}
              className={cn("rounded-r-none", viewMode === "grid" && "bg-secondary")}
              aria-label="Vista de cuadrícula"
            >
              <Grid3X3 className="h-4 w-4" />
            </Button>
            <Button
              variant="ghost"
              size="icon"
              onClick={() => onViewModeChange("list")}
              className={cn("rounded-l-none", viewMode === "list" && "bg-secondary")}
              aria-label="Vista de lista"
            >
              <List className="h-4 w-4" />
            </Button>
          </div>
        </div>
      </div>

      {showFilters && (
        <div className="rounded-lg border border-border bg-card p-4">
          <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
            <div className="space-y-2">
              <label className="text-sm font-medium text-foreground">Materia</label>
              <Select value={filtros.categoria} onValueChange={(v) => set("categoria", v)}>
                <SelectTrigger>
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="all">Todas las materias</SelectItem>
                  {categorias.map((c) => (
                    <SelectItem key={c} value={c}>
                      {c}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>

            <div className="space-y-2">
              <label className="text-sm font-medium text-foreground">Tipo de Material</label>
              <Select value={filtros.tipo} onValueChange={(v) => set("tipo", v)}>
                <SelectTrigger>
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="all">Todos los tipos</SelectItem>
                  {tipos.map((t) => (
                    <SelectItem key={t} value={t}>
                      {t}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>

            <div className="space-y-2">
              <label className="text-sm font-medium text-foreground">Disponibilidad</label>
              <Select
                value={filtros.disponibilidad}
                onValueChange={(v) => set("disponibilidad", v)}
              >
                <SelectTrigger>
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="all">Cualquier estado</SelectItem>
                  <SelectItem value="available">Con ejemplares libres</SelectItem>
                  <SelectItem value="borrowed">Todos prestados</SelectItem>
                </SelectContent>
              </Select>
            </div>

            <div className="space-y-2">
              <label className="text-sm font-medium text-foreground">Año de Publicación</label>
              <Select value={filtros.ano} onValueChange={(v) => set("ano", v)}>
                <SelectTrigger>
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="all">Cualquier año</SelectItem>
                  <SelectItem value="2024-2026">2024 - 2026</SelectItem>
                  <SelectItem value="2020-2023">2020 - 2023</SelectItem>
                  <SelectItem value="2015-2019">2015 - 2019</SelectItem>
                  <SelectItem value="2010-2014">2010 - 2014</SelectItem>
                  <SelectItem value="older">Anterior a 2010</SelectItem>
                </SelectContent>
              </Select>
            </div>
          </div>

          {activos > 0 && (
            <Button
              variant="ghost"
              size="sm"
              className="mt-4"
              onClick={() => onFiltrosChange(FILTROS_VACIOS)}
            >
              <X className="mr-2 h-4 w-4" />
              Limpiar filtros
            </Button>
          )}
        </div>
      )}
    </div>
  )
}
