"use client"

import { ShieldOff } from "lucide-react"

import { useSesion } from "@/components/auth/sesion-provider"
import { NOMBRE_PERMISO, type Permiso } from "@/lib/types"
import { Sidebar } from "./sidebar"

interface AppLayoutProps {
  children: React.ReactNode
  /** Permiso necesario para ver la pantalla. Sin él, cualquier miembro del personal entra. */
  permiso?: Permiso
}

/** Marco de la intranet. La sesión ya la garantiza <SesionProvider>. */
export function AppLayout({ children, permiso }: AppLayoutProps) {
  const { tienePermiso } = useSesion()

  return (
    <div className="min-h-screen bg-background">
      <Sidebar />
      <main className="pl-64">
        {permiso && !tienePermiso(permiso) ? <SinPermiso permiso={permiso} /> : children}
      </main>
    </div>
  )
}

function SinPermiso({ permiso }: { permiso: Permiso }) {
  return (
    <div className="flex min-h-screen flex-col items-center justify-center gap-3 p-6 text-center">
      <ShieldOff className="h-10 w-10 text-muted-foreground" />
      <h1 className="text-lg font-semibold text-foreground">No tienes acceso a esta sección</h1>
      <p className="max-w-sm text-sm text-muted-foreground">
        Necesitas el permiso{" "}
        <span className="font-medium text-foreground">{NOMBRE_PERMISO[permiso]}</span>. Pídeselo a
        un administrador de la biblioteca.
      </p>
    </div>
  )
}
