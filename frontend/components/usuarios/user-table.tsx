"use client"

import { useState } from "react"
import Link from "next/link"
import {
  MoreHorizontal,
  Eye,
  Edit,
  Ban,
  CheckCircle,
  XCircle,
  AlertCircle,
  Loader2,
} from "lucide-react"
import { toast } from "sonner"

import { cn } from "@/lib/utils"
import { Button } from "@/components/ui/button"
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
} from "@/components/ui/alert-dialog"
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu"
import { apiPatch, mensajeDeError } from "@/lib/api"

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
  onEditar?: (carnet: string) => void
  onChange?: () => void
}

const statusConfig = {
  active: { icon: CheckCircle, label: "Activo", className: "text-primary bg-primary/10" },
  inactive: { icon: XCircle, label: "Inactivo", className: "text-muted-foreground bg-muted" },
  suspended: { icon: AlertCircle, label: "Con multas", className: "text-destructive bg-destructive/10" },
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

export function UserTable({ users, onEditar, onChange }: UserTableProps) {
  const [procesando, setProcesando] = useState<string | null>(null)
  const [aCambiar, setACambiar] = useState<User | null>(null)

  async function confirmarCambioEstado() {
    const user = aCambiar
    if (!user) return

    // "inactive" es el único estado que representa una cuenta desactivada;
    // "suspended" en la UI solo refleja que el lector tiene multas pendientes.
    const reactivar = user.status === "inactive"
    setACambiar(null)
    setProcesando(user.id)
    try {
      await apiPatch(`/users/${encodeURIComponent(user.id)}/status`, { activo: reactivar })
      toast.success(reactivar ? "Usuario reactivado" : "Usuario suspendido", {
        description: user.name,
      })
      onChange?.()
    } catch (error) {
      toast.error("No se pudo cambiar el estado", { description: mensajeDeError(error) })
    } finally {
      setProcesando(null)
    }
  }

  if (users.length === 0) {
    return (
      <div className="rounded-lg border border-dashed border-border bg-card py-16 text-center text-muted-foreground">
        <p className="text-lg font-medium">No hay usuarios que mostrar</p>
        <p className="text-sm">Registra el primer lector con “Nuevo Usuario”.</p>
      </div>
    )
  }

  return (
    <>
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
                const ocupado = procesando === user.id

                return (
                  <tr key={user.id} className="hover:bg-muted/30">
                    <td className="px-4 py-4">
                      <div className="flex items-center gap-3">
                        <div className="flex h-10 w-10 items-center justify-center rounded-full bg-primary/10 text-sm font-medium text-primary">
                          {user.name.split(" ").map((n) => n[0]).join("").slice(0, 2)}
                        </div>
                        <div>
                          <p className="font-medium text-foreground">{user.name}</p>
                          <p className="text-sm text-muted-foreground">{user.email}</p>
                        </div>
                      </div>
                    </td>
                    <td className="px-4 py-4">
                      <span
                        className={cn(
                          "inline-flex rounded-full px-2.5 py-0.5 text-xs font-medium",
                          userTypeColors[user.type]
                        )}
                      >
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
                      <p className="text-xs text-muted-foreground">
                        {user.totalLoans} total histórico
                      </p>
                    </td>
                    <td className="px-4 py-4">
                      <div
                        className={cn(
                          "inline-flex items-center gap-1.5 rounded-full px-2.5 py-1 text-xs font-medium",
                          status.className
                        )}
                      >
                        <StatusIcon className="h-3.5 w-3.5" />
                        {status.label}
                      </div>
                    </td>
                    <td className="px-4 py-4 text-right">
                      <DropdownMenu>
                        <DropdownMenuTrigger asChild>
                          <Button variant="ghost" size="icon" disabled={ocupado}>
                            {ocupado ? (
                              <Loader2 className="h-4 w-4 animate-spin" />
                            ) : (
                              <MoreHorizontal className="h-4 w-4" />
                            )}
                          </Button>
                        </DropdownMenuTrigger>
                        <DropdownMenuContent align="end">
                          <DropdownMenuItem asChild>
                            <Link href={`/usuarios/${encodeURIComponent(user.id)}`}>
                              <Eye className="mr-2 h-4 w-4" />
                              Ver Perfil
                            </Link>
                          </DropdownMenuItem>
                          <DropdownMenuItem onClick={() => onEditar?.(user.id)}>
                            <Edit className="mr-2 h-4 w-4" />
                            Editar
                          </DropdownMenuItem>
                          <DropdownMenuSeparator />
                          <DropdownMenuItem
                            className={user.status === "inactive" ? "" : "text-destructive"}
                            onClick={() => setACambiar(user)}
                          >
                            <Ban className="mr-2 h-4 w-4" />
                            {user.status === "inactive" ? "Reactivar" : "Suspender"}
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

      <AlertDialog open={aCambiar !== null} onOpenChange={(v) => !v && setACambiar(null)}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>
              {aCambiar?.status === "inactive" ? "¿Reactivar la cuenta?" : "¿Suspender la cuenta?"}
            </AlertDialogTitle>
            <AlertDialogDescription>
              {aCambiar?.status === "inactive" ? (
                <>
                  <strong>{aCambiar?.name}</strong> volverá a poder retirar material.
                </>
              ) : (
                <>
                  <strong>{aCambiar?.name}</strong> no podrá retirar material mientras esté
                  suspendido. El sistema rechaza la suspensión si tiene préstamos sin devolver.
                </>
              )}
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel>Cancelar</AlertDialogCancel>
            <AlertDialogAction onClick={confirmarCambioEstado}>Confirmar</AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </>
  )
}
