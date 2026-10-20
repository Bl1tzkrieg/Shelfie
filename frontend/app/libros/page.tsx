"use client"

import { AppLayout } from "@/components/layout/app-layout"
import { Header } from "@/components/layout/header"
import { EnConstruccion } from "@/components/lite/en-construccion"

/** Los libros en el orden del estante, con importación y exportación MARC. */
export default function LibrosPage() {
  return (
    <AppLayout permiso="catalogo">
      <Header title="Libros" description="El catálogo en el orden del estante" />
      <div className="p-4 sm:p-6">
        <EnConstruccion />
      </div>
    </AppLayout>
  )
}
