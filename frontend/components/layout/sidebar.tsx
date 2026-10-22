"use client"

import { useState } from "react"
import Link from "next/link"
import { usePathname } from "next/navigation"
import {
  BookMarked,
  BookPlus,
  History,
  KeyRound,
  Library,
  LogOut,
  Search,
  Settings,
  Users,
  type LucideIcon,
} from "lucide-react"
import { CambiarClaveDialog } from "@/components/auth/cambiar-clave-dialog"
import { useSesion } from "@/components/auth/sesion-provider"
import { Button } from "@/components/ui/button"
import { useNombreBiblioteca } from "@/lib/biblioteca"
import { NOMBRE_ROL, type Permiso } from "@/lib/types"
import { cn } from "@/lib/utils"

type ItemNavegacion = {
  name: string
  href: string
  icon: LucideIcon
  /** Permiso para ver el ítem; sin él, lo ve todo el personal. */
  permiso?: Permiso
}

const navigation: ItemNavegacion[] = [
  { name: "Buscar", href: "/", icon: Search },
  { name: "Ingreso", href: "/ingreso", icon: BookPlus, permiso: "catalogo" },
  { name: "Libros", href: "/libros", icon: Library, permiso: "catalogo" },
  { name: "Usuarios", href: "/usuarios", icon: Users, permiso: "superbibliotecario" },
  { name: "Registro", href: "/registro", icon: History, permiso: "superbibliotecario" },
  { name: "Configuración", href: "/configuracion", icon: Settings, permiso: "superbibliotecario" },
]

/** La ruta sin la barra final que agrega `trailingSlash` (salvo la raíz). */
function sinBarraFinal(ruta: string) {
  return ruta.length > 1 && ruta.endsWith("/") ? ruta.slice(0, -1) : ruta
}

export function Sidebar({ enHoja = false, onNavegar }: {
  /** Dentro del menú deslizable del celular: sin posición fija ni ancho propio. */
  enHoja?: boolean
  /** Para cerrar el menú del celular al elegir una sección. */
  onNavegar?: () => void
} = {}) {
  const pathname = usePathname()
  const { usuario, tienePermiso, cerrarSesion } = useSesion()
  // Shelfie es el producto; el nombre de la biblioteca sale de Configuración.
  const institucion = useNombreBiblioteca()
  const [cambiandoClave, setCambiandoClave] = useState(false)

  const visibles = navigation.filter((item) => !item.permiso || tienePermiso(item.permiso))
  const ruta = sinBarraFinal(pathname)
  const activo = visibles.find((i) => i.href === ruta)?.href

  return (
    <aside className={cn("flex flex-col bg-sidebar",
                         enHoja ? "h-full w-full" : "fixed inset-y-0 left-0 z-50 hidden w-64 lg:flex")}>
      {/* Logo */}
      <div className="flex h-16 items-center gap-3 border-b border-sidebar-border px-6">
        <div className="flex h-9 w-9 items-center justify-center rounded-lg bg-sidebar-primary shadow-papel">
          <BookMarked className="h-5 w-5 text-sidebar-primary-foreground" />
        </div>
        <div className="flex min-w-0 flex-col">
          <span className="text-base font-semibold text-sidebar-foreground">Shelfie</span>
          {institucion && (
            <span className="truncate text-xs text-sidebar-foreground/60">{institucion}</span>
          )}
        </div>
      </div>

      {/* Navigation */}
      <nav className="flex-1 space-y-1 px-3 py-4">
        {visibles.map((item) => {
          const isActive = item.href === activo

          return (
            <Link
              key={item.name}
              href={item.href}
              onClick={onNavegar}
              className={cn(
                "flex items-center gap-3 rounded-lg px-3 py-2.5 text-sm font-medium transition-colors",
                isActive
                  ? "bg-sidebar-accent text-sidebar-accent-foreground shadow-papel"
                  : "text-sidebar-foreground/70 hover:bg-sidebar-accent/50 hover:text-sidebar-foreground"
              )}
            >
              <item.icon className={cn("h-5 w-5", isActive && "text-sidebar-primary")} />
              {item.name}
            </Link>
          )
        })}
      </nav>

      {/* User section */}
      {usuario && (
        <div className="border-t border-sidebar-border p-4">
          <div className="flex items-center gap-3">
            <div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-full bg-sidebar-accent text-sm font-medium text-sidebar-accent-foreground">
              {`${usuario.nombre[0] ?? ""}${usuario.apellido[0] ?? ""}`.toUpperCase()}
            </div>
            <div className="flex min-w-0 flex-1 flex-col">
              <span className="truncate text-sm font-medium text-sidebar-foreground">
                {usuario.nombre} {usuario.apellido}
              </span>
              <span className="text-xs text-sidebar-foreground/60">
                {NOMBRE_ROL[usuario.rol]}
              </span>
            </div>
            <Button
              variant="ghost"
              size="icon"
              className="shrink-0 text-sidebar-foreground/70 hover:text-sidebar-foreground"
              onClick={() => setCambiandoClave(true)}
              title="Cambiar contraseña"
            >
              <KeyRound className="h-4 w-4" />
              <span className="sr-only">Cambiar contraseña</span>
            </Button>
            <Button
              variant="ghost"
              size="icon"
              className="shrink-0 text-sidebar-foreground/70 hover:text-sidebar-foreground"
              onClick={() => cerrarSesion()}
              title="Cerrar sesión"
            >
              <LogOut className="h-4 w-4" />
              <span className="sr-only">Cerrar sesión</span>
            </Button>
          </div>
          <CambiarClaveDialog open={cambiandoClave} onOpenChange={setCambiandoClave} />
        </div>
      )}
    </aside>
  )
}
