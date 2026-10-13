"use client"

import { useState } from "react"
import {
  Clock,
  AlertTriangle,
  CheckCircle,
  MoreHorizontal,
  RotateCcw,
  RefreshCw,
  Loader2,
  PackageX,
  PackageCheck,
} from "lucide-react"
import { toast } from "sonner"

import { cn } from "@/lib/utils"
import { useSesion } from "@/components/auth/sesion-provider"
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
import { apiPost, mensajeDeError } from "@/lib/api"
import type { ApiLoan, ResultadoDevolucion } from "@/lib/types"
import { avisarDevolucion } from "./aviso-devolucion"

export type Loan = ApiLoan

interface LoanTableProps {
  loans: Loan[]
  /** Tope por defecto si el préstamo no trae el de su regla de circulación. */
  maxRenovaciones?: number
  onChange?: () => void
}

const statusConfig = {
  active: { icon: Clock, label: "Activo", className: "text-primary bg-primary/10" },
  overdue: { icon: AlertTriangle, label: "Vencido", className: "text-destructive bg-destructive/10" },
  returned: { icon: CheckCircle, label: "Devuelto", className: "text-muted-foreground bg-muted" },
}

const estadoPerdido = {
  icon: PackageX,
  label: "Perdido",
  className: "text-destructive bg-destructive/10",
}

const userTypeLabels = {
  student: "Estudiante",
  teacher: "Docente",
  staff: "Personal",
}

export function LoanTable({ loans, maxRenovaciones = 2, onChange }: LoanTableProps) {
  const circula = useSesion().tienePermiso("circulacion")
  const [procesando, setProcesando] = useState<string | null>(null)
  const [aDevolver, setADevolver] = useState<Loan | null>(null)
  const [aPerder, setAPerder] = useState<Loan | null>(null)

  async function confirmarPerdida() {
    const loan = aPerder
    if (!loan) return
    setAPerder(null)
    setProcesando(loan.id)
    try {
      const res = await apiPost<{ cargo_reposicion: number }>(
        `/circulation/loans/${encodeURIComponent(loan.id)}/lost`
      )
      toast.success("Ejemplar declarado perdido", {
        description: `Se cargaron Bs. ${res.cargo_reposicion.toFixed(2)} a la cuenta de ${loan.userName}.`,
      })
      onChange?.()
    } catch (error) {
      toast.error("No se pudo declarar la pérdida", { description: mensajeDeError(error) })
    } finally {
      setProcesando(null)
    }
  }

  async function confirmarDevolucion() {
    const loan = aDevolver
    if (!loan) return

    setADevolver(null)
    setProcesando(loan.id)
    try {
      const res = await apiPost<ResultadoDevolucion>("/circulation/checkin", {
        codigo_barras: loan.bookCode,
      })
      avisarDevolucion(res)
      onChange?.()
    } catch (error) {
      toast.error("No se pudo registrar la devolución", {
        description: mensajeDeError(error),
      })
    } finally {
      setProcesando(null)
    }
  }

  async function renovar(loan: Loan) {
    setProcesando(loan.id)
    try {
      const res = await apiPost<{
        nueva_fecha_vencimiento: string
        renovaciones_restantes: number
        multa_aplicada: number
      }>("/circulation/renew", { prestamo_id: Number(loan.id) })

      const nueva = new Date(res.nueva_fecha_vencimiento).toLocaleDateString("es-VE")
      const mora =
        res.multa_aplicada > 0
          ? ` Se cobró el atraso acumulado: Bs. ${res.multa_aplicada.toFixed(2)}.`
          : ""
      toast.success("Préstamo renovado", {
        description: `Nuevo vencimiento: ${nueva}. Quedan ${res.renovaciones_restantes} renovación(es).${mora}`,
      })
      onChange?.()
    } catch (error) {
      toast.error("No se pudo renovar", { description: mensajeDeError(error) })
    } finally {
      setProcesando(null)
    }
  }

  if (loans.length === 0) {
    return (
      <div className="rounded-lg border border-dashed border-border bg-card py-16 text-center text-muted-foreground">
        <p className="text-lg font-medium">No hay préstamos en esta vista</p>
        <p className="text-sm">Registra uno nuevo para verlo aquí.</p>
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
                const status = loan.lost ? estadoPerdido : statusConfig[loan.status]
                const StatusIcon = status.icon
                const restantes = Math.max(
                  0,
                  (loan.renewalsAllowed ?? maxRenovaciones) - loan.renewals
                )
                const ocupado = procesando === loan.id

                return (
                  <tr key={loan.id} className="hover:bg-muted/30">
                    <td className="px-4 py-4">
                      <p className="font-medium text-foreground">{loan.bookTitle}</p>
                      <p className="text-sm text-muted-foreground">{loan.bookCode}</p>
                    </td>
                    <td className="px-4 py-4">
                      <p className="font-medium text-foreground">{loan.userName}</p>
                      <p className="text-sm text-muted-foreground">
                        {loan.userId} · {userTypeLabels[loan.userType] ?? "Lector"}
                      </p>
                    </td>
                    <td className="px-4 py-4 text-sm text-foreground">{loan.loanDate}</td>
                    <td className="px-4 py-4">
                      <p className="text-sm text-foreground">{loan.dueDate}</p>
                      {loan.returnDate && (
                        <p className="text-xs text-muted-foreground">
                          {loan.lost ? "Perdido" : "Devuelto"}: {loan.returnDate}
                        </p>
                      )}
                      {loan.renewals > 0 && !loan.returnDate && (
                        <p className="text-xs text-muted-foreground">
                          {loan.renewals} renovación(es)
                        </p>
                      )}
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
                      {circula && loan.recoverable && (
                        <Button
                          variant="outline"
                          size="sm"
                          disabled={ocupado}
                          onClick={() => setADevolver(loan)}
                        >
                          {ocupado ? (
                            <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                          ) : (
                            <PackageCheck className="mr-2 h-4 w-4" />
                          )}
                          Apareció
                        </Button>
                      )}
                      {circula && loan.status !== "returned" && (
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
                            <DropdownMenuItem onClick={() => setADevolver(loan)}>
                              <RotateCcw className="mr-2 h-4 w-4" />
                              Registrar Devolución
                            </DropdownMenuItem>
                            <DropdownMenuItem
                              disabled={restantes === 0}
                              onClick={() => renovar(loan)}
                            >
                              <RefreshCw className="mr-2 h-4 w-4" />
                              Renovar ({restantes} restantes)
                            </DropdownMenuItem>
                            <DropdownMenuSeparator />
                            <DropdownMenuItem
                              className="text-destructive"
                              onClick={() => setAPerder(loan)}
                            >
                              <PackageX className="mr-2 h-4 w-4" />
                              Declarar perdido
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

      <AlertDialog open={aDevolver !== null} onOpenChange={(v) => !v && setADevolver(null)}>
        <AlertDialogContent>
          {aDevolver?.recoverable ? (
            <AlertDialogHeader>
              <AlertDialogTitle>¿Apareció el ejemplar?</AlertDialogTitle>
              <AlertDialogDescription>
                <strong>{aDevolver.bookTitle}</strong> ({aDevolver.bookCode}) volverá al
                inventario, o se apartará si alguien lo tiene reservado. A {aDevolver.userName} se
                le acreditará lo que se le cargó por reposición; si ya lo había pagado, le quedará
                como saldo a favor.
              </AlertDialogDescription>
            </AlertDialogHeader>
          ) : (
            <AlertDialogHeader>
              <AlertDialogTitle>¿Registrar la devolución?</AlertDialogTitle>
              <AlertDialogDescription>
                Se devolverá <strong>{aDevolver?.bookTitle}</strong> ({aDevolver?.bookCode}),
                prestado a {aDevolver?.userName}.
                {aDevolver?.status === "overdue" && (
                  <>
                    {" "}
                    El préstamo está vencido, así que el sistema calculará y aplicará la multa
                    correspondiente a la cuenta del lector.
                  </>
                )}
              </AlertDialogDescription>
            </AlertDialogHeader>
          )}
          <AlertDialogFooter>
            <AlertDialogCancel>Cancelar</AlertDialogCancel>
            <AlertDialogAction onClick={confirmarDevolucion}>
              {aDevolver?.recoverable ? "Reincorporar ejemplar" : "Confirmar devolución"}
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>

      <AlertDialog open={aPerder !== null} onOpenChange={(v) => !v && setAPerder(null)}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>¿Declarar el ejemplar como perdido?</AlertDialogTitle>
            <AlertDialogDescription>
              <strong>{aPerder?.bookTitle}</strong> ({aPerder?.bookCode}) quedará como perdido y
              el préstamo de {aPerder?.userName} se cerrará. Se cargará a su cuenta el precio de
              reposición del ejemplar (o el valor por defecto de Configuración). Si luego
              aparece, se reintegra desde el historial con «Apareció».
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel>Cancelar</AlertDialogCancel>
            <AlertDialogAction
              onClick={confirmarPerdida}
              className="bg-destructive text-destructive-foreground hover:bg-destructive/90"
            >
              Declarar perdido
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </>
  )
}
