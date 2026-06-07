import { MoreHorizontal, Eye, Edit, Ban, CheckCircle, XCircle, AlertCircle } from "lucide-react"
import { cn } from "@/lib/utils"
import { Button } from "@/components/ui/button"
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu"
import Link from "next/link"

export interface User {
  id: string
  name: string
  email: string
  type: "student" | "teacher" | "staff"
  department: string
  status: "active" | "inactive" | "suspended"
  activeLoans: number
  totalLoans: number
  registeredDate: string
}

interface UserTableProps {
  users: User[]
}

const statusConfig = {
  active: {
    icon: CheckCircle,
    label: "Activo",
    className: "text-primary bg-primary/10",
  },
  inactive: {
    icon: XCircle,
    label: "Inactivo",
    className: "text-muted-foreground bg-muted",
  },
  suspended: {
    icon: AlertCircle,
    label: "Suspendido",
    className: "text-destructive bg-destructive/10",
  },
}

const userTypeLabels = {
  student: "Estudiante",
  teacher: "Docente",
  staff: "Personal",
}

const userTypeColors = {
  student: "bg-primary/10 text-primary",
  teacher: "bg-accent/20 text-accent-foreground",
  staff: "bg-secondary text-secondary-foreground",
}

export function UserTable({ users }: UserTableProps) {
  return (
    <div className="rounded-lg border border-border bg-card">
      <div className="overflow-x-auto">
        <table className="w-full">
          <thead>
            <tr className="border-b border-border bg-muted/50">
              <th className="px-4 py-3 text-left text-sm font-medium text-muted-foreground">Usuario</th>
              <th className="px-4 py-3 text-left text-sm font-medium text-muted-foreground">Tipo</th>
              <th className="px-4 py-3 text-left text-sm font-medium text-muted-foreground">Departamento</th>
              <th className="px-4 py-3 text-left text-sm font-medium text-muted-foreground">Préstamos</th>
              <th className="px-4 py-3 text-left text-sm font-medium text-muted-foreground">Estado</th>
              <th className="px-4 py-3 text-right text-sm font-medium text-muted-foreground">Acciones</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-border">
            {users.map((user) => {
              const status = statusConfig[user.status]
              const StatusIcon = status.icon

              return (
                <tr key={user.id} className="hover:bg-muted/30">
                  <td className="px-4 py-4">
                    <div className="flex items-center gap-3">
                      <div className="flex h-10 w-10 items-center justify-center rounded-full bg-primary/10 text-sm font-medium text-primary">
                        {user.name.split(" ").map(n => n[0]).join("").slice(0, 2)}
                      </div>
                      <div>
                        <p className="font-medium text-foreground">{user.name}</p>
                        <p className="text-sm text-muted-foreground">{user.email}</p>
                      </div>
                    </div>
                  </td>
                  <td className="px-4 py-4">
                    <span className={cn(
                      "inline-flex rounded-full px-2.5 py-0.5 text-xs font-medium",
                      userTypeColors[user.type]
                    )}>
                      {userTypeLabels[user.type]}
                    </span>
                  </td>
                  <td className="px-4 py-4">
                    <p className="text-sm text-foreground">{user.department}</p>
                    <p className="text-xs text-muted-foreground">ID: {user.id}</p>
                  </td>
                  <td className="px-4 py-4">
                    <p className="text-sm text-foreground">
                      <span className="font-medium">{user.activeLoans}</span> activos
                    </p>
                    <p className="text-xs text-muted-foreground">{user.totalLoans} total histórico</p>
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
                    <DropdownMenu>
                      <DropdownMenuTrigger asChild>
                        <Button variant="ghost" size="icon">
                          <MoreHorizontal className="h-4 w-4" />
                        </Button>
                      </DropdownMenuTrigger>
                      <DropdownMenuContent align="end">
                        <DropdownMenuItem asChild>
                          <Link href={`/usuarios/${user.id}`}>
                            <Eye className="mr-2 h-4 w-4" />
                            Ver Perfil
                          </Link>
                        </DropdownMenuItem>
                        <DropdownMenuItem>
                          <Edit className="mr-2 h-4 w-4" />
                          Editar
                        </DropdownMenuItem>
                        <DropdownMenuSeparator />
                        <DropdownMenuItem className="text-destructive">
                          <Ban className="mr-2 h-4 w-4" />
                          {user.status === "suspended" ? "Reactivar" : "Suspender"}
                        </DropdownMenuItem>
                      </DropdownMenuContent>
                    </DropdownMenu>
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
