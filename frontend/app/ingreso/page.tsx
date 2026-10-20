"use client"

import { Suspense } from "react"
import { useSearchParams } from "next/navigation"

import { AppLayout } from "@/components/layout/app-layout"
import { Header } from "@/components/layout/header"
import { EnConstruccion } from "@/components/lite/en-construccion"

/** Ingreso de un libro nuevo, o edición de uno con /ingreso?id=. */
export default function IngresoPage() {
  return (
    <AppLayout permiso="catalogo">
      <Suspense fallback={<Header title="Ingreso" />}>
        <Ingreso />
      </Suspense>
    </AppLayout>
  )
}

function Ingreso() {
  const id = useSearchParams().get("id")
  return (
    <>
      <Header title={id ? "Editar libro" : "Ingreso"}
              description={id ? `Libro n.º ${id}` : "Alta de un libro con su cota y sus ejemplares"} />
      <div className="p-4 sm:p-6">
        <EnConstruccion />
      </div>
    </>
  )
}
