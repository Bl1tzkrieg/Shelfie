"use client"

import { Suspense, useEffect, useState } from "react"
import Link from "next/link"
import { useRouter, useSearchParams } from "next/navigation"
import { ArrowLeft, Loader2 } from "lucide-react"
import { toast } from "sonner"

import { useSesion } from "@/components/auth/sesion-provider"
import { AppLayout } from "@/components/layout/app-layout"
import { Header } from "@/components/layout/header"
import { EditorMarc } from "@/components/marc/editor-marc"
import { Button } from "@/components/ui/button"
import { apiGet, apiPut, mensajeDeError } from "@/lib/api"
import type { RegistroMarc, RegistroMarcGuardado } from "@/lib/types"

/** Editor MARC avanzado de un registro: /marc?id=. Solo para el administrador. */
export default function MarcPage() {
  return (
    <AppLayout>
      <Suspense fallback={<Header title="Editor MARC" />}>
        <SoloAdministrador />
      </Suspense>
    </AppLayout>
  )
}

function SoloAdministrador() {
  const router = useRouter()
  const { tienePermiso } = useSesion()
  const esAdministrador = tienePermiso("superbibliotecario")

  useEffect(() => {
    if (!esAdministrador) router.replace("/")
  }, [esAdministrador, router])

  return esAdministrador ? <Marc /> : null
}

function Marc() {
  const router = useRouter()
  const id = useSearchParams().get("id")
  const [carga, setCarga] = useState<{ id: string; registro: RegistroMarcGuardado | null; error?: string } | null>(null)

  useEffect(() => {
    if (!id) return
    let vigente = true
    apiGet<RegistroMarcGuardado>(`/catalog/items/${encodeURIComponent(id)}/marc`)
      .then((registro) => vigente && setCarga({ id, registro }))
      .catch((error) => vigente && setCarga({ id, registro: null, error: mensajeDeError(error) }))
    return () => {
      vigente = false
    }
  }, [id])

  async function guardar(plantilla: string, marc: RegistroMarc, permitirDuplicado: boolean) {
    const r = await apiPut<RegistroMarcGuardado>(`/catalog/items/${id}/marc`, {
      plantilla,
      marc,
      permitir_duplicado: permitirDuplicado,
    })
    setCarga({ id: id!, registro: r })
    toast.success("Registro MARC guardado", {
      description: r.titulo,
      action: { label: "Volver a la ficha", onClick: () => router.push(`/ingreso/?id=${id}`) },
    })
  }

  const actual = carga && carga.id === id ? carga : null
  const registro = actual?.registro ?? null

  return (
    <>
      <Header title="Editor MARC" description={registro ? registro.titulo : id ? `Libro n.º ${id}` : undefined}>
        {id && (
          <Button asChild variant="outline" size="sm">
            <Link href={`/ingreso/?id=${id}`}>
              <ArrowLeft /> Volver a la ficha
            </Link>
          </Button>
        )}
      </Header>
      <div className="p-4 sm:p-6">
        {!id ? (
          <p className="py-12 text-center text-muted-foreground">
            Abre el editor MARC desde la edición de un libro.
          </p>
        ) : !actual ? (
          <p className="flex items-center justify-center gap-2 py-12 text-muted-foreground">
            <Loader2 className="h-4 w-4 animate-spin" /> Cargando el registro…
          </p>
        ) : !registro ? (
          <p role="alert" className="py-12 text-center text-destructive">
            No se pudo cargar el registro: {actual.error}
          </p>
        ) : (
          <EditorMarc
            key={`${registro.id}-${registro.plantilla}`}
            plantillaInicial={registro.plantilla}
            marcInicial={registro.marc}
            textoBoton="Guardar registro"
            onGuardar={guardar}
          />
        )}
      </div>
    </>
  )
}
