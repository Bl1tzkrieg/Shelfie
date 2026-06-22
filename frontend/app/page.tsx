"use client"

import { useState, useEffect } from "react"
import { AppLayout } from "@/components/layout/app-layout"
import { Header } from "@/components/layout/header"
import { StatCard } from "@/components/dashboard/stat-card"
import { RecentLoans } from "@/components/dashboard/recent-loans"
import { QuickActions } from "@/components/dashboard/quick-actions"
import { 
  BookOpen, 
  Users, 
  ArrowRightLeft, 
  AlertTriangle,
  Plus,
  UserPlus,
  BookPlus,
  FileText
} from "lucide-react"

const quickActions = [
  {
    title: "Nuevo Préstamo",
    description: "Registrar préstamo de material",
    href: "/circulacion/nuevo",
    icon: Plus,
    color: "primary" as const,
  },
  {
    title: "Registrar Usuario",
    description: "Agregar nuevo usuario al sistema",
    href: "/usuarios/nuevo",
    icon: UserPlus,
    color: "accent" as const,
  },
  {
    title: "Agregar Material",
    description: "Catalogar nuevo libro o recurso",
    href: "/catalogo/nuevo",
    icon: BookPlus,
    color: "secondary" as const,
  },
  {
    title: "Generar Reporte",
    description: "Crear reporte de actividad",
    href: "/reportes",
    icon: FileText,
    color: "secondary" as const,
  },
]

interface DashboardStats {
  totalItems: number
  totalUsers: number
  activeLoans: number
}

export default function DashboardPage() {
  const [stats, setStats] = useState<DashboardStats>({ totalItems: 0, totalUsers: 0, activeLoans: 0 })
  const [isLoading, setIsLoading] = useState(true)

useEffect(() => {
    async function fetchStats() {
      try {
        const response = await fetch(`${process.env.NEXT_PUBLIC_API_URL}/catalog/dashboard-stats`, {
          cache: "no-store"
        })
        
        if (response.ok) {
          const data = await response.json()
          setStats(data)
        }
      } catch (error) {
        console.error("Error al cargar estadísticas:", error)
      } finally {
        setIsLoading(false)
      }
    }
    fetchStats()
  }, [])

  return (
    <AppLayout>
      <Header 
        title="Dashboard" 
        description="Bienvenido al sistema de biblioteca Shelfie"
      />
      
      <div className="p-6">
        {/* Stats Grid */}
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
          <StatCard
            title="Total de Ítems"
            value={isLoading ? "..." : stats.totalItems.toLocaleString()}
            subtitle="En catálogo real"
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
            value={isLoading ? "..." : "0"}
            subtitle="Requieren atención"
            icon={AlertTriangle}
            className="border-destructive/30"
          />
        </div>

        {/* Main Content Grid */}
        <div className="mt-6 grid gap-6 lg:grid-cols-3">
          <div className="lg:col-span-2">
            <RecentLoans />
          </div>
          <div>
            <QuickActions actions={quickActions} />
          </div>
        </div>
      </div>
    </AppLayout>
  )
}