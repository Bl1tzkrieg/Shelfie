import { Clock, AlertTriangle, CheckCircle } from "lucide-react"
import { cn } from "@/lib/utils"

interface Loan {
  id: string
  book: string
  user: string
  dueDate: string
  status: "active" | "overdue" | "returned"
}

const recentLoans: Loan[] = [
  {
    id: "1",
    book: "Fisiología Vegetal - Taiz & Zeiger",
    user: "Carlos Mendoza",
    dueDate: "28 May 2026",
    status: "active",
  },
  {
    id: "2",
    book: "Introducción a la Agronomía",
    user: "Ana García",
    dueDate: "20 May 2026",
    status: "overdue",
  },
  {
    id: "3",
    book: "Manejo de Suelos Tropicales",
    user: "Pedro Ruiz",
    dueDate: "30 May 2026",
    status: "active",
  },
  {
    id: "4",
    book: "Fitopatología Básica",
    user: "Laura Sánchez",
    dueDate: "22 May 2026",
    status: "returned",
  },
  {
    id: "5",
    book: "Sistemas de Riego Agrícola",
    user: "Miguel Torres",
    dueDate: "25 May 2026",
    status: "active",
  },
]

const statusConfig = {
  active: {
    icon: Clock,
    label: "Activo",
    className: "text-primary bg-primary/10",
  },
  overdue: {
    icon: AlertTriangle,
    label: "Vencido",
    className: "text-destructive bg-destructive/10",
  },
  returned: {
    icon: CheckCircle,
    label: "Devuelto",
    className: "text-muted-foreground bg-muted",
  },
}

export function RecentLoans() {
  return (
    <div className="rounded-xl border border-border bg-card">
      <div className="border-b border-border px-6 py-4">
        <h3 className="font-semibold text-foreground">Préstamos Recientes</h3>
        <p className="text-sm text-muted-foreground">Últimas transacciones de circulación</p>
      </div>
      <div className="divide-y divide-border">
        {recentLoans.map((loan) => {
          const status = statusConfig[loan.status]
          const StatusIcon = status.icon
          
          return (
            <div key={loan.id} className="flex items-center justify-between px-6 py-4">
              <div className="min-w-0 flex-1">
                <p className="truncate font-medium text-foreground">{loan.book}</p>
                <p className="text-sm text-muted-foreground">{loan.user}</p>
              </div>
              <div className="ml-4 flex items-center gap-4">
                <div className="hidden text-right sm:block">
                  <p className="text-sm text-muted-foreground">Vence</p>
                  <p className="text-sm font-medium text-foreground">{loan.dueDate}</p>
                </div>
                <div className={cn(
                  "flex items-center gap-1.5 rounded-full px-2.5 py-1 text-xs font-medium",
                  status.className
                )}>
                  <StatusIcon className="h-3.5 w-3.5" />
                  {status.label}
                </div>
              </div>
            </div>
          )
        })}
      </div>
    </div>
  )
}
