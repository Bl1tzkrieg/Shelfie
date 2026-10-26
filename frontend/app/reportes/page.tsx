"use client"

import { useEffect, useState } from "react"
import { BarChart3, TrendingUp, Users, BookOpen, Download, Loader2, FileText } from "lucide-react"
import { toast } from "sonner"

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
import { apiDownload, apiGet, mensajeDeError } from "@/lib/api"
import type { ReporteDisponible } from "@/lib/types"

interface Stats {
  total_items: number
  total_users: number
  loans_this_month: number
  growth_percentage: string
}

const iconosPorReporte: Record<string, typeof BarChart3> = {
  loans: BarChart3,
  returns: TrendingUp,
  overdue: TrendingUp,
  users: Users,
  catalog: BookOpen,
}

export default function ReportesPage() {
  const [stats, setStats] = useState<Stats>({
    total_items: 0,
    total_users: 0,
    loans_this_month: 0,
    growth_percentage: "0%",
  })
  const [disponibles, setDisponibles] = useState<ReporteDisponible[]>([])
  const [tipo, setTipo] = useState("loans")
  const [periodo, setPeriodo] = useState("month")
  const [formato, setFormato] = useState("csv")
  const [generando, setGenerando] = useState(false)
  const [descargando, setDescargando] = useState<string | null>(null)

  useEffect(() => {
    apiGet<Stats>("/reports/stats")
      .then(setStats)
      .catch((e) =>
        toast.error("No se pudieron cargar las estadísticas", { description: mensajeDeError(e) })
      )

    apiGet<ReporteDisponible[]>("/reports/available")
      .then(setDisponibles)
      .catch(() => setDisponibles([]))
  }, [])

  async function generar() {
    setGenerando(true)
    try {
      if (formato === "json") {
        const data = await apiGet<{ filas: unknown[] }>(
          `/reports/generate?tipo=${tipo}&periodo=${periodo}&formato=json`
        )
        toast.success("Reporte generado", {
          description: `${data.filas.length} fila(s). Cambia el formato a CSV para descargarlo.`,
        })
        return
      }

      await apiDownload(
        `/reports/generate?tipo=${tipo}&periodo=${periodo}&formato=csv`,
        `${tipo}-${periodo}.csv`
      )
      toast.success("Reporte descargado")
    } catch (error) {
      toast.error("No se pudo generar el reporte", { description: mensajeDeError(error) })
    } finally {
      setGenerando(false)
    }
  }

  async function descargarRapido(reporteId: string) {
    setDescargando(reporteId)
    try {
      await apiDownload(
        `/reports/generate?tipo=${reporteId}&periodo=all&formato=csv`,
        `${reporteId}.csv`
      )
      toast.success("Reporte descargado")
    } catch (error) {
      toast.error("No se pudo descargar", { description: mensajeDeError(error) })
    } finally {
      setDescargando(null)
    }
  }

  const tarjetas = [
    { icon: BookOpen, valor: stats.total_items.toLocaleString(), etiqueta: "Ejemplares en catálogo" },
    { icon: Users, valor: stats.total_users.toLocaleString(), etiqueta: "Usuarios registrados" },
    { icon: BarChart3, valor: stats.loans_this_month.toLocaleString(), etiqueta: "Préstamos este mes" },
    { icon: TrendingUp, valor: stats.growth_percentage, etiqueta: "vs mes anterior" },
  ]

  return (
    <AppLayout permiso="reportes">
      <Header title="Reportes" description="Generación de informes y estadísticas" />

      <div className="p-6">
        <div className="mb-8 grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
          {tarjetas.map((t) => (
            <div key={t.etiqueta} className="rounded-lg border border-border bg-card shadow-papel p-4">
              <div className="flex items-center gap-3">
                <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-primary/10">
                  <t.icon className="h-5 w-5 text-primary" />
                </div>
                <div>
                  <p className="text-2xl font-semibold text-foreground">{t.valor}</p>
                  <p className="text-sm text-muted-foreground">{t.etiqueta}</p>
                </div>
              </div>
            </div>
          ))}
        </div>

        <div className="mb-8 rounded-lg border border-border bg-card shadow-papel p-6">
          <h3 className="text-lg font-semibold text-foreground">Generar Reporte Personalizado</h3>
          <p className="mt-1 text-sm text-muted-foreground">
            Selecciona los parámetros para generar un reporte a medida
          </p>

          <div className="mt-6 grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
            <div className="space-y-2">
              <label className="text-sm font-medium text-foreground">Tipo de Reporte</label>
              <Select value={tipo} onValueChange={setTipo}>
                <SelectTrigger>
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="loans">Préstamos</SelectItem>
                  <SelectItem value="returns">Devoluciones</SelectItem>
                  <SelectItem value="overdue">Vencidos</SelectItem>
                  <SelectItem value="users">Usuarios</SelectItem>
                  <SelectItem value="catalog">Catálogo</SelectItem>
                </SelectContent>
              </Select>
            </div>

            <div className="space-y-2">
              <label className="text-sm font-medium text-foreground">Período</label>
              <Select value={periodo} onValueChange={setPeriodo}>
                <SelectTrigger>
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="week">Última semana</SelectItem>
                  <SelectItem value="month">Último mes</SelectItem>
                  <SelectItem value="quarter">Último trimestre</SelectItem>
                  <SelectItem value="year">Último año</SelectItem>
                  <SelectItem value="all">Todo el histórico</SelectItem>
                </SelectContent>
              </Select>
            </div>

            <div className="space-y-2">
              <label className="text-sm font-medium text-foreground">Formato</label>
              <Select value={formato} onValueChange={setFormato}>
                <SelectTrigger>
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="csv">CSV (descarga)</SelectItem>
                  <SelectItem value="json">JSON (vista previa)</SelectItem>
                </SelectContent>
              </Select>
            </div>

            <div className="flex items-end">
              <Button className="w-full" onClick={generar} disabled={generando}>
                {generando ? (
                  <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                ) : (
                  <Download className="mr-2 h-4 w-4" />
                )}
                Generar Reporte
              </Button>
            </div>
          </div>
        </div>

        <div>
          <h3 className="mb-4 text-lg font-semibold text-foreground">Reportes Disponibles</h3>

          {disponibles.length === 0 ? (
            <div className="rounded-lg border border-dashed bg-card py-12 text-center text-muted-foreground">
              No se pudo consultar la lista de reportes.
            </div>
          ) : (
            <div className="grid gap-4 sm:grid-cols-2">
              {disponibles.map((reporte) => {
                const Icono = iconosPorReporte[reporte.id] || FileText
                const ocupado = descargando === reporte.id

                return (
                  <div
                    key={reporte.id}
                    className="flex items-start gap-4 rounded-lg border border-border bg-card shadow-papel p-4 transition-colors hover:bg-muted/50"
                  >
                    <div className="flex h-12 w-12 shrink-0 items-center justify-center rounded-lg bg-primary/10">
                      <Icono className="h-6 w-6 text-primary" />
                    </div>
                    <div className="flex-1">
                      <h4 className="font-medium text-foreground">{reporte.title}</h4>
                      <p className="mt-0.5 text-sm text-muted-foreground">
                        {reporte.description}
                      </p>
                      <p className="mt-2 text-xs text-muted-foreground">
                        {reporte.rows} fila(s) disponibles
                      </p>
                    </div>
                    <Button
                      variant="outline"
                      size="sm"
                      onClick={() => descargarRapido(reporte.id)}
                      disabled={ocupado}
                    >
                      {ocupado ? (
                        <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                      ) : (
                        <Download className="mr-2 h-4 w-4" />
                      )}
                      Descargar
                    </Button>
                  </div>
                )
              })}
            </div>
          )}
        </div>
      </div>
    </AppLayout>
  )
}
