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

export default function DashboardPage() {
  return (
    <AppLayout>
      <Header 
        title="Dashboard" 
        description="Bienvenido al sistema de biblioteca BiblioAgro"
      />
      
      <div className="p-6">
        {/* Stats Grid */}
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
          <StatCard
            title="Total de Títulos"
            value="12,847"
            subtitle="En catálogo"
            icon={BookOpen}
            trend={{ value: 3.2, isPositive: true }}
          />
          <StatCard
            title="Usuarios Activos"
            value="2,456"
            subtitle="Estudiantes y docentes"
            icon={Users}
            trend={{ value: 5.1, isPositive: true }}
          />
          <StatCard
            title="Préstamos Activos"
            value="384"
            subtitle="En circulación"
            icon={ArrowRightLeft}
          />
          <StatCard
            title="Préstamos Vencidos"
            value="23"
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
