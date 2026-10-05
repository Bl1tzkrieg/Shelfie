"use client"

import { Suspense, useCallback, useEffect, useMemo, useState } from "react"
import { useSearchParams } from "next/navigation"
import { toast } from "sonner"

import { AppLayout } from "@/components/layout/app-layout"
import { Header } from "@/components/layout/header"
import { BookCard, Book } from "@/components/catalogo/book-card"
import {
  CatalogFilters,
  CatalogFilterState,
  FILTROS_VACIOS,
  RANGOS_ANO,
} from "@/components/catalogo/catalog-filters"
import { AgregarMaterialDialog } from "@/components/catalogo/agregar-material-dialog"
import {
  AccionEjemplarDialog,
  AccionEjemplar,
} from "@/components/catalogo/accion-ejemplar-dialog"
import { apiGet, mensajeDeError } from "@/lib/api"

export default function CatalogoPage() {
  // useSearchParams exige un límite de Suspense en el App Router.
  return (
    <Suspense fallback={null}>
      <CatalogoContenido />
    </Suspense>
  )
}

function CatalogoContenido() {
  const searchParams = useSearchParams()
  const [books, setBooks] = useState<Book[]>([])
  const [isLoading, setIsLoading] = useState(true)
  const [viewMode, setViewMode] = useState<"grid" | "list">("grid")
  // El buscador global del header navega a /catalogo?q=...; se toma como valor inicial.
  const [searchQuery, setSearchQuery] = useState(() => searchParams.get("q") ?? "")
  const [filtros, setFiltros] = useState<CatalogFilterState>(FILTROS_VACIOS)

  const [accion, setAccion] = useState<AccionEjemplar | null>(null)
  const [seleccionado, setSeleccionado] = useState<Book | null>(null)

  const cargarCatalogo = useCallback(async () => {
    try {
      const data = await apiGet<Book[]>("/catalog/items")
      setBooks(data)
    } catch (error) {
      toast.error("No se pudo cargar el catálogo", { description: mensajeDeError(error) })
      setBooks([])
    } finally {
      setIsLoading(false)
    }
  }, [])

  useEffect(() => {
    cargarCatalogo()
  }, [cargarCatalogo])

  // Las opciones de los selectores salen del catálogo real, no de una lista fija.
  const categorias = useMemo(
    () => Array.from(new Set(books.map((b) => b.category).filter(Boolean))).sort(),
    [books]
  )
  const tipos = useMemo(
    () => Array.from(new Set(books.map((b) => b.type).filter(Boolean))).sort(),
    [books]
  )

  const filteredBooks = useMemo(() => {
    const query = searchQuery.trim().toLowerCase()

    return books.filter((book) => {
      if (query) {
        const coincide = [book.title, book.author, book.isbn, book.category].some((campo) =>
          campo?.toLowerCase().includes(query)
        )
        if (!coincide) return false
      }

      if (filtros.categoria !== "all" && book.category !== filtros.categoria) return false
      if (filtros.tipo !== "all" && book.type !== filtros.tipo) return false

      if (filtros.disponibilidad === "available" && book.available === 0) return false
      if (filtros.disponibilidad === "borrowed" && book.available > 0) return false

      if (filtros.ano !== "all") {
        const rango = RANGOS_ANO[filtros.ano]
        if (!rango) return true
        if (!book.year) return false
        const [desde, hasta] = rango
        if (book.year < desde || book.year > hasta) return false
      }

      return true
    })
  }, [books, searchQuery, filtros])

  function abrirAccion(book: Book, tipo: AccionEjemplar) {
    setSeleccionado(book)
    setAccion(tipo)
  }

  const hayFiltrosActivos =
    searchQuery.trim() !== "" || Object.values(filtros).some((v) => v !== "all")

  return (
    <AppLayout>
      <Header title="Catálogo" description="Explora la colección de materiales bibliográficos" />

      <div className="p-6">
        <div className="mb-6 flex flex-col gap-4 lg:flex-row lg:items-start lg:justify-between">
          <div className="flex-1">
            <CatalogFilters
              viewMode={viewMode}
              onViewModeChange={setViewMode}
              searchQuery={searchQuery}
              onSearchChange={setSearchQuery}
              filtros={filtros}
              onFiltrosChange={setFiltros}
              categorias={categorias}
              tipos={tipos}
            />
          </div>
          <AgregarMaterialDialog onSuccess={cargarCatalogo} />
        </div>

        <div className="mb-4 text-sm text-muted-foreground">
          Mostrando <span className="font-medium text-foreground">{filteredBooks.length}</span> de{" "}
          <span className="font-medium text-foreground">{books.length}</span> títulos
        </div>

        {isLoading ? (
          <div className="rounded-lg border bg-card py-12 text-center text-muted-foreground">
            Cargando catálogo desde la base de datos...
          </div>
        ) : books.length === 0 ? (
          <div className="rounded-lg border border-dashed bg-card py-16 text-center text-muted-foreground">
            <p className="mb-1 text-lg font-medium">El catálogo está vacío</p>
            <p className="text-sm">Usa “Agregar Material” para catalogar el primer título.</p>
          </div>
        ) : filteredBooks.length === 0 ? (
          <div className="rounded-lg border border-dashed bg-card py-16 text-center text-muted-foreground">
            <p className="mb-1 text-lg font-medium">Sin resultados</p>
            <p className="text-sm">
              {hayFiltrosActivos
                ? "Prueba con otros términos o limpia los filtros."
                : "No hay títulos que mostrar."}
            </p>
          </div>
        ) : viewMode === "grid" ? (
          <div className="grid grid-cols-1 gap-6 sm:grid-cols-2 md:grid-cols-3 lg:grid-cols-4 xl:grid-cols-5">
            {filteredBooks.map((book) => (
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
            {filteredBooks.map((book) => (
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
      </div>

      <AccionEjemplarDialog
        accion={accion}
        titulo={seleccionado?.title ?? ""}
        biblioId={seleccionado?.id ?? ""}
        codigoBarras={seleccionado?.availableBarcode}
        onClose={() => setAccion(null)}
        onSuccess={cargarCatalogo}
      />
    </AppLayout>
  )
}
