"use client"

import { AppLayout } from "@/components/layout/app-layout"
import { Header } from "@/components/layout/header"
import { Ajustes } from "@/components/lite/ajustes"

/** Datos de la biblioteca, exportación a Koha y respaldo. */
export default function ConfiguracionPage() {
  return (
    <AppLayout permiso="superbibliotecario">
      <Header title="Configuración" description="La biblioteca, la exportación a Koha y el respaldo" />
      <div className="p-4 sm:p-6">
        <Ajustes />
      </div>
    </AppLayout>
  )
}
