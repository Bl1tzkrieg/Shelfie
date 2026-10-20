"use client"

import { Suspense } from "react"
import { useSearchParams } from "next/navigation"

import { PaginaPublica } from "@/components/layout/pagina-publica"
import { Ficha } from "@/components/lite/ficha"

/** Ficha pública de un libro: /libro?id=. Se ve sin iniciar sesión. */
export default function LibroPage() {
  return (
    <PaginaPublica>
      <Suspense fallback={null}>
        <FichaDeLaUrl />
      </Suspense>
    </PaginaPublica>
  )
}

function FichaDeLaUrl() {
  return <Ficha id={useSearchParams().get("id")} />
}
