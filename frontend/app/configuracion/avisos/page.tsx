"use client"

import { Suspense, useCallback, useEffect, useState } from "react"
import Link from "next/link"
import { usePathname, useRouter, useSearchParams } from "next/navigation"
import { ArrowLeft, Loader2 } from "lucide-react"
import { toast } from "sonner"

import { useSesion } from "@/components/auth/sesion-provider"
import { ColaAvisos } from "@/components/configuracion/avisos/cola-avisos"
import { PlantillasAvisos } from "@/components/configuracion/avisos/plantillas-avisos"
import { TareasAvisos } from "@/components/configuracion/avisos/tareas-avisos"
import { AppLayout } from "@/components/layout/app-layout"
import { Header } from "@/components/layout/header"
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs"
import { apiGet, mensajeDeError } from "@/lib/api"
import type { ResumenAvisos } from "@/lib/types"

const VISTAS = ["cola", "plantillas", "tareas"] as const
type Vista = (typeof VISTAS)[number]

export default function AvisosPage() {
  return (
    <AppLayout>
      <Header title="Avisos" description="Correos a los lectores, plantillas y tareas programadas" />
      <Suspense fallback={null}>
        <Contenido />
      </Suspense>
    </AppLayout>
  )
}

function Contenido() {
  const router = useRouter()
  const pathname = usePathname()
  const pedida = useSearchParams().get("vista")
  const vista: Vista = VISTAS.find((v) => v === pedida) ?? "cola"
  const { tienePermiso } = useSesion()
  const puedeEditar = tienePermiso("configuracion")
  const [resumen, setResumen] = useState<ResumenAvisos | null>(null)

  const cargar = useCallback(async () => {
    try {
      setResumen(await apiGet<ResumenAvisos>("/notices"))
    } catch (e) {
      toast.error("No se pudo cargar", { description: mensajeDeError(e) })
    }
  }, [])

  useEffect(() => {
    cargar()
  }, [cargar])

  return (
    <div className="p-6">
      <div className="mx-auto max-w-6xl space-y-6">
        <Link href="/configuracion" className="inline-flex items-center gap-1 text-sm text-muted-foreground hover:text-foreground">
          <ArrowLeft className="h-4 w-4" /> Configuración
        </Link>

        {resumen && (
          <div className="grid gap-4 sm:grid-cols-3">
            <Cifra titulo="Pendientes" valor={resumen.pendientes} />
            <Cifra titulo="Enviados" valor={resumen.enviados} />
            <Cifra titulo="Fallidos" valor={resumen.fallidos} alerta={resumen.fallidos > 0} />
          </div>
        )}

        <Tabs value={vista} onValueChange={(v) => router.replace(`${pathname}?vista=${v}`, { scroll: false })}>
          <TabsList>
            <TabsTrigger value="cola">Cola de correos</TabsTrigger>
            <TabsTrigger value="plantillas">Plantillas</TabsTrigger>
            <TabsTrigger value="tareas">Correo y tareas</TabsTrigger>
          </TabsList>
          <TabsContent value="cola" className="mt-6"><ColaAvisos puedeEditar={puedeEditar} onCambio={cargar} /></TabsContent>
          <TabsContent value="plantillas" className="mt-6"><PlantillasAvisos puedeEditar={puedeEditar} /></TabsContent>
          <TabsContent value="tareas" className="mt-6">
            {resumen ? <TareasAvisos resumen={resumen} puedeEditar={puedeEditar} onCambio={cargar} />
              : <Loader2 className="mx-auto my-8 h-5 w-5 animate-spin text-muted-foreground" />}
          </TabsContent>
        </Tabs>
      </div>
    </div>
  )
}

function Cifra({ titulo, valor, alerta }: { titulo: string; valor: number; alerta?: boolean }) {
  return (
    <div className={alerta ? "rounded-lg border border-destructive/40 bg-card p-4" : "rounded-lg border bg-card p-4"}>
      <p className="text-sm text-muted-foreground">{titulo}</p>
      <p className={alerta ? "text-2xl font-semibold tabular-nums text-destructive" : "text-2xl font-semibold tabular-nums text-foreground"}>
        {valor}
      </p>
    </div>
  )
}
