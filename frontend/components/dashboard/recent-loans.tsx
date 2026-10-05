import Link from "next/link"
import { Clock, AlertTriangle, CheckCircle, ArrowRight } from "lucide-react"

import { cn } from "@/lib/utils"

interface Loan {
  id: string
  book: string
  user: string
  dueDate: string
  status: "active" | "overdue" | "returned"
}

interface RecentLoansProps {
  loans?: Loan[]
  isLoading?: boolean
}

const statusConfig = {
  active: { icon: Clock, label: "Activo", className: "text-primary bg-primary/10" },
  overdue: { icon: AlertTriangle, label: "Vencido", className: "text-destructive bg-destructive/10" },
  returned: { icon: CheckCircle, label: "Devuelto", className: "text-muted-foreground bg-muted" },
}

export function RecentLoans({ loans = [], isLoading = false }: RecentLoansProps) {
  return (
    <div className="rounded-xl border border-border bg-card">
      <div className="flex items-center justify-between border-b border-border px-6 py-4">
        <div>
          <h3 className="font-semibold text-foreground">Préstamos Recientes</h3>
          <p className="text-sm text-muted-foreground">Últimas transacciones de circulación</p>
        </div>
        <Link
          href="/circulacion"
          className="flex items-center gap-1 text-sm font-medium text-primary hover:underline"
        >
          Ver todos
          <ArrowRight className="h-4 w-4" />
        </Link>
      </div>

      <div className="divide-y divide-border">
        {isLoading ? (
          <div className="py-12 text-center text-sm text-muted-foreground">
            Cargando transacciones...
          </div>
        ) : loans.length === 0 ? (
          <div className="bg-background/20 py-12 text-center text-sm text-muted-foreground">
            No se registran transacciones de circulación recientes.
          </div>
        ) : (
          loans.map((loan) => {
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
                  <div
                    className={cn(
                      "flex items-center gap-1.5 rounded-full px-2.5 py-1 text-xs font-medium",
                      status.className
                    )}
                  >
                    <StatusIcon className="h-3.5 w-3.5" />
                    {status.label}
                  </div>
                </div>
              </div>
            )
          })
        )}
      </div>
    </div>
  )
}
