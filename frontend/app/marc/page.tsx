"use client"

import { Suspense } from "react"
import { useSearchParams } from "next/navigation"

import { AppLayout } from "@/components/layout/app-layout"
import { Header } from "@/components/layout/header"
import { EnConstruccion } from "@/components/lite/en-construccion"

/** Editor MARC avanzado de un registro: /marc?id=. */
export default function MarcPage() {
  return (
    <AppLayout permiso="superbibliotecario">
      <Suspense fallback={<Header title="Editor MARC" />}>
        <Marc />
      </Suspense>
    </AppLayout>
  )
}

function Marc() {
  const id = useSearchParams().get("id")
  return (
    <>
      <Header title="Editor MARC" description={id ? `Libro n.º ${id}` : undefined} />
      <div className="p-4 sm:p-6">
        <EnConstruccion />
      </div>
    </>
  )
}
