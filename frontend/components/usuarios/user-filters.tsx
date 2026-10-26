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

export interface UserFilterState {
  tipo: string
  estado: string
  departamento: string
}

export const FILTROS_USUARIO_VACIOS: UserFilterState = {
  tipo: "all",
  estado: "all",
  departamento: "all",
}

interface UserFiltersProps {
  searchQuery: string
  onSearchChange: (q: string) => void
  filtros: UserFilterState
  onFiltrosChange: (f: UserFilterState) => void
  /** Departamentos presentes en el padrón real. */
  departamentos: string[]
}

export function UserFilters({
  searchQuery,
  onSearchChange,
  filtros,
  onFiltrosChange,
  departamentos,
}: UserFiltersProps) {
  const [showFilters, setShowFilters] = useState(false)
  const activos = Object.values(filtros).filter((v) => v !== "all").length

  function set(campo: keyof UserFilterState, valor: string) {
    onFiltrosChange({ ...filtros, [campo]: valor })
  }

  return (
    <div className="space-y-4">
      <div className="flex flex-col gap-3 sm:flex-row">
        <div className="relative flex-1">
          <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
          <Input
            type="search"
            placeholder="Buscar por nombre, carnet o email..."
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
          <div className="grid gap-4 sm:grid-cols-3">
            <div className="space-y-2">
              <label className="text-sm font-medium text-foreground">Tipo de Usuario</label>
              <Select value={filtros.tipo} onValueChange={(v) => set("tipo", v)}>
                <SelectTrigger>
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="all">Todos los tipos</SelectItem>
                  <SelectItem value="student">Estudiante</SelectItem>
                  <SelectItem value="teacher">Docente</SelectItem>
                  <SelectItem value="staff">Personal Administrativo</SelectItem>
                </SelectContent>
              </Select>
            </div>
            <div className="space-y-2">
              <label className="text-sm font-medium text-foreground">Estado</label>
              <Select value={filtros.estado} onValueChange={(v) => set("estado", v)}>
                <SelectTrigger>
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="all">Cualquier estado</SelectItem>
                  <SelectItem value="active">Activo</SelectItem>
                  <SelectItem value="inactive">Suspendido</SelectItem>
                  <SelectItem value="suspended">Bloqueado por deuda</SelectItem>
                </SelectContent>
              </Select>
            </div>
            <div className="space-y-2">
              <label className="text-sm font-medium text-foreground">Departamento</label>
              <Select value={filtros.departamento} onValueChange={(v) => set("departamento", v)}>
                <SelectTrigger>
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="all">Todos</SelectItem>
                  {departamentos.map((d) => (
                    <SelectItem key={d} value={d}>
                      {d}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
          </div>

          {activos > 0 && (
            <Button
              variant="ghost"
              size="sm"
              className="mt-4"
              onClick={() => onFiltrosChange(FILTROS_USUARIO_VACIOS)}
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
