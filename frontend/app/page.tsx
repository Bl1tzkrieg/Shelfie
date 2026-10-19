"use client"

import { useCallback, useEffect, useState } from "react"
import { BookOpen, Users, ArrowRightLeft, AlertTriangle } from "lucide-react"
import { toast } from "sonner"

import { AppLayout } from "@/components/layout/app-layout"
import { Header } from "@/components/layout/header"
import { StatCard } from "@/components/dashboard/stat-card"
import { RecentLoans } from "@/components/dashboard/recent-loans"
import { QuickActions } from "@/components/dashboard/quick-actions"
import { apiGet, mensajeDeError } from "@/lib/api"
import type { ApiLoan, DashboardStats } from "@/lib/types"

export default function DashboardPage() {
  const [stats, setStats] = useState<DashboardStats>({
    totalItems: 0,
    totalUsers: 0,
    activeLoans: 0,
    overdueLoans: 0,
  })
  const [loans, setLoans] = useState<ApiLoan[]>([])
  const [isLoading, setIsLoading] = useState(true)

  const cargar = useCallback(async () => {
    try {
      const [s, l] = await Promise.all([
        apiGet<DashboardStats>("/catalog/dashboard-stats"),
        apiGet<ApiLoan[]>("/circulation/loans?limite=5"),
      ])
      setStats(s)
      setLoans(l)
    } catch (error) {
      toast.error("No se pudo cargar el dashboard", { description: mensajeDeError(error) })
    } finally {
      setIsLoading(false)
    }
  }, [])

  useEffect(() => {
    cargar()
  }, [cargar])

  // Los 5 movimientos más recientes, en la forma que espera RecentLoans.
  const recientes = loans.slice(0, 5).map((l) => ({
    id: l.id,
    book: l.bookTitle,
    user: l.userName,
    dueDate: l.dueDate,
    status: l.status,
  }))

  return (
    <AppLayout>
      <Header title="Dashboard" description="Bienvenido al sistema de biblioteca Shelfie" />

      <div className="p-6">
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
          <StatCard
            title="Total de Ítems"
            value={isLoading ? "..." : stats.totalItems.toLocaleString()}
            subtitle="Ejemplares en catálogo"
            icon={BookOpen}
          />
          <StatCard
            title="Usuarios Activos"
            value={isLoading ? "..." : stats.totalUsers.toLocaleString()}
            subtitle="Lectores registrados"
            icon={Users}
          />
          <StatCard
            title="Préstamos Activos"
            value={isLoading ? "..." : stats.activeLoans.toLocaleString()}
            subtitle="En circulación"
            icon={ArrowRightLeft}
          />
          <StatCard
            title="Préstamos Vencidos"
            value={isLoading ? "..." : stats.overdueLoans.toLocaleString()}
            subtitle="Requieren atención"
            icon={AlertTriangle}
            className="border-destructive/30"
          />
        </div>

        <div className="mt-6 grid gap-6 lg:grid-cols-3">
          <div className="lg:col-span-2">
            <RecentLoans loans={recientes} isLoading={isLoading} />
          </div>
          <div>
            <QuickActions onChange={cargar} />
          </div>
        </div>
      </div>
    </AppLayout>
  )
}
