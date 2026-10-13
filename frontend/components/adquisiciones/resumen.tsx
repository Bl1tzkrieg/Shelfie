"use client"

import { useEffect, useState } from "react"
import Link from "next/link"
import { AlertTriangle, Loader2 } from "lucide-react"
import { toast } from "sonner"

import { apiGet, mensajeDeError } from "@/lib/api"
import type { PedidoAtrasado, ResumenAdquisiciones } from "@/lib/types"
import { BarraFondo, bs, Kpi, Vacio } from "./comun"

export function ResumenAdquisicionesPanel() {
  const [resumen, setResumen] = useState<ResumenAdquisiciones | null>(null)
  const [atrasados, setAtrasados] = useState<PedidoAtrasado[]>([])

  useEffect(() => {
    Promise.all([
      apiGet<ResumenAdquisiciones>("/acquisitions/summary"),
      apiGet<PedidoAtrasado[]>("/acquisitions/orders/late"),
    ])
      .then(([r, a]) => {
        setResumen(r)
        setAtrasados(a)
      })
      .catch((e) => toast.error("No se pudo cargar el resumen", { description: mensajeDeError(e) }))
  }, [])

  if (!resumen) {
    return (
      <div className="py-16 text-center text-muted-foreground">
        <Loader2 className="mx-auto h-5 w-5 animate-spin" />
      </div>
    )
  }

  return (
    <div className="space-y-6">
      <div className="grid grid-cols-2 gap-4 lg:grid-cols-5">
        <Kpi titulo="Pedidos abiertos" valor={resumen.pedidos_abiertos} />
        <Kpi titulo="Por recibir" valor={resumen.pedidos_por_recibir} />
        <Kpi titulo="Atrasados" valor={resumen.pedidos_atrasados} alerta={resumen.pedidos_atrasados > 0} />
        <Kpi titulo="Facturas abiertas" valor={resumen.facturas_abiertas} />
        <Kpi titulo="Sugerencias por revisar" valor={resumen.sugerencias_pendientes} />
      </div>

      <section className="space-y-3">
        <h3 className="font-semibold text-foreground">Fondos disponibles</h3>
        {resumen.fondos.length === 0 ? (
          <Vacio>
            No hay fondos activos. Créalos en{" "}
            <Link href="/adquisiciones?vista=presupuestos" className="text-primary hover:underline">Presupuestos</Link>;
            mientras tanto se puede pedir sin fondo.
          </Vacio>
        ) : (
          <div className="grid gap-3 md:grid-cols-2">
            {resumen.fondos.map((f) => (
              <div key={f.id} className="rounded-lg border bg-card p-4">
                <div className="mb-2 flex items-baseline justify-between gap-3">
                  <p className="font-medium text-foreground">
                    <span className="font-mono text-xs text-muted-foreground">{f.codigo}</span> {f.nombre}
                  </p>
                  <p className="text-sm tabular-nums text-muted-foreground">{bs(f.asignado)}</p>
                </div>
                <BarraFondo fondo={f} />
                {f.presupuesto && <p className="mt-1 text-xs text-muted-foreground">{f.presupuesto}</p>}
              </div>
            ))}
          </div>
        )}
      </section>

      {atrasados.length > 0 && (
        <section className="space-y-3">
          <h3 className="flex items-center gap-2 font-semibold text-foreground">
            <AlertTriangle className="h-4 w-4 text-destructive" />
            Pedidos atrasados
          </h3>
          <div className="divide-y divide-border rounded-lg border bg-card">
            {atrasados.map((a) => (
              <div key={a.orden_id} className="flex flex-col gap-1 px-4 py-3 sm:flex-row sm:items-center sm:justify-between">
                <div>
                  <Link href={`/adquisiciones/pedidos/${a.orden_id}`} className="font-medium text-foreground hover:underline">
                    {a.nombre}
                  </Link>
                  <p className="text-xs text-muted-foreground">
                    {a.proveedor_nombre} · enviado el {a.fecha_cierre} ·{" "}
                    {a.lineas.reduce((s, l) => s + l.pendiente, 0)} ejemplar(es) sin llegar
                  </p>
                </div>
                <div className="flex items-center gap-3 text-sm">
                  <span className="font-medium text-destructive">{a.dias_atraso} día(s) de atraso</span>
                  {a.proveedor_email && (
                    <a className="text-primary hover:underline"
                       href={`mailto:${a.proveedor_email}?subject=${encodeURIComponent(`Reclamo: ${a.nombre}`)}&body=${encodeURIComponent(
                         `Buenos días,\n\nTodavía no hemos recibido lo siguiente del pedido "${a.nombre}" (enviado el ${a.fecha_cierre}):\n\n${a.lineas
                           .map((l) => `- ${l.titulo}${l.isbn ? ` (ISBN ${l.isbn})` : ""}: ${l.pendiente}`)
                           .join("\n")}\n\nGracias.`,
                       )}`}>
                      Reclamar por correo
                    </a>
                  )}
                </div>
              </div>
            ))}
          </div>
        </section>
      )}
    </div>
  )
}
