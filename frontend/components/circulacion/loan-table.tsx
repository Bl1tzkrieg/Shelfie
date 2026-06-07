import { Clock, AlertTriangle, CheckCircle, MoreHorizontal, RotateCcw, RefreshCw } from "lucide-react"
import { cn } from "@/lib/utils"
import { Button } from "@/components/ui/button"
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu"

export interface Loan {
  id: string
  bookTitle: string
  bookCode: string
  userName: string
  userId: string
  userType: "student" | "teacher" | "staff"
  loanDate: string
  dueDate: string
  returnDate?: string
  status: "active" | "overdue" | "returned"
  renewals: number
}

interface LoanTableProps {
  loans: Loan[]
}

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

const userTypeLabels = {
  student: "Estudiante",
  teacher: "Docente",
  staff: "Personal",
}

export function LoanTable({ loans }: LoanTableProps) {
  return (
    <div className="rounded-lg border border-border bg-card">
      <div className="overflow-x-auto">
        <table className="w-full">
          <thead>
            <tr className="border-b border-border bg-muted/50">
              <th className="px-4 py-3 text-left text-sm font-medium text-muted-foreground">Material</th>
              <th className="px-4 py-3 text-left text-sm font-medium text-muted-foreground">Usuario</th>
              <th className="px-4 py-3 text-left text-sm font-medium text-muted-foreground">Fecha Préstamo</th>
              <th className="px-4 py-3 text-left text-sm font-medium text-muted-foreground">Fecha Vencimiento</th>
              <th className="px-4 py-3 text-left text-sm font-medium text-muted-foreground">Estado</th>
              <th className="px-4 py-3 text-right text-sm font-medium text-muted-foreground">Acciones</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-border">
            {loans.map((loan) => {
              const status = statusConfig[loan.status]
              const StatusIcon = status.icon

              return (
                <tr key={loan.id} className="hover:bg-muted/30">
                  <td className="px-4 py-4">
                    <div>
                      <p className="font-medium text-foreground">{loan.bookTitle}</p>
                      <p className="text-sm text-muted-foreground">{loan.bookCode}</p>
                    </div>
                  </td>
                  <td className="px-4 py-4">
                    <div>
                      <p className="font-medium text-foreground">{loan.userName}</p>
                      <p className="text-sm text-muted-foreground">
                        {loan.userId} · {userTypeLabels[loan.userType]}
                      </p>
                    </div>
                  </td>
                  <td className="px-4 py-4 text-sm text-foreground">{loan.loanDate}</td>
                  <td className="px-4 py-4">
                    <p className="text-sm text-foreground">{loan.dueDate}</p>
                    {loan.returnDate && (
                      <p className="text-xs text-muted-foreground">Devuelto: {loan.returnDate}</p>
                    )}
                  </td>
                  <td className="px-4 py-4">
                    <div className={cn(
                      "inline-flex items-center gap-1.5 rounded-full px-2.5 py-1 text-xs font-medium",
                      status.className
                    )}>
                      <StatusIcon className="h-3.5 w-3.5" />
                      {status.label}
                    </div>
                  </td>
                  <td className="px-4 py-4 text-right">
                    {loan.status !== "returned" && (
                      <DropdownMenu>
                        <DropdownMenuTrigger asChild>
                          <Button variant="ghost" size="icon">
                            <MoreHorizontal className="h-4 w-4" />
                          </Button>
                        </DropdownMenuTrigger>
                        <DropdownMenuContent align="end">
                          <DropdownMenuItem>
                            <RotateCcw className="mr-2 h-4 w-4" />
                            Registrar Devolución
                          </DropdownMenuItem>
                          <DropdownMenuItem disabled={loan.renewals >= 2}>
                            <RefreshCw className="mr-2 h-4 w-4" />
                            Renovar ({2 - loan.renewals} restantes)
                          </DropdownMenuItem>
                        </DropdownMenuContent>
                      </DropdownMenu>
                    )}
                  </td>
                </tr>
              )
            })}
          </tbody>
        </table>
      </div>
    </div>
  )
}
