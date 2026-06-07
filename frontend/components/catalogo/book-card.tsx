import Link from "next/link"
import { BookOpen, Calendar, User, MapPin } from "lucide-react"
import { cn } from "@/lib/utils"
import { Button } from "@/components/ui/button"

export interface Book {
  id: string
  title: string
  author: string
  year: number
  category: string
  type: string
  isbn: string
  location: string
  copies: number
  available: number
  cover?: string
}

interface BookCardProps {
  book: Book
  viewMode: "grid" | "list"
}

export function BookCard({ book, viewMode }: BookCardProps) {
  const isAvailable = book.available > 0

  if (viewMode === "list") {
    return (
      <div className="flex gap-4 rounded-lg border border-border bg-card p-4 transition-colors hover:bg-muted/50">
        {/* Cover */}
        <div className="flex h-24 w-16 flex-shrink-0 items-center justify-center rounded bg-primary/10">
          <BookOpen className="h-8 w-8 text-primary" />
        </div>

        {/* Info */}
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
              <span className="flex items-center gap-1">
                <Calendar className="h-3.5 w-3.5" />
                {book.year}
              </span>
              <span className="flex items-center gap-1">
                <MapPin className="h-3.5 w-3.5" />
                {book.location}
              </span>
            </div>
          </div>
          <div className="mt-2 flex items-center justify-between">
            <div className="flex items-center gap-2">
              <span className={cn(
                "rounded-full px-2 py-0.5 text-xs font-medium",
                isAvailable 
                  ? "bg-primary/10 text-primary" 
                  : "bg-destructive/10 text-destructive"
              )}>
                {isAvailable ? `${book.available} disponibles` : "No disponible"}
              </span>
              <span className="text-xs text-muted-foreground">{book.category}</span>
            </div>
            <Button size="sm" variant={isAvailable ? "default" : "outline"} disabled={!isAvailable}>
              {isAvailable ? "Prestar" : "Reservar"}
            </Button>
          </div>
        </div>
      </div>
    )
  }

  // Grid view
  return (
    <div className="group flex flex-col rounded-lg border border-border bg-card transition-colors hover:bg-muted/50">
      {/* Cover */}
      <div className="flex h-40 items-center justify-center rounded-t-lg bg-primary/5">
        <BookOpen className="h-16 w-16 text-primary/40" />
      </div>

      {/* Info */}
      <div className="flex flex-1 flex-col p-4">
        <Link 
          href={`/catalogo/${book.id}`}
          className="line-clamp-2 font-semibold text-foreground hover:text-primary hover:underline"
        >
          {book.title}
        </Link>
        <p className="mt-1 text-sm text-muted-foreground">{book.author}</p>
        <p className="text-xs text-muted-foreground">{book.year}</p>
        
        <div className="mt-auto pt-4">
          <div className="mb-3 flex items-center justify-between">
            <span className={cn(
              "rounded-full px-2 py-0.5 text-xs font-medium",
              isAvailable 
                ? "bg-primary/10 text-primary" 
                : "bg-destructive/10 text-destructive"
            )}>
              {isAvailable ? `${book.available} disp.` : "No disp."}
            </span>
            <span className="text-xs text-muted-foreground">{book.location}</span>
          </div>
          <Button size="sm" className="w-full" variant={isAvailable ? "default" : "outline"} disabled={!isAvailable}>
            {isAvailable ? "Prestar" : "Reservar"}
          </Button>
        </div>
      </div>
    </div>
  )
}
