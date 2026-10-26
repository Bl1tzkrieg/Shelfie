"use client"

import { useState } from "react"
import Link from "next/link"
import { ArrowRight, Plus, UserPlus, BookPlus, FileText } from "lucide-react"

import { useSesion } from "@/components/auth/sesion-provider"
import { cn } from "@/lib/utils"
import { NuevoPrestamoDialog } from "@/components/circulacion/nuevo-prestamo-dialog"
import { AgregarMaterialDialog } from "@/components/catalogo/agregar-material-dialog"
import { UsuarioDialog } from "@/components/usuarios/usuario-dialog"

interface QuickActionsProps {
  /** Se llama tras cualquier alta para refrescar las métricas del dashboard. */
  onChange?: () => void
}

const colorConfig = {
  primary: "bg-primary/10 text-primary",
  aviso: "bg-aviso/20 text-aviso-foreground",
  secondary: "bg-secondary text-secondary-foreground",
}

/**
 * Las acciones rápidas abren los mismos diálogos que el resto de la app en vez
 * de navegar a rutas dedicadas, que era lo que antes producía 404.
 */
export function QuickActions({ onChange }: QuickActionsProps) {
  const [usuarioAbierto, setUsuarioAbierto] = useState(false)
  const { tienePermiso } = useSesion()

  return (
    <div className="rounded-xl border border-border bg-card shadow-papel">
      <div className="border-b border-border px-6 py-4">
        <h3 className="font-semibold text-foreground">Acciones Rápidas</h3>
        <p className="text-sm text-muted-foreground">Operaciones frecuentes</p>
      </div>

      <div className="grid gap-2 p-4">
        {tienePermiso("circulacion") && (
        <NuevoPrestamoDialog
          onSuccess={onChange}
          trigger={
            <button className="group flex w-full items-center gap-4 rounded-lg p-3 text-left transition-colors hover:bg-muted">
              <Icono color="primary">
                <Plus className="h-5 w-5" />
              </Icono>
              <Texto titulo="Nuevo Préstamo" descripcion="Registrar préstamo de material" />
              <Flecha />
            </button>
          }
        />
        )}

        {tienePermiso("lectores") && (
        <button
          onClick={() => setUsuarioAbierto(true)}
          className="group flex w-full items-center gap-4 rounded-lg p-3 text-left transition-colors hover:bg-muted"
        >
          <Icono color="aviso">
            <UserPlus className="h-5 w-5" />
          </Icono>
          <Texto titulo="Registrar Usuario" descripcion="Agregar nuevo lector al sistema" />
          <Flecha />
        </button>
        )}

        {tienePermiso("catalogo") && (
          <AgregarMaterialDialog
            onSuccess={onChange}
            trigger={
              <button className="group flex w-full items-center gap-4 rounded-lg p-3 text-left transition-colors hover:bg-muted">
                <Icono color="secondary">
                  <BookPlus className="h-5 w-5" />
                </Icono>
                <Texto titulo="Agregar Material" descripcion="Catalogar nuevo libro o recurso" />
                <Flecha />
              </button>
            }
          />
        )}

        {tienePermiso("reportes") && (
        <Link
          href="/reportes"
          className="group flex items-center gap-4 rounded-lg p-3 transition-colors hover:bg-muted"
        >
          <Icono color="secondary">
            <FileText className="h-5 w-5" />
          </Icono>
          <Texto titulo="Generar Reporte" descripcion="Crear reporte de actividad" />
          <Flecha />
        </Link>
        )}
      </div>

      <UsuarioDialog
        open={usuarioAbierto}
        onOpenChange={setUsuarioAbierto}
        onSuccess={onChange}
      />
    </div>
  )
}

function Icono({
  color,
  children,
}: {
  color: keyof typeof colorConfig
  children: React.ReactNode
}) {
  return (
    <div
      className={cn(
        "flex h-10 w-10 shrink-0 items-center justify-center rounded-lg",
        colorConfig[color]
      )}
    >
      {children}
    </div>
  )
}

function Texto({ titulo, descripcion }: { titulo: string; descripcion: string }) {
  return (
    <div className="flex-1">
      <p className="font-medium text-foreground">{titulo}</p>
      <p className="text-sm text-muted-foreground">{descripcion}</p>
    </div>
  )
}

function Flecha() {
  return (
    <ArrowRight className="h-5 w-5 shrink-0 text-muted-foreground opacity-0 transition-opacity group-hover:opacity-100" />
  )
}
