"use client"

import { useCallback, useEffect, useMemo, useState } from "react"
import { Download, Loader2 } from "lucide-react"
import { toast } from "sonner"

import { AppLayout } from "@/components/layout/app-layout"
import { Header } from "@/components/layout/header"
import {
  LoanFilters,
  LoanFilterState,
  FILTROS_PRESTAMO_VACIOS,
} from "@/components/circulacion/loan-filters"
import { LoanTable } from "@/components/circulacion/loan-table"
import { NuevoPrestamoDialog } from "@/components/circulacion/nuevo-prestamo-dialog"
import { DevolucionDialog } from "@/components/circulacion/devolucion-dialog"
import { useSesion } from "@/components/auth/sesion-provider"
import { Button } from "@/components/ui/button"
import { apiDownload, apiGet, mensajeDeError } from "@/lib/api"
import type { ApiLoan, Configuracion } from "@/lib/types"

export default function CirculacionPage() {
  const { tienePermiso } = useSesion()
  const [activeTab, setActiveTab] = useState<"active" | "history">("active")
  const [loans, setLoans] = useState<ApiLoan[]>([])
  const [maxRenovaciones, setMaxRenovaciones] = useState(2)
  const [isLoading, setIsLoading] = useState(true)
  const [exportando, setExportando] = useState(false)
  const [searchQuery, setSearchQuery] = useState("")
  const [filtros, setFiltros] = useState<LoanFilterState>(FILTROS_PRESTAMO_VACIOS)

  const cargarPrestamos = useCallback(async () => {
    try {
      const data = await apiGet<ApiLoan[]>("/circulation/loans")
      setLoans(data)
    } catch (error) {
      toast.error("No se pudieron cargar los préstamos", {
        description: mensajeDeError(error),
      })
    } finally {
      setIsLoading(false)
    }
  }, [])

  useEffect(() => {
    cargarPrestamos()

    // El tope de renovaciones es configurable; la tabla lo necesita para
    // mostrar cuántas quedan en cada préstamo.
    apiGet<Configuracion>("/settings")
      .then((c) => setMaxRenovaciones(c.politicas_prestamo.renovaciones_permitidas))
      .catch(() => {
        /* se mantiene el valor por defecto */
      })
  }, [cargarPrestamos])

  async function exportar() {
    setExportando(true)
    try {
      await apiDownload("/circulation/loans/export", "prestamos.csv")
      toast.success("Exportación lista", { description: "Se descargó el CSV de préstamos." })
    } catch (error) {
      toast.error("No se pudo exportar", { description: mensajeDeError(error) })
    } finally {
      setExportando(false)
    }
  }

  const activeLoans = loans.filter((l) => l.status === "active" || l.status === "overdue")
  const historyLoans = loans.filter((l) => l.status === "returned")
  const overdueCount = activeLoans.filter((l) => l.status === "overdue").length

  const currentLoans = useMemo(() => {
    const base = activeTab === "active" ? activeLoans : historyLoans
    const query = searchQuery.trim().toLowerCase()

    return base.filter((loan) => {
      if (query) {
        const coincide = [loan.userName, loan.bookTitle, loan.bookCode, loan.userId].some(
          (campo) => campo?.toLowerCase().includes(query)
        )
        if (!coincide) return false
      }
      if (filtros.estado !== "all" && loan.status !== filtros.estado) return false
      if (filtros.tipoUsuario !== "all" && loan.userType !== filtros.tipoUsuario) return false
      return true
    })
  }, [activeTab, activeLoans, historyLoans, searchQuery, filtros])

  return (
    <AppLayout>
      <Header title="Circulación" description="Gestión de préstamos y devoluciones" />

      <div className="p-6">
        <div className="mb-6 grid grid-cols-1 gap-6 md:grid-cols-3">
          <div className="rounded-lg border bg-card p-6">
            <h3 className="mb-2 text-sm font-medium text-muted-foreground">Préstamos Activos</h3>
            <p className="text-3xl font-bold">{activeLoans.length}</p>
          </div>
          <div className="rounded-lg border bg-card p-6">
            <h3 className="mb-2 text-sm font-medium text-muted-foreground">Vencidos</h3>
            <p className="text-3xl font-bold text-destructive">{overdueCount}</p>
          </div>
          <div className="rounded-lg border bg-card p-6">
            <h3 className="mb-2 text-sm font-medium text-muted-foreground">Devueltos</h3>
            <p className="text-3xl font-bold text-foreground">{historyLoans.length}</p>
          </div>
        </div>

        <div className="mb-6 flex flex-col items-start justify-between gap-4 lg:flex-row">
          <div className="w-full lg:flex-1">
            <LoanFilters
              activeTab={activeTab}
              onTabChange={setActiveTab}
              searchQuery={searchQuery}
              onSearchChange={setSearchQuery}
              filtros={filtros}
              onFiltrosChange={setFiltros}
            />
          </div>

          <div className="flex shrink-0 gap-2">
            <Button variant="outline" onClick={exportar} disabled={exportando}>
              {exportando ? (
                <Loader2 className="mr-2 h-4 w-4 animate-spin" />
              ) : (
                <Download className="mr-2 h-4 w-4" />
              )}
              Exportar
            </Button>
            {tienePermiso("circulacion") && (
              <>
                <DevolucionDialog onSuccess={cargarPrestamos} />
                <NuevoPrestamoDialog onSuccess={cargarPrestamos} />
              </>
            )}
          </div>
        </div>

        {isLoading ? (
          <div className="rounded-lg border bg-card py-10 text-center text-muted-foreground">
            Cargando información desde la base de datos...
          </div>
        ) : (
          <LoanTable
            loans={currentLoans}
            maxRenovaciones={maxRenovaciones}
            onChange={cargarPrestamos}
          />
        )}
      </div>
    </AppLayout>
  )
}
