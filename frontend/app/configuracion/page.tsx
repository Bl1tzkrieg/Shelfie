"use client"

import { AppLayout } from "@/components/layout/app-layout"
import { Header } from "@/components/layout/header"
import { EnConstruccion } from "@/components/lite/en-construccion"

/** Datos de la biblioteca, exportación a Koha y respaldo. */
export default function ConfiguracionPage() {
  return (
    <AppLayout permiso="superbibliotecario">
      <Header title="Configuración" description="La biblioteca, la exportación a Koha y el respaldo" />
      <div className="p-4 sm:p-6">
        <EnConstruccion />
      </div>
    </AppLayout>
  )
}
