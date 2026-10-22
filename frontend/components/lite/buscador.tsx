"use client"

import { useCallback, useEffect, useRef, useState } from "react"
import { useRouter, useSearchParams } from "next/navigation"
import { Search } from "lucide-react"

import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select"
import { Skeleton } from "@/components/ui/skeleton"
import { FondoGeometrico } from "@/components/lite/fondo-geometrico"
import { Resultado, marcarLlegadaDeBuscar } from "@/components/lite/resultado"
import { api } from "@/lib/api"
import type { CampoBusqueda, PaginaBusqueda } from "@/lib/types"
import { cn } from "@/lib/utils"

const PAUSA_MS = 300
const POR_PAGINA = 20

const CAMPOS: { valor: CampoBusqueda; rotulo: string }[] = [
  { valor: "todo", rotulo: "Todo" },
  { valor: "titulo", rotulo: "Título" },
  { valor: "autor", rotulo: "Autor" },
  { valor: "materia", rotulo: "Materia" },
  { valor: "cota", rotulo: "Cota" },
  { valor: "isbn", rotulo: "ISBN" },
  { valor: "editorial", rotulo: "Editorial" },
]

function campoValido(valor: string | null): CampoBusqueda {
  return CAMPOS.find((c) => c.valor === valor)?.valor ?? "todo"
}

type Consulta = { q: string; campo: CampoBusqueda; pagina: number }

type Estado =
  | { tipo: "inactivo" }
  | { tipo: "cargando" }
  | { tipo: "error" }
  | { tipo: "listo"; datos: PaginaBusqueda }

function urlDe({ q, campo, pagina }: Consulta): string {
  const params = new URLSearchParams()
  if (q) params.set("q", q)
  if (campo !== "todo") params.set("campo", campo)
  if (pagina > 1) params.set("pagina", String(pagina))
  const texto = params.toString()
  return texto ? `/?${texto}` : "/"
}

/** Buscador del catálogo: la consulta vive en la URL (?q=&campo=&pagina=) para que "atrás" funcione. */
export function Buscador() {
  const router = useRouter()
  const params = useSearchParams()

  const [entrada, setEntrada] = useState(params.get("q") ?? "")
  const [consulta, setConsulta] = useState<Consulta>(() => ({
    q: (params.get("q") ?? "").trim(),
    campo: campoValido(params.get("campo")),
    pagina: Math.max(1, Number(params.get("pagina")) || 1),
  }))
  const [reintento, setReintento] = useState(0)
  // La respuesta lleva la clave de la consulta que la pidió: si no coincide con la actual,
  // todavía se está buscando.
  const [respuesta, setRespuesta] = useState<{ clave: string; resultado: PaginaBusqueda | "error" } | null>(null)
  const pausa = useRef<ReturnType<typeof setTimeout> | null>(null)

  useEffect(() => {
    marcarLlegadaDeBuscar(false)
  }, [])

  useEffect(() => () => { if (pausa.current) clearTimeout(pausa.current) }, [])

  const clave = `${consulta.q}|${consulta.campo}|${consulta.pagina}|${reintento}`

  // Cada cambio de consulta actualiza la URL (sin apilar historial) y pide la página.
  // El AbortController descarta la petición anterior: nunca se ve un resultado viejo.
  useEffect(() => {
    router.replace(urlDe(consulta), { scroll: false })
    if (!consulta.q) return
    const control = new AbortController()
    const query = new URLSearchParams({
      q: consulta.q,
      campo: consulta.campo,
      pagina: String(consulta.pagina),
    })
    api<PaginaBusqueda>(`/buscar?${query}`, { signal: control.signal })
      .then((resultado) => setRespuesta({ clave, resultado }))
      .catch(() => {
        if (!control.signal.aborted) setRespuesta({ clave, resultado: "error" })
      })
    return () => control.abort()
  }, [consulta, clave, router])

  const estado: Estado = !consulta.q
    ? { tipo: "inactivo" }
    : respuesta?.clave !== clave
      ? { tipo: "cargando" }
      : respuesta.resultado === "error"
        ? { tipo: "error" }
        : { tipo: "listo", datos: respuesta.resultado }

  const escribir = useCallback((texto: string) => {
    setEntrada(texto)
    if (pausa.current) clearTimeout(pausa.current)
    pausa.current = setTimeout(() => {
      setConsulta((c) => ({ ...c, q: texto.trim(), pagina: 1 }))
    }, PAUSA_MS)
  }, [])

  const irAPagina = (pagina: number) => {
    setConsulta((c) => ({ ...c, pagina }))
    window.scrollTo({ top: 0 })
  }

  const cambiarCampo = (valor: string) => {
    setConsulta((c) => ({ ...c, q: entrada.trim(), campo: campoValido(valor), pagina: 1 }))
  }

  const buscarYa = (e: React.FormEvent) => {
    e.preventDefault()
    if (pausa.current) clearTimeout(pausa.current)
    setConsulta((c) => ({ ...c, q: entrada.trim(), pagina: 1 }))
  }

  // Con una consulta en curso el encabezado se reduce a una franja para no empujar los resultados.
  const compacto = estado.tipo !== "inactivo"
  // Transición de las medidas del encabezado; con movimiento reducido el cambio es inmediato.
  const transicion = "duration-500 ease-out motion-reduce:transition-none"

  return (
    <div className="space-y-6">
      <div
        className={cn(
          "relative isolate overflow-hidden rounded-2xl text-hero-foreground shadow-papel-flotante",
          "transition-[padding]", transicion,
          compacto ? "px-3 py-3 sm:px-5 sm:py-4" : "px-5 pb-8 pt-10 sm:px-10 sm:pb-12 sm:pt-16",
        )}
      >
        <FondoGeometrico compacto={compacto} />

        <div className="max-w-2xl">
          <h1
            className={cn(
              "font-semibold tracking-tight text-balance transition-[font-size,line-height]", transicion,
              compacto ? "px-1 text-sm/5 text-hero-muted" : "text-3xl/tight sm:text-4xl/tight",
            )}
          >
            Encuentra un libro y su ubicación
          </h1>
          <div
            aria-hidden={compacto}
            className={cn(
              "grid transition-[grid-template-rows,opacity]", transicion,
              compacto ? "grid-rows-[0fr] opacity-0" : "grid-rows-[1fr] opacity-100",
            )}
          >
            <p className="min-h-0 overflow-hidden">
              <span className="block pt-3 text-base text-pretty text-hero-muted sm:text-lg">
                Busca por título, autor, materia, cota o ISBN y te mostramos en qué estante está.
              </span>
            </p>
          </div>
        </div>

        <form
          onSubmit={buscarYa}
          role="search"
          className={cn(
            // En escritorio deja ver el estante del fondo a la derecha.
            "flex flex-col gap-2 rounded-xl bg-card p-2 text-card-foreground shadow-papel-flotante sm:flex-row lg:max-w-2xl",
            "transition-[margin]", transicion,
            compacto ? "mt-2" : "mt-8",
          )}
        >
          <div className="relative flex-1">
            <label htmlFor="buscar-q" className="sr-only">Buscar en el catálogo</label>
            <Search className="pointer-events-none absolute left-4 top-1/2 h-5 w-5 -translate-y-1/2 text-primary" aria-hidden />
            <Input
              id="buscar-q"
              type="search"
              autoFocus
              autoComplete="off"
              value={entrada}
              onChange={(e) => escribir(e.target.value)}
              placeholder="Título, autor, materia, cota o ISBN"
              className="h-12 border-transparent pl-12 text-lg shadow-none md:text-lg"
            />
          </div>
          <Select value={consulta.campo} onValueChange={cambiarCampo}>
            <SelectTrigger aria-label="Buscar en"
                           className="h-12 w-full border-transparent bg-muted text-base shadow-none data-[size=default]:h-12 sm:w-44">
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              {CAMPOS.map((c) => (
                <SelectItem key={c.valor} value={c.valor}>{c.rotulo}</SelectItem>
              ))}
            </SelectContent>
          </Select>
        </form>
      </div>

      <Resultados
        estado={estado}
        consulta={consulta}
        onPagina={irAPagina}
        onReintentar={() => setReintento((n) => n + 1)}
      />
    </div>
  )
}

function Resultados({
  estado,
  consulta,
  onPagina,
  onReintentar,
}: {
  estado: Estado
  consulta: Consulta
  onPagina: (pagina: number) => void
  onReintentar: () => void
}) {
  if (estado.tipo === "inactivo") {
    return (
      <p className="px-2 py-4 text-center text-sm text-muted-foreground">
        Si sabes la cota, escríbela tal cual (p. ej. 612.015) o elige «Cota» en «Buscar en».
      </p>
    )
  }
  if (estado.tipo === "cargando") {
    return (
      <div className="space-y-3" role="status" aria-label="Buscando">
        {[0, 1, 2].map((i) => <Skeleton key={i} className="h-24 w-full rounded-xl" />)}
      </div>
    )
  }
  if (estado.tipo === "error") {
    return (
      <div role="alert" className="flex flex-col items-center gap-3 rounded-xl border border-destructive/40 bg-card p-6 text-center shadow-papel">
        <p className="text-destructive">No se pudo buscar. Revisa la conexión con el servidor.</p>
        <Button variant="outline" onClick={onReintentar}>Reintentar</Button>
      </div>
    )
  }

  const { total, resultados } = estado.datos
  if (total === 0) {
    return (
      <p className="py-10 text-center text-muted-foreground">
        No se encontró nada con «{consulta.q}». Prueba con menos palabras o busca solo por autor o por cota.
      </p>
    )
  }

  const paginas = Math.max(1, Math.ceil(total / POR_PAGINA))
  return (
    <section aria-label="Resultados" className="space-y-4">
      <p className="text-sm text-muted-foreground" aria-live="polite">
        {total === 1 ? "1 resultado" : `${total} resultados`}
      </p>
      <ul className="space-y-3">
        {resultados.map((r) => <Resultado key={r.id} r={r} />)}
      </ul>
      {paginas > 1 && (
        <nav aria-label="Paginación" className="flex items-center justify-between gap-3 pt-2">
          <Button variant="outline" disabled={consulta.pagina <= 1} onClick={() => onPagina(consulta.pagina - 1)}>
            Anterior
          </Button>
          <span className="text-sm text-muted-foreground">Página {consulta.pagina} de {paginas}</span>
          <Button variant="outline" disabled={consulta.pagina >= paginas} onClick={() => onPagina(consulta.pagina + 1)}>
            Siguiente
          </Button>
        </nav>
      )}
    </section>
  )
}
