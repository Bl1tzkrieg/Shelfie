"use client"

import Link from "next/link"
import { BookOpen, Calendar, User, MapPin } from "lucide-react"

import { cn } from "@/lib/utils"
import { Button } from "@/components/ui/button"

export interface Book {
  id: string
  title: string
  author: string
  year: number | null
  category: string
  type: string
  isbn: string
  location: string | null
  copies: number
  available: number
  cover?: string
  // Código de barras del primer ejemplar libre; es lo que consume /circulation/checkout.
  availableBarcode?: string | null
}

interface BookCardProps {
  book: Book
  viewMode: "grid" | "list"
  onPrestar?: (book: Book) => void
  onReservar?: (book: Book) => void
}

export function BookCard({ book, viewMode, onPrestar, onReservar }: BookCardProps) {
  const isAvailable = book.available > 0

  // Prestar exige un ejemplar libre con código de barras; si no lo hay, se reserva.
  const puedePrestar = isAvailable && Boolean(book.availableBarcode)

  function handleAccion() {
    if (puedePrestar) onPrestar?.(book)
    else onReservar?.(book)
  }

  const etiquetaDisponibilidad = isAvailable
    ? `${book.available} de ${book.copies} disp.`
    : "No disponible"

  if (viewMode === "list") {
    return (
      <div className="flex gap-4 rounded-lg border border-border bg-card p-4 transition-colors hover:bg-muted/50">
        <div className="flex h-24 w-16 flex-shrink-0 items-center justify-center rounded bg-primary/10">
          <BookOpen className="h-8 w-8 text-primary" />
        </div>

        <div className="flex flex-1 flex-col justify-between">
          <div>
            <Link
              href={`/catalogo/${book.id}`}
              className="font-semibold text-foreground hover:text-primary hover:underline"
            >
              {book.title}
            </Link>
            <div className="mt-1 flex flex-wrap gap-x-4 gap-y-1 text-sm text-muted-foreground">
              <span className="flex items-center gap-1">
                <User className="h-3.5 w-3.5" />
                {book.author}
              </span>
              {book.year && (
                <span className="flex items-center gap-1">
                  <Calendar className="h-3.5 w-3.5" />
                  {book.year}
                </span>
              )}
              {book.location && (
                <span className="flex items-center gap-1">
                  <MapPin className="h-3.5 w-3.5" />
                  {book.location}
                </span>
              )}
            </div>
          </div>
          <div className="mt-2 flex items-center justify-between">
            <div className="flex items-center gap-2">
              <span
                className={cn(
                  "rounded-full px-2 py-0.5 text-xs font-medium",
                  isAvailable ? "bg-primary/10 text-primary" : "bg-destructive/10 text-destructive"
                )}
              >
                {etiquetaDisponibilidad}
              </span>
              <span className="text-xs text-muted-foreground">{book.category}</span>
            </div>
            <Button
              size="sm"
              variant={puedePrestar ? "default" : "outline"}
              onClick={handleAccion}
            >
              {puedePrestar ? "Prestar" : "Reservar"}
            </Button>
          </div>
        </div>
      </div>
    )
  }

  return (
    <div className="group flex flex-col rounded-lg border border-border bg-card transition-colors hover:bg-muted/50">
      <div className="flex h-40 items-center justify-center rounded-t-lg bg-primary/5">
        <BookOpen className="h-16 w-16 text-primary/40" />
      </div>

      <div className="flex flex-1 flex-col p-4">
        <Link
          href={`/catalogo/${book.id}`}
          className="line-clamp-2 font-semibold text-foreground hover:text-primary hover:underline"
        >
          {book.title}
        </Link>
        <p className="mt-1 text-sm text-muted-foreground">{book.author}</p>
        {book.year && <p className="text-xs text-muted-foreground">{book.year}</p>}

        <div className="mt-auto pt-4">
          <div className="mb-3 flex items-center justify-between gap-2">
            <span
              className={cn(
                "rounded-full px-2 py-0.5 text-xs font-medium",
                isAvailable ? "bg-primary/10 text-primary" : "bg-destructive/10 text-destructive"
              )}
            >
              {etiquetaDisponibilidad}
            </span>
            {book.location && (
              <span className="truncate text-xs text-muted-foreground">{book.location}</span>
            )}
          </div>
          <Button
            size="sm"
            className="w-full"
            variant={puedePrestar ? "default" : "outline"}
            onClick={handleAccion}
          >
            {puedePrestar ? "Prestar" : "Reservar"}
          </Button>
        </div>
      </div>
    </div>
  )
}
