"use client"

import { useCallback, useEffect, useState } from "react"
import { useParams, useRouter } from "next/navigation"
import {
  ArrowLeft,
  Mail,
  Building2,
  CalendarDays,
  AlertCircle,
  Edit,
  Clock,
  AlertTriangle,
  CheckCircle,
  KeyRound,
} from "lucide-react"
import { toast } from "sonner"

import { useSesion } from "@/components/auth/sesion-provider"
import { AppLayout } from "@/components/layout/app-layout"
import { Header } from "@/components/layout/header"
import { Button } from "@/components/ui/button"
import { CuentaLector } from "@/components/usuarios/cuenta-lector"
import { RestablecerClaveDialog } from "@/components/usuarios/restablecer-clave-dialog"
import { UsuarioDialog } from "@/components/usuarios/usuario-dialog"
import { apiGet, ApiError, mensajeDeError } from "@/lib/api"
import { cn } from "@/lib/utils"
import type { ApiUser, ApiLoan } from "@/lib/types"

const statusConfig = {
  active: { icon: Clock, label: "Activo", className: "text-primary bg-primary/10" },
  overdue: { icon: AlertTriangle, label: "Vencido", className: "text-destructive bg-destructive/10" },
  returned: { icon: CheckCircle, label: "Devuelto", className: "text-muted-foreground bg-muted" },
}

export default function PerfilUsuarioPage() {
  const params = useParams<{ id: string }>()
  const router = useRouter()
  const carnet = decodeURIComponent(params.id)

  const [usuario, setUsuario] = useState<ApiUser | null>(null)
  const [prestamos, setPrestamos] = useState<ApiLoan[]>([])
  const [isLoading, setIsLoading] = useState(true)
  const [noEncontrado, setNoEncontrado] = useState(false)
  const [editando, setEditando] = useState(false)
  const [restableciendo, setRestableciendo] = useState(false)
  const { usuario: yo, tienePermiso } = useSesion()

  const cargar = useCallback(async () => {
    try {
      const [u, p] = await Promise.all([
        apiGet<ApiUser>(`/users/${encodeURIComponent(carnet)}`),
        apiGet<ApiLoan[]>(`/users/${encodeURIComponent(carnet)}/loans`),
      ])
      setUsuario(u)
      setPrestamos(p)
    } catch (error) {
      if (error instanceof ApiError && error.status === 404) {
        setNoEncontrado(true)
      } else {
        toast.error("No se pudo cargar el perfil", { description: mensajeDeError(error) })
      }
    } finally {
      setIsLoading(false)
    }
  }, [carnet])

  useEffect(() => {
    cargar()
  }, [cargar])

  if (isLoading) {
    return (
      <AppLayout>
        <Header title="Perfil de usuario" />
        <div className="p-6">
          <div className="rounded-lg border bg-card py-16 text-center text-muted-foreground">
            Cargando perfil...
          </div>
        </div>
      </AppLayout>
    )
  }

  if (noEncontrado || !usuario) {
    return (
      <AppLayout>
        <Header title="Perfil de usuario" />
        <div className="p-6">
          <div className="rounded-lg border border-dashed bg-card py-16 text-center">
            <p className="text-lg font-medium text-foreground">Usuario no encontrado</p>
            <p className="mb-4 text-sm text-muted-foreground">
              No existe ningún lector con el carnet {carnet}.
            </p>
            <Button variant="outline" onClick={() => router.push("/usuarios")}>
              <ArrowLeft className="mr-2 h-4 w-4" />
              Volver al padrón
            </Button>
          </div>
        </div>
      </AppLayout>
    )
  }

  const activos = prestamos.filter((p) => p.status !== "returned")
  const nombreCompleto = `${usuario.nombre} ${usuario.apellido}`
  const iniciales = nombreCompleto.split(" ").map((n) => n[0]).join("").slice(0, 2)

  return (
    <AppLayout>
      <Header title="Perfil de usuario" description={nombreCompleto} />

      <div className="p-6">
        <Button variant="ghost" size="sm" className="mb-4" onClick={() => router.push("/usuarios")}>
          <ArrowLeft className="mr-2 h-4 w-4" />
          Volver al padrón
        </Button>

        <div className="mb-6 rounded-lg border border-border bg-card p-6">
          <div className="flex flex-col gap-4 sm:flex-row sm:items-start sm:justify-between">
            <div className="flex items-start gap-4">
              <div className="flex h-16 w-16 items-center justify-center rounded-full bg-primary/10 text-xl font-semibold text-primary">
                {iniciales}
              </div>
              <div>
                <h2 className="text-xl font-semibold text-foreground">{nombreCompleto}</h2>
                <p className="text-sm text-muted-foreground">
                  Carnet {usuario.nro_carnet}
                  {usuario.categoria && ` · ${usuario.categoria.descripcion}`}
                </p>
                <div className="mt-3 flex flex-col gap-1 text-sm text-muted-foreground">
                  <span className="flex items-center gap-2">
                    <Mail className="h-4 w-4" />
                    {usuario.email}
                  </span>
                  <span className="flex items-center gap-2">
                    <Building2 className="h-4 w-4" />
                    {usuario.departamento || "Sin departamento asignado"}
                  </span>
                  {usuario.fecha_creacion && (
                    <span className="flex items-center gap-2">
                      <CalendarDays className="h-4 w-4" />
                      Registrado el{" "}
                      {new Date(usuario.fecha_creacion).toLocaleDateString("es-VE")}
                    </span>
                  )}
                </div>
              </div>
            </div>

            <div className="flex items-center gap-2">
              <span
                className={cn(
                  "rounded-full px-3 py-1 text-xs font-medium",
                  usuario.activo
                    ? "bg-primary/10 text-primary"
                    : "bg-muted text-muted-foreground"
                )}
              >
                {usuario.activo ? "Cuenta activa" : "Cuenta suspendida"}
              </span>
              {tienePermiso("lectores") && (
                <Button variant="outline" size="sm" onClick={() => setEditando(true)}>
                  <Edit className="mr-2 h-4 w-4" />
                  Editar
                </Button>
              )}
              {tienePermiso("lectores") && usuario.nro_carnet !== yo?.nro_carnet &&
                (!usuario.es_personal || tienePermiso("superbibliotecario")) && (
                <Button variant="outline" size="sm" onClick={() => setRestableciendo(true)}>
                  <KeyRound className="mr-2 h-4 w-4" />
                  Restablecer contraseña
                </Button>
              )}
            </div>
          </div>

          {usuario.bloqueado_por_deuda && (
            <div className="mt-4 flex items-center gap-2 rounded-lg border border-destructive/30 bg-destructive/5 px-4 py-3 text-sm text-destructive">
              <AlertCircle className="h-4 w-4 shrink-0" />
              Debe Bs. {usuario.saldo_multas.toFixed(2)}, por encima del máximo permitido. No
              podrá retirar, renovar ni reservar material hasta pagar.
            </div>
          )}
        </div>

        <div className="mb-6 grid gap-4 sm:grid-cols-3">
          <div className="rounded-lg border border-border bg-card p-4">
            <p className="text-sm text-muted-foreground">Préstamos activos</p>
            <p className="mt-1 text-2xl font-semibold text-foreground">{activos.length}</p>
          </div>
          <div className="rounded-lg border border-border bg-card p-4">
            <p className="text-sm text-muted-foreground">Histórico total</p>
            <p className="mt-1 text-2xl font-semibold text-foreground">{prestamos.length}</p>
          </div>
          <div className="rounded-lg border border-border bg-card p-4">
            <p className="text-sm text-muted-foreground">Deuda</p>
            <p
              className={cn(
                "mt-1 text-2xl font-semibold",
                usuario.bloqueado_por_deuda ? "text-destructive" : "text-foreground"
              )}
            >
              Bs. {usuario.saldo_multas.toFixed(2)}
            </p>
          </div>
        </div>

        <CuentaLector carnet={usuario.nro_carnet} onChange={cargar} />

        <div className="rounded-lg border border-border bg-card">
          <div className="border-b border-border px-6 py-4">
            <h3 className="font-semibold text-foreground">Historial de préstamos</h3>
          </div>

          {prestamos.length === 0 ? (
            <div className="py-12 text-center text-sm text-muted-foreground">
              Este lector todavía no ha retirado material.
            </div>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full">
                <thead>
                  <tr className="border-b border-border bg-muted/50">
                    <th className="px-4 py-3 text-left text-sm font-medium text-muted-foreground">Material</th>
                    <th className="px-4 py-3 text-left text-sm font-medium text-muted-foreground">Préstamo</th>
                    <th className="px-4 py-3 text-left text-sm font-medium text-muted-foreground">Vencimiento</th>
                    <th className="px-4 py-3 text-left text-sm font-medium text-muted-foreground">Estado</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-border">
                  {prestamos.map((p) => {
                    const status = statusConfig[p.status]
                    const StatusIcon = status.icon
                    return (
                      <tr key={p.id} className="hover:bg-muted/30">
                        <td className="px-4 py-4">
                          <p className="font-medium text-foreground">{p.bookTitle}</p>
                          <p className="text-sm text-muted-foreground">{p.bookCode}</p>
                        </td>
                        <td className="px-4 py-4 text-sm text-foreground">{p.loanDate}</td>
                        <td className="px-4 py-4">
                          <p className="text-sm text-foreground">{p.dueDate}</p>
                          {p.returnDate && (
                            <p className="text-xs text-muted-foreground">
                              {p.lost ? "Perdido" : "Devuelto"}: {p.returnDate}
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
                      </tr>
                    )
                  })}
                </tbody>
              </table>
            </div>
          )}
        </div>
      </div>

      <RestablecerClaveDialog
        carnet={usuario.nro_carnet}
        nombre={`${usuario.nombre} ${usuario.apellido}`}
        open={restableciendo}
        onOpenChange={setRestableciendo}
      />
      <UsuarioDialog
        open={editando}
        onOpenChange={setEditando}
        usuario={usuario}
        onSuccess={cargar}
      />
    </AppLayout>
  )
}
