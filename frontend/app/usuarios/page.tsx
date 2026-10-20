"use client"

import { AppLayout } from "@/components/layout/app-layout"
import { Header } from "@/components/layout/header"
import { EnConstruccion } from "@/components/lite/en-construccion"

/** El personal: crear, asignar el rol, desactivar y restablecer la contraseña. */
export default function UsuariosPage() {
  return (
    <AppLayout permiso="superbibliotecario">
      <Header title="Usuarios" description="Administradores y catalogadores" />
      <div className="p-4 sm:p-6">
        <EnConstruccion />
      </div>
    </AppLayout>
  )
}
