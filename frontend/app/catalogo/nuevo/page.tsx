"use client"

import { Suspense } from "react"
import Link from "next/link"
import { useRouter, useSearchParams } from "next/navigation"
import { ArrowLeft } from "lucide-react"
import { toast } from "sonner"

import { AppLayout } from "@/components/layout/app-layout"
import { Header } from "@/components/layout/header"
import { EditorMarc } from "@/components/catalogo/editor-marc"
import { apiPost } from "@/lib/api"
import type { RegistroMarc, RegistroMarcGuardado } from "@/lib/types"

export default function NuevoRegistroPage() {
  return (
    <Suspense fallback={null}>
      <NuevoRegistro />
    </Suspense>
  )
}

/** Catalogación completa con el editor MARC. Los ejemplares se agregan en la ficha. */
function NuevoRegistro() {
  const router = useRouter()
  const plantilla = useSearchParams().get("plantilla") ?? "BKS"

  async function crear(codigo: string, marc: RegistroMarc, permitirDuplicado: boolean) {
    const r = await apiPost<RegistroMarcGuardado>("/catalog/records", {
      plantilla: codigo,
      marc,
      permitir_duplicado: permitirDuplicado,
    })
    toast.success("Registro catalogado", {
      description: `${r.titulo}. Ahora agrega sus ejemplares.`,
    })
    router.push(`/catalogo/${r.id}?ejemplar=nuevo`)
  }

  return (
    <AppLayout permiso="catalogo">
      <Header title="Nuevo registro" description="Catalogación MARC21" />
      <div className="p-6">
        <div className="mx-auto max-w-5xl space-y-4">
          <Link href="/catalogo"
                className="inline-flex items-center gap-1 text-sm text-muted-foreground hover:text-foreground">
            <ArrowLeft className="h-4 w-4" />
            Catálogo
          </Link>
          {/* key: cambiar de plantilla desde la URL arranca un registro limpio. */}
          <EditorMarc key={plantilla} plantillaInicial={plantilla} marcInicial={null}
                      textoBoton="Crear registro" onGuardar={crear} />
        </div>
      </div>
    </AppLayout>
  )
}
