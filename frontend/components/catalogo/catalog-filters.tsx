"use client"

import { useState } from "react"
import { Search, Filter, Grid3X3, List } from "lucide-react"
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

interface CatalogFiltersProps {
  viewMode: "grid" | "list"
  onViewModeChange: (mode: "grid" | "list") => void
}

export function CatalogFilters({ viewMode, onViewModeChange }: CatalogFiltersProps) {
  const [showFilters, setShowFilters] = useState(false)

  return (
    <div className="space-y-4">
      {/* Search Bar */}
      <div className="flex flex-col gap-3 sm:flex-row">
        <div className="relative flex-1">
          <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
          <Input
            type="search"
            placeholder="Buscar por título, autor, ISBN, materia..."
            className="pl-10"
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
          </Button>
          <div className="flex rounded-lg border border-border">
            <Button
              variant="ghost"
              size="icon"
              onClick={() => onViewModeChange("grid")}
              className={cn(
                "rounded-r-none",
                viewMode === "grid" && "bg-secondary"
              )}
            >
              <Grid3X3 className="h-4 w-4" />
            </Button>
            <Button
              variant="ghost"
              size="icon"
              onClick={() => onViewModeChange("list")}
              className={cn(
                "rounded-l-none",
                viewMode === "list" && "bg-secondary"
              )}
            >
              <List className="h-4 w-4" />
            </Button>
          </div>
        </div>
      </div>

      {/* Filters Panel */}
      {showFilters && (
        <div className="grid gap-4 rounded-lg border border-border bg-card p-4 sm:grid-cols-2 lg:grid-cols-4">
          <div className="space-y-2">
            <label className="text-sm font-medium text-foreground">Categoría</label>
            <Select>
              <SelectTrigger>
                <SelectValue placeholder="Todas las categorías" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="all">Todas las categorías</SelectItem>
                <SelectItem value="agronomia">Agronomía General</SelectItem>
                <SelectItem value="fitotecnia">Fitotecnia</SelectItem>
                <SelectItem value="zootecnia">Zootecnia</SelectItem>
                <SelectItem value="suelos">Ciencias del Suelo</SelectItem>
                <SelectItem value="botanica">Botánica</SelectItem>
                <SelectItem value="entomologia">Entomología</SelectItem>
              </SelectContent>
            </Select>
          </div>
          <div className="space-y-2">
            <label className="text-sm font-medium text-foreground">Tipo de Material</label>
            <Select>
              <SelectTrigger>
                <SelectValue placeholder="Todos los tipos" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="all">Todos los tipos</SelectItem>
                <SelectItem value="libro">Libro</SelectItem>
                <SelectItem value="revista">Revista</SelectItem>
                <SelectItem value="tesis">Tesis</SelectItem>
                <SelectItem value="articulo">Artículo</SelectItem>
                <SelectItem value="multimedia">Multimedia</SelectItem>
              </SelectContent>
            </Select>
          </div>
          <div className="space-y-2">
            <label className="text-sm font-medium text-foreground">Disponibilidad</label>
            <Select>
              <SelectTrigger>
                <SelectValue placeholder="Cualquier estado" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="all">Cualquier estado</SelectItem>
                <SelectItem value="available">Disponible</SelectItem>
                <SelectItem value="borrowed">En préstamo</SelectItem>
                <SelectItem value="reserved">Reservado</SelectItem>
              </SelectContent>
            </Select>
          </div>
          <div className="space-y-2">
            <label className="text-sm font-medium text-foreground">Año de Publicación</label>
            <Select>
              <SelectTrigger>
                <SelectValue placeholder="Cualquier año" />
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
      )}
    </div>
  )
}
