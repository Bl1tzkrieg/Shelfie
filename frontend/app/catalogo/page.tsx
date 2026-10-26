"use client"

import { Suspense, useCallback, useEffect, useRef, useState } from "react"
import { usePathname, useRouter, useSearchParams } from "next/navigation"
import { ArrowLeftRight, ChevronDown, ChevronLeft, ChevronRight, FilePlus2, X } from "lucide-react"
import { toast } from "sonner"

import { AppLayout } from "@/components/layout/app-layout"
import { Header } from "@/components/layout/header"
import { BookCard, Book } from "@/components/catalogo/book-card"
import { CatalogFilters } from "@/components/catalogo/catalog-filters"
import { ClaveFaceta, FacetasBusqueda } from "@/components/catalogo/facetas-busqueda"
import { AgregarMaterialDialog } from "@/components/catalogo/agregar-material-dialog"
import { IntercambioMarcDialog } from "@/components/catalogo/intercambio-marc-dialog"
import { useSesion } from "@/components/auth/sesion-provider"
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu"
import {
  AccionEjemplarDialog,
  AccionEjemplar,
} from "@/components/catalogo/accion-ejemplar-dialog"
import { Button } from "@/components/ui/button"
import { apiGet, mensajeDeError } from "@/lib/api"
import type {
  BusquedaCatalogo,
  FacetasCatalogo,
  OrdenBusqueda,
  ResumenPlantilla,
} from "@/lib/types"
import { cn } from "@/lib/utils"

const POR_PAGINA = 24
const ESPERA_AL_ESCRIBIR_MS = 300
const FACETAS: ClaveFaceta[] = ["disponible", "tipo", "materia", "autor", "decada"]
const ORDENES: OrdenBusqueda[] = ["relevancia", "titulo", "ano_desc", "ano_asc"]

export default function CatalogoPage() {
  // useSearchParams exige un límite de Suspense en el App Router.
  return (
    <Suspense fallback={null}>
      <CatalogoContenido />
    </Suspense>
  )
}

/** La URL es el estado de la búsqueda: se puede recargar, volver atrás y compartir. */
function leerUrl(params: URLSearchParams) {
  const orden = params.get("orden")
  const pagina = Number(params.get("pagina"))
  const seleccion: Partial<Record<ClaveFaceta, string>> = {}
  for (const clave of FACETAS) {
    const valor = params.get(clave)
    if (valor) seleccion[clave] = valor
  }
  return {
    q: params.get("q") ?? "",
    orden: ORDENES.find((o) => o === orden) ?? "relevancia",
    pagina: Number.isInteger(pagina) && pagina > 0 ? pagina : 1,
    seleccion,
  }
}

/** Parámetros de /catalog/search a partir de la URL de la página. */
function consultaApi(estado: ReturnType<typeof leerUrl>) {
  const p = new URLSearchParams()
  if (estado.q.trim()) p.set("q", estado.q.trim())
  const { disponible, tipo, materia, autor, decada } = estado.seleccion
  if (disponible) p.set("disponible", disponible === "si" ? "true" : "false")
  if (tipo) p.set("tipo", tipo)
  if (materia) p.set("materia", materia)
  if (autor) p.set("autor", autor)
  if (decada && /^\d+$/.test(decada)) {
    p.set("ano_desde", decada)
    p.set("ano_hasta", String(Number(decada) + 9))
  }
  p.set("orden", estado.orden)
  p.set("pagina", String(estado.pagina))
  p.set("por_pagina", String(POR_PAGINA))
  return p.toString()
}

function etiquetaElegida(facetas: FacetasCatalogo | null, clave: ClaveFaceta, valor: string) {
  const grupo = {
    disponible: facetas?.disponibilidad,
    tipo: facetas?.tipos,
    materia: facetas?.materias,
    autor: facetas?.autores,
    decada: facetas?.decadas,
  }[clave]
  const encontrado = grupo?.find((v) => String(v.valor) === valor)
  if (encontrado?.etiqueta) return encontrado.etiqueta
  if (clave === "disponible") return valor === "si" ? "Con ejemplares libres" : "Sin ejemplares libres"
  if (clave === "decada") return `${valor}–${Number(valor) + 9}`
  return valor
}

function CatalogoContenido() {
  const router = useRouter()
  const pathname = usePathname()
  const searchParams = useSearchParams()
  const clave = searchParams.toString()
  const estado = leerUrl(searchParams)

  const [respuesta, setRespuesta] = useState<BusquedaCatalogo<Book> | null>(null)
  const [buscando, setBuscando] = useState(true)
  const [recarga, setRecarga] = useState(0)
  const [viewMode, setViewMode] = useState<"grid" | "list">("grid")
  const [facetasAbiertas, setFacetasAbiertas] = useState(false)
  const [accion, setAccion] = useState<AccionEjemplar | null>(null)
  const [intercambio, setIntercambio] = useState(false)
  const [plantillas, setPlantillas] = useState<ResumenPlantilla[]>([])
  const { tienePermiso } = useSesion()
  const puedeCatalogar = tienePermiso("catalogo")

  useEffect(() => {
    apiGet<ResumenPlantilla[]>("/catalog/frameworks").then(setPlantillas).catch(() => {})
  }, [])
  const [seleccionado, setSeleccionado] = useState<Book | null>(null)

  // El texto del buscador va un paso adelante de la URL (se escribe más rápido de lo
  // que conviene buscar). Si la URL cambia desde afuera, p. ej. el buscador del
  // encabezado, el campo se pone al día.
  const [texto, setTexto] = useState(estado.q)
  const [qDeUrl, setQDeUrl] = useState(estado.q)
  // Lo último que este campo mandó a la URL: cuando la URL llega con eso, no se toca el campo
  // (el usuario puede haber seguido escribiendo).
  const [qEnviado, setQEnviado] = useState(estado.q)
  if (qDeUrl !== estado.q) {
    setQDeUrl(estado.q)
    if (estado.q !== qEnviado) {
      setQEnviado(estado.q)
      setTexto(estado.q)
    }
  }

  const navegar = useCallback(
    (cambios: Record<string, string | null>, { reiniciarPagina = true } = {}) => {
      // La URL de este momento, no la del render en que se creó la función: el buscador
      // navega 300 ms después de la tecla y en ese tiempo pudo elegirse una faceta u orden.
      const p = new URLSearchParams(
        typeof window !== "undefined" ? window.location.search : searchParams.toString())
      for (const [k, v] of Object.entries(cambios)) {
        if (v === null || v === "") p.delete(k)
        else p.set(k, v)
      }
      if (reiniciarPagina && !("pagina" in cambios)) p.delete("pagina")
      const destino = p.toString()
      router.replace(destino ? `${pathname}?${destino}` : pathname, { scroll: false })
    },
    [pathname, router, searchParams]
  )

  // Escribir en el buscador actualiza la URL tras una pausa.
  const temporizador = useRef<ReturnType<typeof setTimeout> | null>(null)
  function cambiarTexto(valor: string) {
    setTexto(valor)
    if (temporizador.current) clearTimeout(temporizador.current)
    temporizador.current = setTimeout(() => {
      setQEnviado(valor.trim())
      navegar({ q: valor.trim() || null })
    }, ESPERA_AL_ESCRIBIR_MS)
  }
  useEffect(() => () => {
    if (temporizador.current) clearTimeout(temporizador.current)
  }, [])

  // Cada cambio de la URL dispara una búsqueda; la respuesta de una búsqueda vieja se descarta.
  const ultima = useRef(0)
  useEffect(() => {
    const id = ++ultima.current
    const consulta = consultaApi(leerUrl(new URLSearchParams(clave)))
    apiGet<BusquedaCatalogo<Book>>(`/catalog/search?${consulta}`)
      .then((r) => {
        if (id === ultima.current) setRespuesta(r)
      })
      .catch((error) => {
        if (id === ultima.current)
          toast.error("No se pudo buscar en el catálogo", { description: mensajeDeError(error) })
      })
      .finally(() => {
        if (id === ultima.current) setBuscando(false)
      })
    return () => {
      // Marca de "buscando" para la próxima consulta; se apaga cuando responde.
      setBuscando(true)
    }
  }, [clave, recarga])

  function abrirAccion(book: Book, tipo: AccionEjemplar) {
    setSeleccionado(book)
    setAccion(tipo)
  }

  const recargar = () => setRecarga((n) => n + 1)
  function irAPagina(pagina: number) {
    navegar({ pagina: String(pagina) })
    window.scrollTo({ top: 0, behavior: "smooth" })
  }
  const filtrosActivos = Object.keys(estado.seleccion).length
  const hayBusqueda = estado.q.trim() !== "" || filtrosActivos > 0
  // La exportación usa los mismos filtros que la búsqueda, sin orden ni página.
  const filtrosExportacion = (() => {
    if (!hayBusqueda) return ""
    const p = new URLSearchParams(consultaApi(estado))
    for (const k of ["orden", "pagina", "por_pagina"]) p.delete(k)
    return p.toString()
  })()
  const resultados = respuesta?.resultados ?? []
  const facetas = respuesta?.facetas ?? null

  const panelFacetas = facetas && (
    <FacetasBusqueda
      facetas={facetas}
      seleccion={estado.seleccion}
      onElegir={(k, v) => navegar({ [k]: v })}
    />
  )

  return (
    <AppLayout>
      <Header title="Catálogo" description="Explora la colección de materiales bibliográficos" />

      <div className="p-6">
        <div className="mb-6 flex flex-col gap-4 lg:flex-row lg:items-start lg:justify-between">
          <div className="flex-1">
            <CatalogFilters
              texto={texto}
              onTextoChange={cambiarTexto}
              buscando={buscando && respuesta !== null}
              orden={estado.orden}
              onOrdenChange={(o) => navegar({ orden: o === "relevancia" ? null : o })}
              viewMode={viewMode}
              onViewModeChange={setViewMode}
              facetasAbiertas={facetasAbiertas}
              onFacetasToggle={() => setFacetasAbiertas((v) => !v)}
              filtrosActivos={filtrosActivos}
            />
          </div>
          <div className="flex flex-wrap gap-2 sm:shrink-0">
            <Button variant="outline" onClick={() => setIntercambio(true)}>
              <ArrowLeftRight className="mr-2 h-4 w-4" />
              Importar / Exportar
            </Button>
            {puedeCatalogar && (
              <DropdownMenu>
                <DropdownMenuTrigger asChild>
                  <Button variant="outline">
                    <FilePlus2 className="mr-2 h-4 w-4" />
                    Catalogar
                    <ChevronDown className="ml-1 h-4 w-4" />
                  </Button>
                </DropdownMenuTrigger>
                <DropdownMenuContent align="end" className="w-72">
                  <DropdownMenuLabel>Registro MARC completo</DropdownMenuLabel>
                  {plantillas.map((p) => (
                    <DropdownMenuItem key={p.codigo}
                                      onClick={() => router.push(`/catalogo/nuevo?plantilla=${p.codigo}`)}>
                      <div>
                        <p className="font-medium">{p.nombre}</p>
                        <p className="text-xs text-muted-foreground">{p.descripcion}</p>
                      </div>
                    </DropdownMenuItem>
                  ))}
                </DropdownMenuContent>
              </DropdownMenu>
            )}
            {puedeCatalogar && <AgregarMaterialDialog onSuccess={recargar} />}
          </div>
        </div>

        <div className="flex gap-8">
          <aside
            aria-label="Refinar la búsqueda"
            className={cn(
              "w-60 shrink-0",
              facetasAbiertas
                ? "fixed inset-y-0 right-0 z-50 w-72 overflow-y-auto border-l border-border bg-card p-6 shadow-lg lg:static lg:z-auto lg:w-60 lg:border-0 lg:bg-transparent lg:p-0 lg:shadow-none"
                : "hidden lg:block"
            )}
          >
            {facetasAbiertas && (
              <div className="mb-4 flex items-center justify-between lg:hidden">
                <span className="font-medium">Filtros</span>
                <Button variant="ghost" size="icon" aria-label="Cerrar filtros"
                        onClick={() => setFacetasAbiertas(false)}>
                  <X className="h-4 w-4" />
                </Button>
              </div>
            )}
            {panelFacetas}
          </aside>

          <div className="min-w-0 flex-1">
            <div className="mb-4 flex flex-wrap items-center gap-2 text-sm text-muted-foreground"
                 aria-live="polite">
              {respuesta && (
                <span>
                  <span className="font-medium text-foreground">{respuesta.total}</span>{" "}
                  {respuesta.total === 1 ? "título" : "títulos"}
                  {estado.q.trim() && (
                    <>
                      {" "}para «<span className="text-foreground">{estado.q.trim()}</span>»
                    </>
                  )}
                </span>
              )}
              {Object.entries(estado.seleccion).map(([k, v]) => (
                <button
                  key={k}
                  type="button"
                  onClick={() => navegar({ [k]: null })}
                  className="inline-flex items-center gap-1 rounded-full bg-primary/10 py-0.5 pl-2.5 pr-1.5 text-xs font-medium text-primary hover:bg-primary/15"
                  aria-label={`Quitar el filtro ${etiquetaElegida(facetas, k as ClaveFaceta, v)}`}
                >
                  {etiquetaElegida(facetas, k as ClaveFaceta, v)}
                  <X className="h-3 w-3" />
                </button>
              ))}
              {hayBusqueda && (
                <button
                  type="button"
                  className="text-xs text-primary hover:underline"
                  onClick={() => {
                    setTexto("")
                    setQEnviado("")
                    router.replace(pathname, { scroll: false })
                  }}
                >
                  Limpiar todo
                </button>
              )}
            </div>

            {respuesta === null ? (
              <div className="rounded-lg border bg-card shadow-papel py-12 text-center text-muted-foreground">
                Cargando catálogo…
              </div>
            ) : resultados.length === 0 ? (
              <div className="rounded-lg border border-dashed bg-card py-16 text-center text-muted-foreground">
                {hayBusqueda ? (
                  <>
                    <p className="mb-1 text-lg font-medium">Sin resultados</p>
                    <p className="text-sm">
                      Prueba con menos palabras, otra forma de escribirlas, o quita algún filtro.
                    </p>
                  </>
                ) : (
                  <>
                    <p className="mb-1 text-lg font-medium">El catálogo está vacío</p>
                    <p className="text-sm">Usa “Agregar Material” para catalogar el primer título.</p>
                  </>
                )}
              </div>
            ) : (
              <div className={cn("transition-opacity", buscando && "opacity-60")}>
                {viewMode === "grid" ? (
                  <div className="grid grid-cols-1 gap-6 sm:grid-cols-2 md:grid-cols-3 xl:grid-cols-4">
                    {resultados.map((book) => (
                      <BookCard
                        key={book.id}
                        book={book}
                        viewMode="grid"
                        onPrestar={(b) => abrirAccion(b, "prestar")}
                        onReservar={(b) => abrirAccion(b, "reservar")}
                      />
                    ))}
                  </div>
                ) : (
                  <div className="flex flex-col gap-3">
                    {resultados.map((book) => (
                      <BookCard
                        key={book.id}
                        book={book}
                        viewMode="list"
                        onPrestar={(b) => abrirAccion(b, "prestar")}
                        onReservar={(b) => abrirAccion(b, "reservar")}
                      />
                    ))}
                  </div>
                )}

                {respuesta.paginas > 1 && (
                  <nav aria-label="Páginas de resultados"
                       className="mt-8 flex items-center justify-center gap-3">
                    <Button
                      variant="outline"
                      size="sm"
                      disabled={respuesta.pagina <= 1}
                      onClick={() => irAPagina(respuesta.pagina - 1)}
                    >
                      <ChevronLeft className="mr-1 h-4 w-4" />
                      Anterior
                    </Button>
                    <span className="text-sm tabular-nums text-muted-foreground">
                      Página {respuesta.pagina} de {respuesta.paginas}
                    </span>
                    <Button
                      variant="outline"
                      size="sm"
                      disabled={respuesta.pagina >= respuesta.paginas}
                      onClick={() => irAPagina(respuesta.pagina + 1)}
                    >
                      Siguiente
                      <ChevronRight className="ml-1 h-4 w-4" />
                    </Button>
                  </nav>
                )}
              </div>
            )}
          </div>
        </div>
      </div>

      <IntercambioMarcDialog
        open={intercambio}
        onOpenChange={setIntercambio}
        filtrosBusqueda={filtrosExportacion}
        totalBusqueda={respuesta?.total ?? null}
        puedeImportar={puedeCatalogar}
        onImportado={recargar}
      />

      <AccionEjemplarDialog
        accion={accion}
        titulo={seleccionado?.title ?? ""}
        biblioId={seleccionado?.id ?? ""}
        codigoBarras={seleccionado?.availableBarcode}
        onClose={() => setAccion(null)}
        onSuccess={recargar}
      />
    </AppLayout>
  )
}
