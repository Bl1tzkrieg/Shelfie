"use client"

import { Suspense, useEffect, useState } from "react"
import Link from "next/link"
import { useSearchParams } from "next/navigation"
import { Code2, Loader2 } from "lucide-react"

import { useSesion } from "@/components/auth/sesion-provider"
import { AppLayout } from "@/components/layout/app-layout"
import { Header } from "@/components/layout/header"
import { Ejemplares } from "@/components/lite/ejemplares"
import { EnlaceFicha, FormularioLibro } from "@/components/lite/formulario-libro"
import { Button } from "@/components/ui/button"
import { ApiError, apiGet, mensajeDeError } from "@/lib/api"
import type { EjemplarLibro, LibroCatalogo } from "@/lib/types"

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
  if (!id) {
    return (
      <>
        <Header title="Ingreso" description="Alta de un libro con su cota y sus ejemplares" />
        <div className="p-4 sm:p-6">
          <FormularioLibro libro={null} />
        </div>
      </>
    )
  }
  // La clave rehace la edición al pasar de un libro a otro.
  return <Edicion key={id} id={id} />
}

type Carga = { libro: LibroCatalogo } | { error: string; noExiste: boolean }

function Edicion({ id }: { id: string }) {
  const { tienePermiso } = useSesion()
  const [carga, setCarga] = useState<Carga | null>(null)
  const [ejemplares, setEjemplares] = useState<EjemplarLibro[]>([])

  useEffect(() => {
    let vigente = true
    apiGet<LibroCatalogo>(`/books/${encodeURIComponent(id)}`)
      .then((libro) => {
        if (!vigente) return
        setCarga({ libro })
        setEjemplares(libro.ejemplares)
      })
      .catch((error) => {
        if (!vigente) return
        const noExiste = error instanceof ApiError && (error.status === 404 || error.status === 422)
        setCarga({ error: mensajeDeError(error), noExiste })
      })
    return () => {
      vigente = false
    }
  }, [id])

  const libro = carga && "libro" in carga ? carga.libro : null
  const titulo = libro?.ficha.titulo || "Libro sin título"

  return (
    <>
      <Header title="Editar libro" description={libro ? titulo : `Libro n.º ${id}`}>
        {libro && <EnlaceFicha id={libro.id} />}
        {libro && tienePermiso("superbibliotecario") && (
          <Button asChild variant="outline" size="sm">
            <Link href={`/marc/?id=${libro.id}`}>
              <Code2 /> Editar MARC
            </Link>
          </Button>
        )}
      </Header>
      <div className="space-y-6 p-4 sm:p-6">
        {carga === null && (
          <p className="flex items-center justify-center gap-2 py-12 text-muted-foreground">
            <Loader2 className="h-4 w-4 animate-spin" /> Cargando el libro…
          </p>
        )}
        {carga && "error" in carga && (
          <div className="mx-auto max-w-md space-y-3 py-12 text-center">
            <p className="font-medium text-foreground">
              {carga.noExiste ? "Ese libro no existe o ya se borró." : "No se pudo cargar el libro."}
            </p>
            {!carga.noExiste && <p className="text-sm text-muted-foreground">{carga.error}</p>}
            <Button asChild variant="outline">
              <Link href="/libros/">Ir a Libros</Link>
            </Button>
          </div>
        )}
        {libro && (
          <>
            <FormularioLibro libro={libro} />
            <Ejemplares libroId={libro.id} cotaLibro={libro.ficha.cota ?? ""} ejemplares={ejemplares}
                        onCambio={setEjemplares} />
          </>
        )}
      </div>
    </>
  )
}
