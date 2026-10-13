"use client"

import { Suspense, useEffect, useState } from "react"
import Link from "next/link"
import { usePathname, useRouter, useSearchParams } from "next/navigation"
import { ChevronLeft, ChevronRight, Loader2, X } from "lucide-react"

import { ClaveFaceta, FacetasBusqueda } from "@/components/catalogo/facetas-busqueda"
import { TituloResultado } from "@/components/opac/titulo-resultado"
import { Button } from "@/components/ui/button"
import { apiGet, mensajeDeError } from "@/lib/api"
import type { ResultadosOpac } from "@/lib/opac"

const POR_PAGINA = 20
const FACETAS: ClaveFaceta[] = ["disponible", "tipo", "materia", "autor", "decada"]

export default function BuscarPage() {
  return (
    <Suspense fallback={null}>
      <Resultados />
    </Suspense>
  )
}

function Resultados() {
  const router = useRouter()
  const pathname = usePathname()
  const params = useSearchParams()
  const clave = params.toString()
  const q = params.get("q") ?? ""
  const pagina = Math.max(1, Number(params.get("pagina")) || 1)
  const seleccion: Partial<Record<ClaveFaceta, string>> = {}
  for (const f of FACETAS) {
    const v = params.get(f)
    if (v) seleccion[f] = v
  }

  const [respuesta, setRespuesta] = useState<ResultadosOpac | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [buscando, setBuscando] = useState(true)

  useEffect(() => {
    const p = new URLSearchParams(clave)
    p.delete("pagina")
    p.set("pagina", String(pagina))
    p.set("limit", String(POR_PAGINA))
    let vigente = true
    setBuscando(true)
    apiGet<ResultadosOpac>(`/opac/search?${p}`)
      .then((r) => {
        if (!vigente) return
        setRespuesta(r)
        setError(null)
      })
      .catch((e) => vigente && setError(mensajeDeError(e)))
      .finally(() => vigente && setBuscando(false))
    return () => {
      vigente = false
    }
  }, [clave, pagina])

  function cambiar(cambios: Record<string, string | null>) {
    const p = new URLSearchParams(clave)
    for (const [k, v] of Object.entries(cambios)) {
      if (v === null || v === "") p.delete(k)
      else p.set(k, v)
    }
    if (!("pagina" in cambios)) p.delete("pagina")
    router.push(`${pathname}?${p}`)
  }

  const elegidas = Object.entries(seleccion)

  return (
    <div className="grid gap-8 lg:grid-cols-[14rem_1fr]">
      <aside aria-label="Refinar la búsqueda" className="order-last lg:order-none">
        {respuesta && (
          <FacetasBusqueda
            facetas={respuesta.facetas}
            seleccion={seleccion}
            onElegir={(clave, valor) => cambiar({ [clave]: valor })}
          />
        )}
      </aside>

      <section aria-live="polite" className="min-w-0 space-y-4">
        <div className="flex flex-wrap items-baseline justify-between gap-2">
          <h1 className="text-xl font-semibold text-foreground">
            {q ? <>Resultados para «{q}»</> : "Todo el catálogo"}
          </h1>
          {respuesta && (
            <p className="text-sm tabular-nums text-muted-foreground">
              {respuesta.total} título{respuesta.total === 1 ? "" : "s"}
            </p>
          )}
        </div>

        {elegidas.length > 0 && (
          <div className="flex flex-wrap gap-2">
            {elegidas.map(([k, v]) => (
              <button
                key={k}
                type="button"
                onClick={() => cambiar({ [k]: null })}
                className="inline-flex items-center gap-1 rounded-full bg-primary/10 px-3 py-1 text-sm text-primary hover:bg-primary/15"
              >
                {k === "disponible" ? (v === "si" ? "Con ejemplares libres" : "Sin ejemplares libres")
                  : k === "decada" ? `${v}–${Number(v) + 9}` : v}
                <X className="h-3.5 w-3.5" aria-label="Quitar" />
              </button>
            ))}
          </div>
        )}

        {error && <p role="alert" className="text-sm text-destructive">{error}</p>}
        {buscando && !respuesta && (
          <p className="flex items-center text-sm text-muted-foreground">
            <Loader2 className="mr-2 h-4 w-4 animate-spin" /> Buscando…
          </p>
        )}

        {respuesta && respuesta.total === 0 && (
          <div className="rounded-lg border border-dashed border-border p-8 text-center">
            <p className="font-medium text-foreground">No encontramos nada con esa búsqueda.</p>
            <p className="mt-1 text-sm text-muted-foreground">
              Prueba con menos palabras o quita algún filtro. Si la biblioteca no lo tiene, puedes{" "}
              <Link href="/opac/cuenta?vista=sugerencias" className="text-primary hover:underline">
                sugerir que lo compre
              </Link>
              .
            </p>
          </div>
        )}

        {respuesta && respuesta.total > 0 && (
          <ul className={buscando ? "space-y-3 opacity-60" : "space-y-3"}>
            {respuesta.resultados.map((t) => (
              <TituloResultado key={t.id} titulo={t} />
            ))}
          </ul>
        )}

        {respuesta && respuesta.paginas > 1 && (
          <nav aria-label="Páginas" className="flex items-center justify-between pt-2">
            <Button variant="outline" size="sm" disabled={pagina <= 1}
                    onClick={() => cambiar({ pagina: String(pagina - 1) })}>
              <ChevronLeft className="mr-1 h-4 w-4" /> Anterior
            </Button>
            <span className="text-sm tabular-nums text-muted-foreground">
              Página {pagina} de {respuesta.paginas}
            </span>
            <Button variant="outline" size="sm" disabled={pagina >= respuesta.paginas}
                    onClick={() => cambiar({ pagina: String(pagina + 1) })}>
              Siguiente <ChevronRight className="ml-1 h-4 w-4" />
            </Button>
          </nav>
        )}
      </section>
    </div>
  )
}
