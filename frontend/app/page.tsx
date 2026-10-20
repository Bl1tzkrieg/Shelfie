"use client"

import { Suspense } from "react"

import { PaginaPublica } from "@/components/layout/pagina-publica"
import { Buscador } from "@/components/lite/buscador"

/** Buscar: la pantalla pública del catálogo. Se ve sin iniciar sesión. */
export default function BuscarPage() {
  return (
    <PaginaPublica>
      <h1 className="sr-only">Buscar en el catálogo</h1>
      <Suspense fallback={null}>
        <Buscador />
      </Suspense>
    </PaginaPublica>
  )
}
