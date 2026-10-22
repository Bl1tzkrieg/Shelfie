"use client"

import { useEffect, useState } from "react"
import Link from "next/link"
import { useRouter } from "next/navigation"
import { ArrowLeft } from "lucide-react"

import { Button } from "@/components/ui/button"
import { Skeleton } from "@/components/ui/skeleton"
import { Cota, LLEGO_DE_BUSCAR } from "@/components/lite/resultado"
import { ApiError, api } from "@/lib/api"
import type { FichaPublica } from "@/lib/types"

type Estado =
  | { tipo: "cargando" }
  | { tipo: "noexiste" }
  | { tipo: "error" }
  | { tipo: "listo"; datos: FichaPublica }

/** Vuelve a la búsqueda con el historial si se llegó desde ella; si no, a la pantalla Buscar. */
function VolverABuscar() {
  const router = useRouter()
  const volver = (e: React.MouseEvent) => {
    let desdeBuscar = false
    try {
      desdeBuscar = sessionStorage.getItem(LLEGO_DE_BUSCAR) === "1"
    } catch {
      // almacenamiento no disponible
    }
    if (desdeBuscar && window.history.length > 1) {
      e.preventDefault()
      router.back()
    }
  }
  return (
    <Button asChild variant="ghost" className="-ml-3">
      <Link href="/" onClick={volver}>
        <ArrowLeft aria-hidden /> Volver a la búsqueda
      </Link>
    </Button>
  )
}

function Dato({ rotulo, children }: { rotulo: string; children: React.ReactNode }) {
  return (
    <div className="grid gap-1 py-3 sm:grid-cols-[11rem_1fr] sm:gap-4">
      <dt className="text-sm font-medium text-muted-foreground">{rotulo}</dt>
      <dd className="whitespace-pre-line text-foreground">{children}</dd>
    </div>
  )
}

/** La ficha pública de un libro: todos los campos con valor, la cota destacada y los ejemplares. */
export function Ficha({ id }: { id: string | null }) {
  const [reintento, setReintento] = useState(0)
  const [respuesta, setRespuesta] = useState<{
    clave: string
    resultado: FichaPublica | "noexiste" | "error"
  } | null>(null)

  const idValido = id !== null && /^\d+$/.test(id)
  const clave = `${id}|${reintento}`

  useEffect(() => {
    if (!idValido) return
    const control = new AbortController()
    api<FichaPublica>(`/buscar/${id}`, { signal: control.signal })
      .then((resultado) => setRespuesta({ clave, resultado }))
      .catch((error) => {
        if (control.signal.aborted) return
        const resultado = error instanceof ApiError && error.status === 404 ? "noexiste" : "error"
        setRespuesta({ clave, resultado })
      })
    return () => control.abort()
  }, [id, idValido, clave])

  const estado: Estado = !idValido
    ? { tipo: "noexiste" }
    : respuesta?.clave !== clave
      ? { tipo: "cargando" }
      : respuesta.resultado === "noexiste"
        ? { tipo: "noexiste" }
        : respuesta.resultado === "error"
          ? { tipo: "error" }
          : { tipo: "listo", datos: respuesta.resultado }

  return (
    <div className="space-y-6">
      <VolverABuscar />
      <Contenido estado={estado} onReintentar={() => setReintento((n) => n + 1)} />
    </div>
  )
}

function Contenido({ estado, onReintentar }: { estado: Estado; onReintentar: () => void }) {
  if (estado.tipo === "cargando") {
    return (
      <div className="space-y-3" role="status" aria-label="Cargando la ficha">
        <Skeleton className="h-12 w-48" />
        <Skeleton className="h-8 w-full" />
        <Skeleton className="h-40 w-full" />
      </div>
    )
  }
  if (estado.tipo === "noexiste") {
    return <p className="py-10 text-center text-muted-foreground">No se encontró ese libro.</p>
  }
  if (estado.tipo === "error") {
    return (
      <div role="alert" className="flex flex-col items-center gap-3 rounded-xl border border-destructive/40 bg-card p-6 text-center shadow-papel">
        <p className="text-destructive">No se pudo cargar la ficha. Revisa la conexión con el servidor.</p>
        <Button variant="outline" onClick={onReintentar}>Reintentar</Button>
      </div>
    )
  }

  const { ficha: f, ejemplares } = estado.datos
  const datos: [string, React.ReactNode][] = [
    ["Mención de responsabilidad", f.mencion],
    ["Autor", f.autor],
    ["Otros autores", f.otros_autores.length ? f.otros_autores.join("\n") : null],
    ["Edición", f.edicion],
    ["Lugar", f.lugar],
    ["Editorial", f.editorial],
    ["Año", f.ano],
    ["Páginas", f.paginas],
    ["Ilustraciones", f.ilustraciones],
    ["Dimensiones", f.dimensiones],
    ["ISBN", f.isbn.length ? f.isbn.join("\n") : null],
    ["Materias", f.materias.length ? f.materias.join("\n") : null],
    ["Descripción", f.descripcion],
    ["Notas", f.notas],
  ]

  return (
    <article className="space-y-6">
      <header className="relative space-y-2 overflow-hidden rounded-2xl border border-border/80 bg-card p-5 pl-7 shadow-papel-alzado sm:p-7 sm:pl-9">
        <span aria-hidden className="absolute inset-y-0 left-0 w-1.5 bg-primary" />
        <p className="text-xs font-semibold uppercase tracking-wider text-muted-foreground">Cota</p>
        <Cota cota={f.cota || null} className="block text-4xl" />
        <h1 className="pt-2 text-2xl font-semibold leading-snug text-balance text-foreground">{f.titulo}</h1>
        {f.subtitulo && <p className="text-lg text-pretty text-muted-foreground">{f.subtitulo}</p>}
      </header>

      <dl className="divide-y divide-border rounded-xl border border-border/80 bg-card px-4 shadow-papel sm:px-6">
        {datos
          .filter(([, valor]) => valor !== null && valor !== "")
          .map(([rotulo, valor]) => <Dato key={rotulo} rotulo={rotulo}>{valor}</Dato>)}
      </dl>

      <section aria-labelledby="ejemplares-titulo" className="space-y-3">
        <h2 id="ejemplares-titulo" className="text-lg font-semibold text-foreground">
          Ejemplares ({ejemplares.length})
        </h2>
        {ejemplares.length === 0 ? (
          <p className="text-muted-foreground">Este libro no tiene ejemplares registrados.</p>
        ) : (
          <ul className="divide-y divide-border rounded-xl border border-border/80 bg-card shadow-papel">
            {ejemplares.map((e, i) => (
              <li key={i} className="flex flex-wrap items-baseline gap-x-6 gap-y-1 px-4 py-3 sm:px-6">
                <Cota cota={e.cota} className="text-xl" />
                {e.numero_copia && <span className="text-foreground">{e.numero_copia}</span>}
                {e.nota && <span className="text-sm text-muted-foreground">{e.nota}</span>}
              </li>
            ))}
          </ul>
        )}
      </section>
    </article>
  )
}
