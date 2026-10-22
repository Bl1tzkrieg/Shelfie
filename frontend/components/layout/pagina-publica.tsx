"use client"

import Link from "next/link"
import { BookMarked } from "lucide-react"

import { AvisoRespaldo } from "@/components/lite/aviso-respaldo"
import { useSesion } from "@/components/auth/sesion-provider"
import { useNombreBiblioteca } from "@/lib/biblioteca"

/**
 * Marco de las pantallas que se ven sin sesión (Buscar y la ficha de un libro): un
 * encabezado mínimo con el nombre de la biblioteca y la entrada del personal.
 */
export function PaginaPublica({ children }: { children: React.ReactNode }) {
  const nombre = useNombreBiblioteca()
  const { usuario, cargando, tienePermiso } = useSesion()

  return (
    <div className="min-h-screen bg-background">
      <AvisoRespaldo />
      <header className="border-b border-border/70 bg-card/95 shadow-papel">
        <div className="mx-auto flex h-16 max-w-5xl items-center justify-between gap-4 px-4">
          <Link href="/" className="flex min-w-0 items-center gap-3">
            <span className="flex h-9 w-9 shrink-0 items-center justify-center rounded-lg bg-hero shadow-papel">
              <BookMarked className="h-5 w-5 text-sidebar-primary" aria-hidden />
            </span>
            <span className="truncate text-base font-semibold text-foreground">
              {nombre ?? "Biblioteca"}
            </span>
          </Link>
          <nav className="flex shrink-0 items-center gap-4 text-sm">
            <Link href="/" className="text-muted-foreground transition-colors hover:text-foreground">Buscar</Link>
            {!cargando && usuario && tienePermiso("catalogo") && (
              <Link href="/libros/" className="text-muted-foreground transition-colors hover:text-foreground">
                Ingreso / Libros
              </Link>
            )}
            {!cargando && !usuario && (
              <Link href="/login/"
                    className="rounded-md px-3 py-1.5 font-medium text-primary transition-colors hover:bg-accent hover:text-accent-foreground">
                Entrar
              </Link>
            )}
          </nav>
        </div>
      </header>
      <main className="mx-auto max-w-5xl px-4 py-6 sm:py-8">{children}</main>
    </div>
  )
}
