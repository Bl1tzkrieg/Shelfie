"use client"

import { useState } from "react"
import { AppLayout } from "@/components/layout/app-layout"
import { Header } from "@/components/layout/header"
import { CatalogFilters } from "@/components/catalogo/catalog-filters"
import { BookCard, Book } from "@/components/catalogo/book-card"
import { Button } from "@/components/ui/button"
import { Plus } from "lucide-react"
import Link from "next/link"

const books: Book[] = [
  {
    id: "1",
    title: "Fisiología Vegetal",
    author: "Lincoln Taiz & Eduardo Zeiger",
    year: 2022,
    category: "Fitotecnia",
    type: "Libro",
    isbn: "978-84-9035-123-4",
    location: "A-101",
    copies: 5,
    available: 3,
  },
  {
    id: "2",
    title: "Introducción a la Ciencia del Suelo",
    author: "Roberto Núñez Escobar",
    year: 2021,
    category: "Ciencias del Suelo",
    type: "Libro",
    isbn: "978-607-32-4567-8",
    location: "B-203",
    copies: 3,
    available: 0,
  },
  {
    id: "3",
    title: "Manejo Integrado de Plagas",
    author: "Marcos Kogan",
    year: 2020,
    category: "Entomología",
    type: "Libro",
    isbn: "978-1-4020-8991-3",
    location: "C-105",
    copies: 4,
    available: 2,
  },
  {
    id: "4",
    title: "Sistemas de Riego: Diseño y Manejo",
    author: "Fernando Pizarro Cabello",
    year: 2019,
    category: "Agronomía General",
    type: "Libro",
    isbn: "978-84-7114-456-7",
    location: "A-205",
    copies: 2,
    available: 1,
  },
  {
    id: "5",
    title: "Nutrición Animal Aplicada",
    author: "Peter McDonald",
    year: 2023,
    category: "Zootecnia",
    type: "Libro",
    isbn: "978-84-200-1234-5",
    location: "D-102",
    copies: 6,
    available: 4,
  },
  {
    id: "6",
    title: "Genética Vegetal",
    author: "María Teresa Martínez",
    year: 2021,
    category: "Fitotecnia",
    type: "Libro",
    isbn: "978-84-9035-789-1",
    location: "A-103",
    copies: 3,
    available: 3,
  },
  {
    id: "7",
    title: "Botánica Sistemática: Fundamentos",
    author: "Walter S. Judd",
    year: 2018,
    category: "Botánica",
    type: "Libro",
    isbn: "978-0-87893-407-2",
    location: "B-101",
    copies: 4,
    available: 2,
  },
  {
    id: "8",
    title: "Economía Agrícola",
    author: "Carlos Alberto Pérez",
    year: 2022,
    category: "Agronomía General",
    type: "Libro",
    isbn: "978-607-15-0987-6",
    location: "E-201",
    copies: 5,
    available: 5,
  },
]

export default function CatalogoPage() {
  const [viewMode, setViewMode] = useState<"grid" | "list">("grid")

  return (
    <AppLayout>
      <Header 
        title="Catálogo" 
        description="Explora la colección de materiales bibliográficos"
      />
      
      <div className="p-6">
        {/* Action Bar */}
        <div className="mb-6 flex items-center justify-between">
          <div>
            <p className="text-sm text-muted-foreground">
              Mostrando <span className="font-medium text-foreground">8</span> de{" "}
              <span className="font-medium text-foreground">12,847</span> resultados
            </p>
          </div>
          <Link href="/catalogo/nuevo">
            <Button>
              <Plus className="mr-2 h-4 w-4" />
              Agregar Material
            </Button>
          </Link>
        </div>

        {/* Filters */}
        <CatalogFilters viewMode={viewMode} onViewModeChange={setViewMode} />

        {/* Results */}
        <div className={
          viewMode === "grid" 
            ? "mt-6 grid gap-4 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4"
            : "mt-6 space-y-3"
        }>
          {books.map((book) => (
            <BookCard key={book.id} book={book} viewMode={viewMode} />
          ))}
        </div>

        {/* Pagination */}
        <div className="mt-8 flex items-center justify-center gap-2">
          <Button variant="outline" size="sm" disabled>
            Anterior
          </Button>
          <div className="flex items-center gap-1">
            <Button variant="default" size="sm">1</Button>
            <Button variant="outline" size="sm">2</Button>
            <Button variant="outline" size="sm">3</Button>
            <span className="px-2 text-muted-foreground">...</span>
            <Button variant="outline" size="sm">125</Button>
          </div>
          <Button variant="outline" size="sm">
            Siguiente
          </Button>
        </div>
      </div>
    </AppLayout>
  )
}
