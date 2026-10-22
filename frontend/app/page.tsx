"use client"

import { Suspense } from "react"

import { PaginaPublica } from "@/components/layout/pagina-publica"
import { Buscador } from "@/components/lite/buscador"

/** Buscar: la pantalla pública del catálogo. Se ve sin iniciar sesión. El h1 está en el Buscador. */
export default function BuscarPage() {
  return (
    <PaginaPublica>
      <Suspense fallback={null}>
        <Buscador />
      </Suspense>
    </PaginaPublica>
  )
}
