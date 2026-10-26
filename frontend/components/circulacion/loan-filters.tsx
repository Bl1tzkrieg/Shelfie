"use client"

import { useState } from "react"
import { Search, Filter, X } from "lucide-react"

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

export interface LoanFilterState {
  estado: string
  tipoUsuario: string
}

export const FILTROS_PRESTAMO_VACIOS: LoanFilterState = {
  estado: "all",
  tipoUsuario: "all",
}

interface LoanFiltersProps {
  activeTab: "active" | "history"
  onTabChange: (tab: "active" | "history") => void
  searchQuery: string
  onSearchChange: (q: string) => void
  filtros: LoanFilterState
  onFiltrosChange: (f: LoanFilterState) => void
}

export function LoanFilters({
  activeTab,
  onTabChange,
  searchQuery,
  onSearchChange,
  filtros,
  onFiltrosChange,
}: LoanFiltersProps) {
  const [showFilters, setShowFilters] = useState(false)
  const activos = Object.values(filtros).filter((v) => v !== "all").length

  function set(campo: keyof LoanFilterState, valor: string) {
    onFiltrosChange({ ...filtros, [campo]: valor })
  }

  return (
    <div className="w-full space-y-4">
      <div className="flex gap-1 rounded-lg border border-border bg-muted/50 p-1">
        <button
          onClick={() => onTabChange("active")}
          className={cn(
            "flex-1 rounded-md px-4 py-2 text-sm font-medium transition-colors",
            activeTab === "active"
              ? "bg-card text-foreground shadow-sm"
              : "text-muted-foreground hover:text-foreground"
          )}
        >
          Préstamos Activos
        </button>
        <button
          onClick={() => onTabChange("history")}
          className={cn(
            "flex-1 rounded-md px-4 py-2 text-sm font-medium transition-colors",
            activeTab === "history"
              ? "bg-card text-foreground shadow-sm"
              : "text-muted-foreground hover:text-foreground"
          )}
        >
          Historial
        </button>
      </div>

      <div className="flex flex-col gap-3 sm:flex-row">
        <div className="relative flex-1">
          <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
          <Input
            type="search"
            placeholder="Buscar por lector, título o código..."
            className="pl-10"
            value={searchQuery}
            onChange={(e) => onSearchChange(e.target.value)}
          />
        </div>
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
      </div>

      {showFilters && (
        <div className="rounded-lg border border-border bg-card shadow-papel p-4">
          <div className="grid gap-4 sm:grid-cols-2">
            <div className="space-y-2">
              <label className="text-sm font-medium text-foreground">Estado</label>
              <Select value={filtros.estado} onValueChange={(v) => set("estado", v)}>
                <SelectTrigger>
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="all">Todos los estados</SelectItem>
                  <SelectItem value="active">Activo</SelectItem>
                  <SelectItem value="overdue">Vencido</SelectItem>
                  <SelectItem value="returned">Devuelto</SelectItem>
                </SelectContent>
              </Select>
            </div>
            <div className="space-y-2">
              <label className="text-sm font-medium text-foreground">Tipo de Usuario</label>
              <Select value={filtros.tipoUsuario} onValueChange={(v) => set("tipoUsuario", v)}>
                <SelectTrigger>
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="all">Todos los usuarios</SelectItem>
                  <SelectItem value="student">Estudiante</SelectItem>
                  <SelectItem value="teacher">Docente</SelectItem>
                  <SelectItem value="staff">Personal</SelectItem>
                </SelectContent>
              </Select>
            </div>
          </div>

          {activos > 0 && (
            <Button
              variant="ghost"
              size="sm"
              className="mt-4"
              onClick={() => onFiltrosChange(FILTROS_PRESTAMO_VACIOS)}
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
