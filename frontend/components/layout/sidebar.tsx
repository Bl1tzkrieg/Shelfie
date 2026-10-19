"use client"

import { useEffect, useState } from "react"
import Link from "next/link"
import { usePathname } from "next/navigation"
import {
  LayoutDashboard,
  Search,
  ArrowRightLeft,
  Users,
  BarChart3,
  Settings,
  BookMarked,
  BookmarkCheck,
  ExternalLink,
  KeyRound,
  LogOut,
  Newspaper,
  ShoppingCart,
  Truck,
  History,
} from "lucide-react"
import { CambiarClaveDialog } from "@/components/auth/cambiar-clave-dialog"
import { useSesion } from "@/components/auth/sesion-provider"
import { Button } from "@/components/ui/button"
import { apiGet } from "@/lib/api"
import type { Configuracion, Permiso } from "@/lib/types"
import { cn } from "@/lib/utils"

type ItemNavegacion = {
  name: string
  href: string
  icon: typeof LayoutDashboard
  /** Permiso para ver el ítem; sin él, lo ve todo el personal. */
  permiso?: Permiso
}

const navigation: ItemNavegacion[] = [
  { name: "Dashboard", href: "/", icon: LayoutDashboard },
  { name: "Catálogo", href: "/catalogo", icon: Search },
  { name: "Circulación", href: "/circulacion", icon: ArrowRightLeft },
  { name: "Reservas", href: "/circulacion/reservas", icon: BookmarkCheck },
  { name: "Traslados", href: "/circulacion/traslados", icon: Truck },
  { name: "Usuarios", href: "/usuarios", icon: Users },
  { name: "Adquisiciones", href: "/adquisiciones", icon: ShoppingCart, permiso: "adquisiciones" },
  { name: "Seriadas", href: "/seriadas", icon: Newspaper, permiso: "seriadas" },
  { name: "Reportes", href: "/reportes", icon: BarChart3, permiso: "reportes" },
  { name: "Registro", href: "/registro", icon: History, permiso: "registro" },
  { name: "Configuración", href: "/configuracion", icon: Settings, permiso: "configuracion" },
]

function describirRol(permisos: Permiso[]) {
  if (permisos.includes("superbibliotecario")) return "Administrador"
  if (permisos.length === 0) return "Solo consulta"
  return "Personal"
}

// El nombre de la institución casi nunca cambia: se pide una vez por pestaña, no en cada
// navegación (la barra lateral se vuelve a montar con cada página).
let institucionEnMemoria: string | null | undefined

/** Tras cambiar el nombre en Configuración, la próxima barra lateral lo vuelve a pedir. */
export function olvidarInstitucion() {
  institucionEnMemoria = undefined
}

export function Sidebar({ enHoja = false, onNavegar }: {
  /** Dentro del menú deslizable del celular: sin posición fija ni ancho propio. */
  enHoja?: boolean
  /** Para cerrar el menú del celular al elegir una sección. */
  onNavegar?: () => void
} = {}) {
  const pathname = usePathname()
  const { usuario, tienePermiso, cerrarSesion } = useSesion()
  // Shelfie es el producto; el nombre de la institución sale de Configuración.
  const [institucion, setInstitucion] = useState<string | null>(institucionEnMemoria ?? null)
  const [cambiandoClave, setCambiandoClave] = useState(false)

  useEffect(() => {
    if (institucionEnMemoria !== undefined) return
    apiGet<Configuracion>("/settings")
      .then((c) => {
        institucionEnMemoria = c.institucion.nombre
        setInstitucion(institucionEnMemoria)
      })
      .catch(() => setInstitucion(null))
  }, [])

  const visibles = navigation.filter((item) => !item.permiso || tienePermiso(item.permiso))
  // La entrada más específica que contiene la ruta actual (Reservas antes que Circulación).
  const activo = visibles
    .filter((i) => pathname === i.href || (i.href !== "/" && pathname.startsWith(`${i.href}/`)))
    .sort((a, b) => b.href.length - a.href.length)[0]?.href

  return (
    <aside className={cn("flex flex-col bg-sidebar",
                         enHoja ? "h-full w-full" : "fixed inset-y-0 left-0 z-50 hidden w-64 lg:flex")}>
      {/* Logo */}
      <div className="flex h-16 items-center gap-3 border-b border-sidebar-border px-6">
        <div className="flex h-9 w-9 items-center justify-center rounded-lg bg-sidebar-primary">
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
                  ? "bg-sidebar-accent text-sidebar-accent-foreground"
                  : "text-sidebar-foreground/70 hover:bg-sidebar-accent/50 hover:text-sidebar-foreground"
              )}
            >
              <item.icon className="h-5 w-5" />
              {item.name}
            </Link>
          )
        })}
      </nav>

      <div className="px-3 pb-2">
        <a
          href="/opac"
          target="_blank"
          rel="noopener"
          className="flex items-center gap-3 rounded-lg px-3 py-2 text-sm text-sidebar-foreground/60 transition-colors hover:bg-sidebar-accent/50 hover:text-sidebar-foreground"
        >
          <ExternalLink className="h-4 w-4" />
          Catálogo público
        </a>
      </div>

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
                {describirRol(usuario.permisos)}
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
