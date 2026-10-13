"use client"

import { Suspense } from "react"
import { usePathname, useRouter, useSearchParams } from "next/navigation"

import { FacturasPanel } from "@/components/adquisiciones/facturas"
import { PedidosPanel } from "@/components/adquisiciones/pedidos"
import { PresupuestosPanel } from "@/components/adquisiciones/presupuestos"
import { ProveedoresPanel } from "@/components/adquisiciones/proveedores"
import { ResumenAdquisicionesPanel } from "@/components/adquisiciones/resumen"
import { SugerenciasPanel } from "@/components/adquisiciones/sugerencias"
import { AppLayout } from "@/components/layout/app-layout"
import { Header } from "@/components/layout/header"
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs"

const VISTAS = {
  resumen: { texto: "Resumen", Panel: ResumenAdquisicionesPanel },
  pedidos: { texto: "Pedidos", Panel: PedidosPanel },
  facturas: { texto: "Facturas", Panel: FacturasPanel },
  proveedores: { texto: "Proveedores", Panel: ProveedoresPanel },
  presupuestos: { texto: "Presupuestos y fondos", Panel: PresupuestosPanel },
  sugerencias: { texto: "Sugerencias", Panel: SugerenciasPanel },
} as const

type Vista = keyof typeof VISTAS

export default function AdquisicionesPage() {
  return (
    <AppLayout permiso="adquisiciones">
      <Header title="Adquisiciones" description="Pedidos, recepción, facturas y presupuesto" />
      <Suspense fallback={null}>
        <Contenido />
      </Suspense>
    </AppLayout>
  )
}

function Contenido() {
  const router = useRouter()
  const pathname = usePathname()
  const params = useSearchParams()
  const pedida = params.get("vista")
  const vista: Vista = pedida && pedida in VISTAS ? (pedida as Vista) : "resumen"

  return (
    <div className="p-6">
      <Tabs value={vista} onValueChange={(v) => router.replace(`${pathname}?vista=${v}`, { scroll: false })}>
        <TabsList className="flex-wrap">
          {(Object.keys(VISTAS) as Vista[]).map((v) => (
            <TabsTrigger key={v} value={v}>{VISTAS[v].texto}</TabsTrigger>
          ))}
        </TabsList>
        {(Object.keys(VISTAS) as Vista[]).map((v) => {
          const { Panel } = VISTAS[v]
          return (
            <TabsContent key={v} value={v} className="mt-6">
              {vista === v && <Panel />}
            </TabsContent>
          )
        })}
      </Tabs>
    </div>
  )
}
