"use client"

import { useEffect, useState } from "react"
import { useRouter } from "next/navigation"
import Link from "next/link"
import { Bell, Search, AlertTriangle, MapPin } from "lucide-react"

import { Input } from "@/components/ui/input"
import { Button } from "@/components/ui/button"
import {
  Popover,
  PopoverContent,
  PopoverTrigger,
} from "@/components/ui/popover"
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select"
import { useSedes } from "@/components/layout/sede-provider"
import { apiGet } from "@/lib/api"
import type { ApiLoan } from "@/lib/types"

interface HeaderProps {
  title: string
  description?: string
}

export function Header({ title, description }: HeaderProps) {
  const router = useRouter()
  const [query, setQuery] = useState("")
  const [vencidos, setVencidos] = useState<ApiLoan[]>([])

  useEffect(() => {
    // Las notificaciones son los préstamos vencidos: es la alerta que
    // realmente necesita atención del personal.
    // Solo los vencidos: bajar todo el historial en cada página crecía con los años.
    apiGet<ApiLoan[]>("/circulation/loans?estado=vencidos")
      .then(setVencidos)
      .catch(() => setVencidos([]))
  }, [])

  function buscar(e: React.FormEvent) {
    e.preventDefault()
    const q = query.trim()
    if (!q) return
    // El catálogo es el destino natural de la búsqueda global.
    router.push(`/catalogo?q=${encodeURIComponent(q)}`)
  }

  return (
    <header className="sticky top-14 z-30 flex h-16 items-center justify-between gap-3 border-b border-border/70 bg-card/95 px-4 shadow-papel backdrop-blur-sm sm:px-6 lg:top-0">
      <div className="min-w-0">
        <h1 className="truncate text-lg font-semibold text-foreground">{title}</h1>
        {description && <p className="hidden truncate text-sm text-muted-foreground sm:block">{description}</p>}
      </div>

      <div className="flex items-center gap-4">
        <SelectorDeSede />

        <form onSubmit={buscar} className="relative hidden md:block">
          <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
          <Input
            type="search"
            placeholder="Buscar en el catálogo..."
            className="w-64 bg-background pl-9"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
          />
        </form>

        <Popover>
          <PopoverTrigger asChild>
            <Button variant="ghost" size="icon" className="relative">
              <Bell className="h-5 w-5" />
              {vencidos.length > 0 && (
                <span className="absolute right-1.5 top-1.5 h-2 w-2 rounded-full bg-destructive" />
              )}
              <span className="sr-only">Notificaciones</span>
            </Button>
          </PopoverTrigger>
          <PopoverContent align="end" className="w-80 p-0">
            <div className="border-b border-border px-4 py-3">
              <p className="font-medium text-foreground">Notificaciones</p>
              <p className="text-sm text-muted-foreground">
                {vencidos.length === 0
                  ? "Todo al día"
                  : `${vencidos.length} préstamo(s) vencido(s)`}
              </p>
            </div>

            {vencidos.length === 0 ? (
              <div className="px-4 py-8 text-center text-sm text-muted-foreground">
                No hay préstamos vencidos.
              </div>
            ) : (
              <>
                <div className="max-h-72 divide-y divide-border overflow-y-auto">
                  {vencidos.slice(0, 6).map((loan) => (
                    <div key={loan.id} className="flex gap-3 px-4 py-3">
                      <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0 text-destructive" />
                      <div className="min-w-0">
                        <p className="truncate text-sm font-medium text-foreground">
                          {loan.bookTitle}
                        </p>
                        <p className="text-xs text-muted-foreground">
                          {loan.userName} · venció el {loan.dueDate}
                        </p>
                      </div>
                    </div>
                  ))}
                </div>
                <div className="border-t border-border p-2">
                  <Link
                    href="/circulacion"
                    className="block rounded-md px-3 py-2 text-center text-sm font-medium text-primary hover:bg-muted"
                  >
                    Ver circulación
                  </Link>
                </div>
              </>
            )}
          </PopoverContent>
        </Popover>
      </div>
    </header>
  )
}

/** Sede desde la que se opera. Solo aparece cuando la biblioteca tiene más de una. */
function SelectorDeSede() {
  const { sedes, sedeId, cambiarSede } = useSedes()
  if (sedes.length < 2 || sedeId === null) return null

  return (
    <Select value={String(sedeId)} onValueChange={(v) => cambiarSede(Number(v))}>
      <SelectTrigger className="w-52" aria-label="Sede de trabajo" title="Sede de trabajo">
        <MapPin className="h-4 w-4 shrink-0 text-muted-foreground" />
        <SelectValue />
      </SelectTrigger>
      <SelectContent align="end">
        {sedes.map((s) => (
          <SelectItem key={s.id} value={String(s.id)}>
            {s.nombre}
          </SelectItem>
        ))}
      </SelectContent>
    </Select>
  )
}
