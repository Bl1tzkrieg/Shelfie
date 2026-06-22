"use client"

import { useState, useEffect } from "react"
import { AppLayout } from "@/components/layout/app-layout"
import { Header } from "@/components/layout/header"
import { Button } from "@/components/ui/button"
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select"
import { 
  BarChart3, 
  TrendingUp, 
  Users, 
  BookOpen, 
  Download,
  Calendar
} from "lucide-react"

const reportTypes = [
  {
    id: "loans",
    title: "Reporte de Préstamos",
    description: "Estadísticas de préstamos por período",
    icon: BarChart3,
    lastGenerated: "Hace 2 días",
  },
  {
    id: "users",
    title: "Reporte de Usuarios",
    description: "Actividad y estadísticas de usuarios",
    icon: Users,
    lastGenerated: "Hace 1 semana",
  },
  {
    id: "catalog",
    title: "Reporte de Catálogo",
    description: "Inventario y estado de materiales",
    icon: BookOpen,
    lastGenerated: "Hace 3 días",
  },
  {
    id: "trends",
    title: "Tendencias de Uso",
    description: "Análisis de patrones de consulta",
    icon: TrendingUp,
    lastGenerated: "Hace 5 días",
  },
]

interface Stats {
  total_items: number
  total_users: number
  loans_this_month: number
  growth_percentage: string
}

export default function ReportesPage() {
  const [stats, setStats] = useState<Stats>({
    total_items: 0,
    total_users: 0,
    loans_this_month: 0,
    growth_percentage: "+0%"
  })

  // Carga dinámica de las estadísticas reales del backend
  useEffect(() => {
    async function fetchStats() {
      try {
        const response = await fetch(`${process.env.NEXT_PUBLIC_API_URL}/reports/stats`, {
          cache: "no-store"
        })
        if (response.ok) {
          const data = await response.json()
          setStats(data)
        }
      } catch (error) {
        console.error("Error al cargar estadísticas en reportes:", error)
      }
    }
    fetchStats()
  }, [])

  return (
    <AppLayout>
      <Header 
        title="Reportes" 
        description="Generación de informes y estadísticas"
      />
      
      <div className="p-6">
        {/* Quick Stats */}
        <div className="mb-8 grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
          <div className="rounded-lg border border-border bg-card p-4">
            <div className="flex items-center gap-3">
              <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-primary/10">
                <BookOpen className="h-5 w-5 text-primary" />
              </div>
              <div>
                <p className="text-2xl font-semibold text-foreground">
                  {stats.total_items.toLocaleString()}
                </p>
                <p className="text-sm text-muted-foreground">Títulos en catálogo</p>
              </div>
            </div>
          </div>
          <div className="rounded-lg border border-border bg-card p-4">
            <div className="flex items-center gap-3">
              <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-primary/10">
                <Users className="h-5 w-5 text-primary" />
              </div>
              <div>
                <p className="text-2xl font-semibold text-foreground">
                  {stats.total_users.toLocaleString()}
                </p>
                <p className="text-sm text-muted-foreground">Usuarios registrados</p>
              </div>
            </div>
          </div>
          <div className="rounded-lg border border-border bg-card p-4">
            <div className="flex items-center gap-3">
              <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-primary/10">
                <BarChart3 className="h-5 w-5 text-primary" />
              </div>
              <div>
                <p className="text-2xl font-semibold text-foreground">
                  {stats.loans_this_month.toLocaleString()}
                </p>
                <p className="text-sm text-muted-foreground">Préstamos este mes</p>
              </div>
            </div>
          </div>
          <div className="rounded-lg border border-border bg-card p-4">
            <div className="flex items-center gap-3">
              <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-primary/10">
                <TrendingUp className="h-5 w-5 text-primary" />
              </div>
              <div>
                <p className="text-2xl font-semibold text-foreground">{stats.growth_percentage}</p>
                <p className="text-sm text-muted-foreground">vs mes anterior</p>
              </div>
            </div>
          </div>
        </div>

        {/* Report Generator */}
        <div className="mb-8 rounded-lg border border-border bg-card p-6">
          <h3 className="text-lg font-semibold text-foreground">Generar Reporte Personalizado</h3>
          <p className="mt-1 text-sm text-muted-foreground">
            Selecciona los parámetros para generar un reporte a medida
          </p>
          
          <div className="mt-6 grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
            <div className="space-y-2">
              <label className="text-sm font-medium text-foreground">Tipo de Reporte</label>
              <Select>
                <SelectTrigger>
                  <SelectValue placeholder="Seleccionar tipo" />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="loans">Préstamos</SelectItem>
                  <SelectItem value="returns">Devoluciones</SelectItem>
                  <SelectItem value="users">Usuarios</SelectItem>
                  <SelectItem value="catalog">Catálogo</SelectItem>
                  <SelectItem value="overdue">Vencidos</SelectItem>
                </SelectContent>
              </Select>
            </div>
            <div className="space-y-2">
              <label className="text-sm font-medium text-foreground">Período</label>
              <Select>
                <SelectTrigger>
                  <SelectValue placeholder="Seleccionar período" />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="week">Última semana</SelectItem>
                  <SelectItem value="month">Último mes</SelectItem>
                  <SelectItem value="quarter">Último trimestre</SelectItem>
                  <SelectItem value="year">Último año</SelectItem>
                  <SelectItem value="custom">Personalizado</SelectItem>
                </SelectContent>
              </Select>
            </div>
            <div className="space-y-2">
              <label className="text-sm font-medium text-foreground">Formato</label>
              <Select>
                <SelectTrigger>
                  <SelectValue placeholder="Seleccionar formato" />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="pdf">PDF</SelectItem>
                  <SelectItem value="excel">Excel</SelectItem>
                  <SelectItem value="csv">CSV</SelectItem>
                </SelectContent>
              </Select>
            </div>
            <div className="flex items-end">
              <Button className="w-full">
                <Download className="mr-2 h-4 w-4" />
                Generar Reporte
              </Button>
            </div>
          </div>
        </div>

        {/* Report Types */}
        <div>
          <h3 className="mb-4 text-lg font-semibold text-foreground">Reportes Disponibles</h3>
          <div className="grid gap-4 sm:grid-cols-2">
            {reportTypes.map((report) => (
              <div
                key={report.id}
                className="flex items-start gap-4 rounded-lg border border-border bg-card p-4 transition-colors hover:bg-muted/50"
              >
                <div className="flex h-12 w-12 items-center justify-center rounded-lg bg-primary/10">
                  <report.icon className="h-6 w-6 text-primary" />
                </div>
                <div className="flex-1">
                  <h4 className="font-medium text-foreground">{report.title}</h4>
                  <p className="mt-0.5 text-sm text-muted-foreground">{report.description}</p>
                  <div className="mt-2 flex items-center gap-2 text-xs text-muted-foreground">
                    <Calendar className="h-3.5 w-3.5" />
                    Último: {report.lastGenerated}
                  </div>
                </div>
                <Button variant="outline" size="sm">
                  <Download className="mr-2 h-4 w-4" />
                  Descargar
                </Button>
              </div>
            ))}
          </div>
        </div>
      </div>
    </AppLayout>
  )
}