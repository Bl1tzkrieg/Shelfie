"use client"

import { useState } from "react"
import Link from "next/link"
import { ArrowRight, Plus, UserPlus, BookPlus, FileText } from "lucide-react"

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
  accent: "bg-accent/20 text-accent-foreground",
  secondary: "bg-secondary text-secondary-foreground",
}

/**
 * Las acciones rápidas abren los mismos diálogos que el resto de la app en vez
 * de navegar a rutas dedicadas, que era lo que antes producía 404.
 */
export function QuickActions({ onChange }: QuickActionsProps) {
  const [usuarioAbierto, setUsuarioAbierto] = useState(false)

  return (
    <div className="rounded-xl border border-border bg-card">
      <div className="border-b border-border px-6 py-4">
        <h3 className="font-semibold text-foreground">Acciones Rápidas</h3>
        <p className="text-sm text-muted-foreground">Operaciones frecuentes</p>
      </div>

      <div className="grid gap-2 p-4">
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

        <button
          onClick={() => setUsuarioAbierto(true)}
          className="group flex w-full items-center gap-4 rounded-lg p-3 text-left transition-colors hover:bg-muted"
        >
          <Icono color="accent">
            <UserPlus className="h-5 w-5" />
          </Icono>
          <Texto titulo="Registrar Usuario" descripcion="Agregar nuevo lector al sistema" />
          <Flecha />
        </button>

        <div className="[&_button]:w-full">
          <AgregarMaterialDialogWrapper onSuccess={onChange} />
        </div>

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

/**
 * AgregarMaterialDialog trae su propio botón; aquí se reutiliza tal cual para no
 * duplicar el formulario de catalogación.
 */
function AgregarMaterialDialogWrapper({ onSuccess }: { onSuccess?: () => void }) {
  return (
    <div className="flex items-center gap-4 rounded-lg p-3 transition-colors hover:bg-muted">
      <Icono color="secondary">
        <BookPlus className="h-5 w-5" />
      </Icono>
      <div className="flex-1">
        <p className="font-medium text-foreground">Agregar Material</p>
        <p className="text-sm text-muted-foreground">Catalogar nuevo libro o recurso</p>
      </div>
      <AgregarMaterialDialog onSuccess={onSuccess} />
    </div>
  )
}
