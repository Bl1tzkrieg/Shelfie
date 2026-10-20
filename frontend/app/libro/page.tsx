"use client"

import { Suspense } from "react"
import { useSearchParams } from "next/navigation"

import { PaginaPublica } from "@/components/layout/pagina-publica"
import { EnConstruccion } from "@/components/lite/en-construccion"

/** Ficha pública de un libro: /libro?id=. Se ve sin iniciar sesión. */
export default function LibroPage() {
  return (
    <PaginaPublica>
      <h1 className="mb-6 text-2xl font-semibold text-foreground">Ficha del libro</h1>
      <Suspense fallback={null}>
        <Ficha />
      </Suspense>
    </PaginaPublica>
  )
}

function Ficha() {
  const id = useSearchParams().get("id")
  return <EnConstruccion>{id && <p className="text-xs">Libro n.º {id}</p>}</EnConstruccion>
}
