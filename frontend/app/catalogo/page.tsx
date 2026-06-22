"use client"

import { useState, useEffect } from "react"
import { AppLayout } from "@/components/layout/app-layout"
import { Header } from "@/components/layout/header"
import { BookCard } from "@/components/catalogo/book-card"
import { Button } from "@/components/ui/button"
import { Plus, SlidersHorizontal } from "lucide-react"

interface Book {
  id: string
  title: string
  author: string
  isbn: string
  status: "disponible" | "prestado" | "reservado"
  coverImage: string
}

export default function CatalogoPage() {
  const [books, setBooks] = useState<Book[]>([])
  const [isLoading, setIsLoading] = useState(true)

  useEffect(() => {
    async function fetchCatalog() {
      try {
        const response = await fetch(`${process.env.NEXT_PUBLIC_API_URL}/catalog/items`)
        if (response.ok) {
          const data = await response.json()
          setBooks(data)
        } else {
          setBooks([])
        }
      } catch (error) {
        print("Error en el fetch del catálogo:", error)
        setBooks([])
      } finally {
        setIsLoading(false)
      }
    }
    fetchCatalog()
  }, [])

  return (
    <AppLayout>
      <Header 
        title="Catálogo" 
        description="Explora la colección de materiales bibliográficos"
      />
      
      <div className="p-6">
        {/* Contador Real */}
        <div className="mb-4 text-sm text-muted-foreground">
          Mostrando <span className="font-medium">{books.length}</span> resultados reales
        </div>

        {/* Barra de herramientas simplificada temporalmente para evitar mocks */}
        <div className="flex flex-col sm:flex-row justify-between items-start sm:items-center mb-6 gap-4">
          <div className="relative w-full max-w-md">
            <input 
              type="text" 
              placeholder="Buscar por título, autor, ISBN..." 
              className="w-full px-4 py-2 border rounded-lg bg-background text-sm"
              disabled
            />
          </div>
          
          <div className="flex gap-2 w-full sm:w-auto justify-end">
            <Button variant="outline" size="sm">
              <SlidersHorizontal className="mr-2 h-4 w-4" />
              Filtros
            </Button>
            <Button size="sm" className="bg-emerald-700 hover:bg-emerald-800 text-white">
              <Plus className="mr-2 h-4 w-4" />
              Agregar Material
            </Button>
          </div>
        </div>

        {/* Renderizado Condicional Estricto */}
        {isLoading ? (
          <div className="text-center py-12 bg-card border rounded-lg text-muted-foreground">
            Cargando catálogo desde la base de datos...
          </div>
        ) : books.length === 0 ? (
          <div className="text-center py-16 bg-card border rounded-lg border-dashed text-muted-foreground">
            <p className="text-lg font-medium mb-1">El catálogo está vacío en la base de datos</p>
            <p className="text-sm">Si ya corriste el script, verifica que el Backend esté encendido.</p>
          </div>
        ) : (
          <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-3 lg:grid-cols-4 xl:grid-cols-5 gap-6">
            {books.map((book) => (
              <BookCard key={book.id} book={book} />
            ))}
          </div>
        )}
      </div>
    </AppLayout>
  )
}