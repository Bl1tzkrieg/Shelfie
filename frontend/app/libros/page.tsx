"use client"

import { Suspense, useState } from "react"

import { AppLayout } from "@/components/layout/app-layout"
import { Header } from "@/components/layout/header"
import { AccionesLibros, ListaLibros } from "@/components/lite/lista-libros"
import { IntercambioMarcDialog } from "@/components/marc/intercambio-marc-dialog"

/** Los libros en el orden del estante, con importación y exportación MARC. */
export default function LibrosPage() {
  const [importando, setImportando] = useState(false)
  // Tras una importación la lista se vuelve a pedir.
  const [recarga, setRecarga] = useState(0)

  return (
    <AppLayout permiso="catalogo">
      <Header title="Libros" description="El catálogo en el orden del estante">
        <AccionesLibros onImportar={() => setImportando(true)} />
      </Header>
      <div className="p-4 sm:p-6">
        <Suspense fallback={null}>
          <ListaLibros recarga={recarga} />
        </Suspense>
      </div>
      <IntercambioMarcDialog open={importando} onOpenChange={setImportando} puedeImportar
                             onImportado={() => setRecarga((n) => n + 1)} />
    </AppLayout>
  )
}
