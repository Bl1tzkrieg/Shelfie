"use client"

import { Suspense, useEffect, useState } from "react"
import Link from "next/link"
import { usePathname, useRouter, useSearchParams } from "next/navigation"
import { BookMarked, LogIn, LogOut, Search, UserRound } from "lucide-react"

import { destinoActual, registrarPaginaVista, rutaDeEntrada, useLector } from "@/components/opac/lector-provider"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { apiGet } from "@/lib/api"
import type { Biblioteca } from "@/lib/opac"

/** Cabecera, buscador y pie del catálogo público. */
export function OpacShell({ children }: { children: React.ReactNode }) {
  const [biblioteca, setBiblioteca] = useState<Biblioteca | null>(null)
  const pathname = usePathname()

  useEffect(() => {
    registrarPaginaVista()
  }, [pathname])

  useEffect(() => {
    apiGet<Biblioteca>("/opac/library").then(setBiblioteca).catch(() => setBiblioteca(null))
  }, [])

  return (
    <div className="flex min-h-screen flex-col bg-background">
      <Cabecera nombre={biblioteca?.nombre ?? null} />
      <main className="mx-auto w-full max-w-6xl flex-1 px-4 py-8 sm:px-6">{children}</main>
      <Pie biblioteca={biblioteca} />
    </div>
  )
}

function Cabecera({ nombre }: { nombre: string | null }) {
  const pathname = usePathname()
  const router = useRouter()
  const { lector, cargando, salir } = useLector()
  const enInicio = pathname === "/opac"

  async function cerrar() {
    await salir()
    router.push("/opac")
  }

  return (
    <header className="border-b border-border/70 bg-card/95 shadow-papel">
      <div className="mx-auto flex max-w-6xl flex-wrap items-center gap-x-6 gap-y-3 px-4 py-3 sm:px-6">
        <Link href="/opac" className="flex items-center gap-3">
          <span className="flex h-9 w-9 items-center justify-center rounded-lg bg-hero shadow-papel">
            <BookMarked className="h-5 w-5 text-sidebar-primary" aria-hidden />
          </span>
          <span className="leading-tight">
            <span className="block text-sm font-semibold text-foreground">{nombre ?? "Biblioteca"}</span>
            <span className="block text-xs text-muted-foreground">Catálogo en línea</span>
          </span>
        </Link>

        {!enInicio && (
          <Suspense fallback={null}>
            <BuscadorConUrl />
          </Suspense>
        )}

        <nav aria-label="Cuenta" className="ml-auto flex items-center gap-2">
          {cargando ? null : lector ? (
            <>
              <Button asChild variant={pathname.startsWith("/opac/cuenta") ? "secondary" : "ghost"} size="sm">
                <Link href="/opac/cuenta">
                  <UserRound className="mr-1.5 h-4 w-4" />
                  {lector.nombre}
                  {lector.para_retirar > 0 && (
                    <span className="ml-1.5 rounded-full bg-aviso px-1.5 text-xs font-semibold text-aviso-foreground">
                      {lector.para_retirar}
                    </span>
                  )}
                </Link>
              </Button>
              <Button variant="ghost" size="sm" onClick={cerrar} aria-label="Salir">
                <LogOut className="h-4 w-4 sm:mr-1.5" />
                <span className="hidden sm:inline">Salir</span>
              </Button>
            </>
          ) : (
            <Button asChild size="sm">
              <Link href={rutaDeEntrada(pathname)} onClick={(e) => {
                // Con la búsqueda incluida: al entrar se vuelve a los mismos resultados.
                e.preventDefault()
                router.push(rutaDeEntrada(destinoActual(pathname)))
              }}>
                <LogIn className="mr-1.5 h-4 w-4" />
                Entrar
              </Link>
            </Button>
          )}
        </nav>
      </div>
    </header>
  )
}

/** El buscador muestra lo que se buscó; se reinicia cuando cambia la búsqueda de la URL. */
function BuscadorConUrl() {
  const q = useSearchParams().get("q") ?? ""
  return <BuscadorCabecera key={q} inicial={q} />
}

function BuscadorCabecera({ inicial }: { inicial: string }) {
  const router = useRouter()
  const [texto, setTexto] = useState(inicial)

  return (
    <form
      role="search"
      className="order-last w-full sm:order-none sm:w-auto sm:flex-1 sm:max-w-md"
      onSubmit={(e) => {
        e.preventDefault()
        router.push(`/opac/buscar?q=${encodeURIComponent(texto.trim())}`)
      }}
    >
      <div className="relative">
        <Search className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-primary" />
        <Input
          aria-label="Buscar en el catálogo"
          placeholder="Título, autor, materia o ISBN"
          className="bg-background pl-9"
          value={texto}
          onChange={(e) => setTexto(e.target.value)}
        />
      </div>
    </form>
  )
}

function Pie({ biblioteca }: { biblioteca: Biblioteca | null }) {
  if (!biblioteca) return null
  return (
    <footer className="border-t border-border bg-card">
      <div className="mx-auto grid max-w-6xl gap-6 px-4 py-8 text-sm sm:grid-cols-2 sm:px-6 lg:grid-cols-3">
        <div>
          <p className="font-semibold text-foreground">{biblioteca.nombre}</p>
          {biblioteca.direccion && <p className="text-muted-foreground">{biblioteca.direccion}</p>}
          {biblioteca.telefono && <p className="text-muted-foreground">{biblioteca.telefono}</p>}
          {biblioteca.email && <p className="text-muted-foreground">{biblioteca.email}</p>}
        </div>
        {biblioteca.sedes.length > 1 && (
          <div className="lg:col-span-2">
            <p className="mb-2 font-semibold text-foreground">Sedes donde retirar reservas</p>
            <ul className="grid gap-x-6 gap-y-2 sm:grid-cols-2">
              {biblioteca.sedes.map((s) => (
                <li key={s.id}>
                  <span className="text-foreground">{s.nombre}</span>
                  {(s.direccion || s.telefono) && (
                    <span className="block text-muted-foreground">
                      {[s.direccion, s.telefono].filter(Boolean).join(" · ")}
                    </span>
                  )}
                </li>
              ))}
            </ul>
          </div>
        )}
      </div>
    </footer>
  )
}
