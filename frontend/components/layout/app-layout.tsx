"use client"

import { useState } from "react"
import { BookMarked, Menu, ShieldOff } from "lucide-react"

import { useSesion } from "@/components/auth/sesion-provider"
import { NOMBRE_PERMISO, type Permiso } from "@/lib/types"
import { Button } from "@/components/ui/button"
import { Sheet, SheetContent, SheetTitle } from "@/components/ui/sheet"
import { Sidebar } from "./sidebar"

interface AppLayoutProps {
  children: React.ReactNode
  /** Permiso necesario para ver la pantalla. Sin él, cualquier miembro del personal entra. */
  permiso?: Permiso
}

/** Marco de la intranet. La sesión ya la garantiza <SesionProvider>. */
export function AppLayout({ children, permiso }: AppLayoutProps) {
  const { tienePermiso } = useSesion()
  const [menuAbierto, setMenuAbierto] = useState(false)

  return (
    <div className="min-h-screen bg-background">
      <Sidebar />
      {/* En pantallas angostas la barra lateral se abre como menú deslizable. */}
      <div className="sticky top-0 z-40 flex h-14 items-center gap-3 border-b border-border bg-sidebar px-4 lg:hidden">
        <Button variant="ghost" size="icon" className="text-sidebar-foreground"
                aria-label="Abrir el menú" onClick={() => setMenuAbierto(true)}>
          <Menu className="h-5 w-5" />
        </Button>
        <BookMarked className="h-5 w-5 text-sidebar-primary" aria-hidden />
        <span className="font-semibold text-sidebar-foreground">Shelfie</span>
      </div>
      <Sheet open={menuAbierto} onOpenChange={setMenuAbierto}>
        <SheetContent side="left" className="w-72 border-0 p-0">
          <SheetTitle className="sr-only">Menú</SheetTitle>
          <Sidebar enHoja onNavegar={() => setMenuAbierto(false)} />
        </SheetContent>
      </Sheet>
      <main className="lg:pl-64">
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
