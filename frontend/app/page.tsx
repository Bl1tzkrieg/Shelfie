"use client"

import { PaginaPublica } from "@/components/layout/pagina-publica"
import { EnConstruccion } from "@/components/lite/en-construccion"

/** Buscar: la pantalla pública del catálogo. Se ve sin iniciar sesión. */
export default function BuscarPage() {
  return (
    <PaginaPublica>
      <h1 className="mb-6 text-2xl font-semibold text-foreground">Buscar en el catálogo</h1>
      <EnConstruccion />
    </PaginaPublica>
  )
}
