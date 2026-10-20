"use client"

import { useCallback, useEffect, useRef, useState } from "react"
import { useRouter, useSearchParams } from "next/navigation"
import { Search } from "lucide-react"

import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select"
import { Skeleton } from "@/components/ui/skeleton"
import { Resultado, marcarLlegadaDeBuscar } from "@/components/lite/resultado"
import { api } from "@/lib/api"
import type { CampoBusqueda, PaginaBusqueda } from "@/lib/types"

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

  return (
    <div className="space-y-6">
      <form onSubmit={buscarYa} role="search" className="flex flex-col gap-3 sm:flex-row">
        <div className="relative flex-1">
          <label htmlFor="buscar-q" className="sr-only">Buscar en el catálogo</label>
          <Search className="pointer-events-none absolute left-4 top-1/2 h-5 w-5 -translate-y-1/2 text-muted-foreground" aria-hidden />
          <Input
            id="buscar-q"
            type="search"
            autoFocus
            autoComplete="off"
            value={entrada}
            onChange={(e) => escribir(e.target.value)}
            placeholder="Título, autor, materia, cota o ISBN"
            className="h-14 pl-12 text-lg md:text-lg"
          />
        </div>
        <Select value={consulta.campo} onValueChange={cambiarCampo}>
          <SelectTrigger aria-label="Buscar en" className="h-14 w-full text-base sm:w-44">
            <SelectValue />
          </SelectTrigger>
          <SelectContent>
            {CAMPOS.map((c) => (
              <SelectItem key={c.valor} value={c.valor}>{c.rotulo}</SelectItem>
            ))}
          </SelectContent>
        </Select>
      </form>

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
      <p className="py-10 text-center text-muted-foreground">
        Escribe un título, autor, materia, cota o ISBN para buscar.
      </p>
    )
  }
  if (estado.tipo === "cargando") {
    return (
      <div className="space-y-3" role="status" aria-label="Buscando">
        {[0, 1, 2].map((i) => <Skeleton key={i} className="h-24 w-full" />)}
      </div>
    )
  }
  if (estado.tipo === "error") {
    return (
      <div role="alert" className="flex flex-col items-center gap-3 rounded-lg border border-destructive/40 p-6 text-center">
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
