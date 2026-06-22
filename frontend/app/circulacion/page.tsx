"use client"

import { useState, useEffect } from "react"
import { AppLayout } from "@/components/layout/app-layout"
import { Header } from "@/components/layout/header"
import { LoanFilters } from "@/components/circulacion/loan-filters"
import { LoanTable, Loan } from "@/components/circulacion/loan-table"
import { Button } from "@/components/ui/button"
import { Plus, Download } from "lucide-react"

export default function CirculacionPage() {
  const [activeTab, setActiveTab] = useState<"active" | "history">("active")
  const [loans, setLoans] = useState<Loan[]>([])
  const [isLoading, setIsLoading] = useState(true)

  // Función para obtener datos del backend en tiempo real
  useEffect(() => {
    async function fetchLoans() {
      try {
        // Añadimos cache: "no-store" para capturar cambios inmediatos de transacciones
        const response = await fetch(`${process.env.NEXT_PUBLIC_API_URL}/circulation/loans`, {
          cache: "no-store"
        })
        if (response.ok) {
          const data = await response.json()
          setLoans(data)
        }
      } catch (error) {
        console.error("Error al obtener los préstamos:", error)
      } finally {
        setIsLoading(false)
      }
    }
    fetchLoans()
  }, [])

  // Filtrado de estados basado en la respuesta de FastAPI
  const activeLoans = loans.filter(l => l.status === "active" || l.status === "overdue")
  const historyLoans = loans.filter(l => l.status === "returned")
  
  const currentLoans = activeTab === "active" ? activeLoans : historyLoans
  const overdueCount = activeLoans.filter(l => l.status === "overdue").length

  return (
    <AppLayout>
      <Header 
        title="Circulación" 
        description="Gestión de préstamos y devoluciones"
      />
      
      <div className="p-6">
        {/* Tarjetas de Métricas Sincronizadas */}
        <div className="grid grid-cols-1 md:grid-cols-3 gap-6 mb-6">
          <div className="bg-card border rounded-lg p-6">
            <h3 className="text-sm font-medium text-muted-foreground mb-2">Préstamos Activos</h3>
            <p className="text-3xl font-bold">{activeLoans.length}</p>
          </div>
          <div className="bg-card border rounded-lg p-6">
            <h3 className="text-sm font-medium text-muted-foreground mb-2">Vencidos</h3>
            <p className="text-3xl font-bold text-destructive">{overdueCount}</p>
          </div>
          <div className="bg-card border rounded-lg p-6">
            {/* Sincronizado con la UI de tu captura: Devueltos */}
            <h3 className="text-sm font-medium text-muted-foreground mb-2">Devueltos (este mes)</h3>
            <p className="text-3xl font-bold text-foreground">{historyLoans.length}</p>
          </div>
        </div>

        <div className="flex flex-col sm:flex-row justify-between items-start sm:items-center mb-6 gap-4">
          <LoanFilters 
            activeTab={activeTab} 
            onTabChange={setActiveTab} 
          />
          
          <div className="flex gap-2">
            <Button variant="outline">
              <Download className="mr-2 h-4 w-4" />
              Exportar
            </Button>
            <Button>
              <Plus className="mr-2 h-4 w-4" />
              Nuevo Préstamo
            </Button>
          </div>
        </div>

        {/* Tabla Dinámica conectado al Estado Global */}
        {isLoading ? (
          <div className="text-center py-10 bg-card border rounded-lg text-muted-foreground">
            Cargando información desde la base de datos...
          </div>
        ) : (
          <LoanTable loans={currentLoans} />
        )}
      </div>
    </AppLayout>
  )
}