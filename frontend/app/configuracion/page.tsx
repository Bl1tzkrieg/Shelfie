"use client"

import { AppLayout } from "@/components/layout/app-layout"
import { Header } from "@/components/layout/header"
import { Ajustes } from "@/components/lite/ajustes"

/** Datos de la biblioteca (nombre y códigos de la exportación MARC) y respaldo. */
export default function ConfiguracionPage() {
  return (
    <AppLayout permiso="superbibliotecario">
      <Header title="Configuración" description="La biblioteca, sus códigos para la exportación MARC y el respaldo" />
      <div className="p-4 sm:p-6">
        <Ajustes />
      </div>
    </AppLayout>
  )
}
