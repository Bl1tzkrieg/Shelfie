"use client"

import { useCallback, useEffect, useState } from "react"
import { useParams, useRouter } from "next/navigation"
import { ArrowLeft, BookOpen, User, Calendar, MapPin, Tag, Hash } from "lucide-react"
import { toast } from "sonner"

import { AppLayout } from "@/components/layout/app-layout"
import { Header } from "@/components/layout/header"
import { Button } from "@/components/ui/button"
import {
  AccionEjemplarDialog,
  AccionEjemplar,
} from "@/components/catalogo/accion-ejemplar-dialog"
import { apiGet, ApiError, mensajeDeError } from "@/lib/api"
import { cn } from "@/lib/utils"
import type { Book } from "@/components/catalogo/book-card"
import type { Ejemplar } from "@/lib/types"

const estadoClases: Record<string, string> = {
  Disponible: "bg-primary/10 text-primary",
  Prestado: "bg-destructive/10 text-destructive",
  Reservado: "bg-accent/20 text-accent-foreground",
}

export default function FichaCatalogoPage() {
  const params = useParams<{ id: string }>()
  const router = useRouter()
  const biblioId = params.id

  const [book, setBook] = useState<Book | null>(null)
  const [ejemplares, setEjemplares] = useState<Ejemplar[]>([])
  const [isLoading, setIsLoading] = useState(true)
  const [noEncontrado, setNoEncontrado] = useState(false)
  const [accion, setAccion] = useState<AccionEjemplar | null>(null)

  const cargar = useCallback(async () => {
    try {
      const [b, e] = await Promise.all([
        apiGet<Book>(`/catalog/items/${biblioId}`),
        apiGet<Ejemplar[]>(`/catalog/items/${biblioId}/ejemplares`),
      ])
      setBook(b)
      setEjemplares(e)
    } catch (error) {
      if (error instanceof ApiError && error.status === 404) {
        setNoEncontrado(true)
      } else {
        toast.error("No se pudo cargar la ficha", { description: mensajeDeError(error) })
      }
    } finally {
      setIsLoading(false)
    }
  }, [biblioId])

  useEffect(() => {
    cargar()
  }, [cargar])

  if (isLoading) {
    return (
      <AppLayout>
        <Header title="Ficha bibliográfica" />
        <div className="p-6">
          <div className="rounded-lg border bg-card py-16 text-center text-muted-foreground">
            Cargando ficha...
          </div>
        </div>
      </AppLayout>
    )
  }

  if (noEncontrado || !book) {
    return (
      <AppLayout>
        <Header title="Ficha bibliográfica" />
        <div className="p-6">
          <div className="rounded-lg border border-dashed bg-card py-16 text-center">
            <p className="text-lg font-medium text-foreground">Título no encontrado</p>
            <p className="mb-4 text-sm text-muted-foreground">
              No existe ningún registro con el identificador {biblioId}.
            </p>
            <Button variant="outline" onClick={() => router.push("/catalogo")}>
              <ArrowLeft className="mr-2 h-4 w-4" />
              Volver al catálogo
            </Button>
          </div>
        </div>
      </AppLayout>
    )
  }

  const puedePrestar = book.available > 0 && Boolean(book.availableBarcode)

  return (
    <AppLayout>
      <Header title="Ficha bibliográfica" description={book.title} />

      <div className="p-6">
        <Button variant="ghost" size="sm" className="mb-4" onClick={() => router.push("/catalogo")}>
          <ArrowLeft className="mr-2 h-4 w-4" />
          Volver al catálogo
        </Button>

        <div className="mb-6 rounded-lg border border-border bg-card p-6">
          <div className="flex flex-col gap-6 sm:flex-row">
            <div className="flex h-40 w-32 shrink-0 items-center justify-center rounded-lg bg-primary/5">
              <BookOpen className="h-16 w-16 text-primary/40" />
            </div>

            <div className="flex-1">
              <h2 className="text-2xl font-semibold text-foreground">{book.title}</h2>

              <div className="mt-3 grid gap-2 text-sm text-muted-foreground sm:grid-cols-2">
                <span className="flex items-center gap-2">
                  <User className="h-4 w-4" />
                  {book.author}
                </span>
                {book.year && (
                  <span className="flex items-center gap-2">
                    <Calendar className="h-4 w-4" />
                    {book.year}
                  </span>
                )}
                <span className="flex items-center gap-2">
                  <Tag className="h-4 w-4" />
                  {book.category}
                </span>
                <span className="flex items-center gap-2">
                  <Hash className="h-4 w-4" />
                  ISBN {book.isbn}
                </span>
                {book.location && (
                  <span className="flex items-center gap-2">
                    <MapPin className="h-4 w-4" />
                    {book.location}
                  </span>
                )}
                <span className="flex items-center gap-2">
                  <BookOpen className="h-4 w-4" />
                  {book.type}
                </span>
              </div>

              <div className="mt-5 flex items-center gap-3">
                <span
                  className={cn(
                    "rounded-full px-3 py-1 text-sm font-medium",
                    book.available > 0
                      ? "bg-primary/10 text-primary"
                      : "bg-destructive/10 text-destructive"
                  )}
                >
                  {book.available} de {book.copies} ejemplar(es) disponible(s)
                </span>
                <Button
                  variant={puedePrestar ? "default" : "outline"}
                  onClick={() => setAccion(puedePrestar ? "prestar" : "reservar")}
                >
                  {puedePrestar ? "Prestar" : "Reservar"}
                </Button>
              </div>
            </div>
          </div>
        </div>

        <div className="rounded-lg border border-border bg-card">
          <div className="border-b border-border px-6 py-4">
            <h3 className="font-semibold text-foreground">Ejemplares</h3>
            <p className="text-sm text-muted-foreground">
              Estado individual de cada copia física
            </p>
          </div>

          <div className="overflow-x-auto">
            <table className="w-full">
              <thead>
                <tr className="border-b border-border bg-muted/50">
                  <th className="px-4 py-3 text-left text-sm font-medium text-muted-foreground">Código de barras</th>
                  <th className="px-4 py-3 text-left text-sm font-medium text-muted-foreground">Signatura</th>
                  <th className="px-4 py-3 text-left text-sm font-medium text-muted-foreground">Estado</th>
                  <th className="px-4 py-3 text-left text-sm font-medium text-muted-foreground">Prestado a</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-border">
                {ejemplares.map((e) => (
                  <tr key={e.id} className="hover:bg-muted/30">
                    <td className="px-4 py-4 font-medium text-foreground">{e.barcode}</td>
                    <td className="px-4 py-4 text-sm text-muted-foreground">
                      {e.location || "—"}
                    </td>
                    <td className="px-4 py-4">
                      <span
                        className={cn(
                          "inline-flex rounded-full px-2.5 py-1 text-xs font-medium",
                          estadoClases[e.status] || "bg-muted text-muted-foreground"
                        )}
                      >
                        {e.status}
                      </span>
                    </td>
                    <td className="px-4 py-4 text-sm">
                      {e.borrowedBy ? (
                        <div>
                          <p className="text-foreground">{e.borrowedBy}</p>
                          {e.dueDate && (
                            <p className="text-xs text-muted-foreground">Vence: {e.dueDate}</p>
                          )}
                        </div>
                      ) : (
                        <span className="text-muted-foreground">—</span>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      </div>

      <AccionEjemplarDialog
        accion={accion}
        titulo={book.title}
        biblioId={book.id}
        codigoBarras={book.availableBarcode}
        onClose={() => setAccion(null)}
        onSuccess={cargar}
      />
    </AppLayout>
  )
}
