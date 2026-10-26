"use client"

import { useCallback, useEffect, useState } from "react"
import Link from "next/link"
import { useParams, useRouter } from "next/navigation"
import { ArrowLeft, Loader2, Lock, LockOpen, PackageCheck, Save, Trash2, Undo2 } from "lucide-react"
import { toast } from "sonner"

import { bs, fechaCorta, FondoSelect, Vacio } from "@/components/adquisiciones/comun"
import { RecibirDialog } from "@/components/adquisiciones/recibir-dialog"
import { AppLayout } from "@/components/layout/app-layout"
import { Header } from "@/components/layout/header"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { Textarea } from "@/components/ui/textarea"
import { apiDelete, apiGet, apiPost, apiPut, mensajeDeError } from "@/lib/api"
import type { Factura, Fondo, LineaPedido } from "@/lib/types"
import { cn } from "@/lib/utils"

export default function FacturaPage() {
  const { id } = useParams<{ id: string }>()
  const router = useRouter()
  const [factura, setFactura] = useState<Factura | null>(null)
  const [pendientes, setPendientes] = useState<LineaPedido[]>([])
  const [fondos, setFondos] = useState<Fondo[]>([])
  const [error, setError] = useState<string | null>(null)
  const [recibiendo, setRecibiendo] = useState<LineaPedido | null>(null)
  const [trabajando, setTrabajando] = useState(false)

  const cargar = useCallback(async () => {
    try {
      const f = await apiGet<Factura>(`/acquisitions/invoices/${id}`)
      setFactura(f)
      const [p, fo] = await Promise.all([
        apiGet<LineaPedido[]>(`/acquisitions/suppliers/${f.proveedor_id}/receivable`),
        apiGet<Fondo[]>("/acquisitions/funds"),
      ])
      setPendientes(p)
      setFondos(fo)
    } catch (e) {
      setError(mensajeDeError(e))
    }
  }, [id])

  useEffect(() => {
    cargar()
  }, [cargar])

  async function ejecutar(accion: () => Promise<unknown>, aviso: string) {
    setTrabajando(true)
    try {
      await accion()
      toast.success(aviso)
      await cargar()
    } catch (e) {
      toast.error("No se pudo completar", { description: mensajeDeError(e) })
    } finally {
      setTrabajando(false)
    }
  }

  if (!factura) {
    return (
      <AppLayout permiso="adquisiciones">
        <Header title="Factura" />
        <div className="p-6 text-center text-muted-foreground">
          {error ? `No se pudo cargar: ${error}` : <Loader2 className="mx-auto h-5 w-5 animate-spin" />}
        </div>
      </AppLayout>
    )
  }

  const recepciones = factura.recepciones ?? []
  const base = `/acquisitions/invoices/${factura.id}`

  return (
    <AppLayout permiso="adquisiciones">
      <Header title={`Factura ${factura.numero}`} description={`${factura.proveedor_nombre} · ${fechaCorta(factura.fecha)}`} />
      <div className="space-y-6 p-6">
        <Link href="/adquisiciones?vista=facturas" className="inline-flex items-center gap-1 text-sm text-muted-foreground hover:text-foreground">
          <ArrowLeft className="h-4 w-4" />
          Facturas
        </Link>

        <div className="grid gap-6 lg:grid-cols-[1fr_22rem]">
          <div className="space-y-6">
            <section className="space-y-3">
              <h3 className="font-semibold text-foreground">Por recibir de {factura.proveedor_nombre}</h3>
              {factura.cerrada ? (
                <Vacio>La factura está cerrada. Reábrela para recibir contra ella.</Vacio>
              ) : pendientes.length === 0 ? (
                <Vacio>
                  Este proveedor no tiene pedidos enviados con algo pendiente. Los pedidos se reciben
                  después de cerrarlos.
                </Vacio>
              ) : (
                <div className="overflow-x-auto rounded-lg border bg-card shadow-papel">
                  <table className="w-full text-sm">
                    <thead className="bg-muted/50 text-left text-muted-foreground">
                      <tr>
                        <th className="px-4 py-3 font-medium">Título</th>
                        <th className="px-4 py-3 font-medium">Pedido</th>
                        <th className="px-4 py-3 text-right font-medium">Faltan</th>
                        <th className="px-4 py-3 text-right font-medium">Estimado c/u</th>
                        <th className="px-4 py-3" />
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-border">
                      {pendientes.map((l) => (
                        <tr key={l.id}>
                          <td className="px-4 py-3">
                            <p className="font-medium text-foreground">{l.titulo}</p>
                            <p className="text-xs text-muted-foreground">{[l.autor, l.isbn].filter(Boolean).join(" · ")}</p>
                          </td>
                          <td className="px-4 py-3">
                            <Link href={`/adquisiciones/pedidos/${l.orden_id}`} className="hover:underline">{l.orden}</Link>
                          </td>
                          <td className="px-4 py-3 text-right tabular-nums">{l.pendiente}</td>
                          <td className="px-4 py-3 text-right tabular-nums">{bs(l.costo_estimado)}</td>
                          <td className="px-4 py-3 text-right">
                            <Button size="sm" onClick={() => setRecibiendo(l)} aria-label={`Recibir ${l.titulo}`}>
                              <PackageCheck className="mr-2 h-4 w-4" />
                              Recibir
                            </Button>
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )}
            </section>

            <section className="space-y-3">
              <h3 className="font-semibold text-foreground">Recibido en esta factura</h3>
              {recepciones.length === 0 ? (
                <Vacio>Todavía no se recibió nada contra esta factura.</Vacio>
              ) : (
                <div className="overflow-x-auto rounded-lg border bg-card shadow-papel">
                  <table className="w-full text-sm">
                    <thead className="bg-muted/50 text-left text-muted-foreground">
                      <tr>
                        <th className="px-4 py-3 font-medium">Título</th>
                        <th className="px-4 py-3 font-medium">Ejemplares</th>
                        <th className="px-4 py-3 text-right font-medium">Costo c/u</th>
                        <th className="px-4 py-3 text-right font-medium">Total</th>
                        <th className="px-4 py-3" />
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-border">
                      {recepciones.map((r) => (
                        <tr key={r.id} className="align-top">
                          <td className="px-4 py-3">
                            {r.biblio_id ? (
                              <Link href={`/catalogo/${r.biblio_id}`} className="font-medium text-foreground hover:underline">{r.titulo}</Link>
                            ) : r.titulo}
                            <p className="text-xs text-muted-foreground">
                              {r.orden}{r.fondo && ` · fondo ${r.fondo}`} · {r.fecha}
                            </p>
                          </td>
                          <td className="px-4 py-3 font-mono text-xs">{r.ejemplares.join(", ")}</td>
                          <td className={cn("px-4 py-3 text-right tabular-nums",
                                            r.costo_unitario > r.costo_estimado && "text-destructive")}>
                            {bs(r.costo_unitario)}
                            {r.costo_unitario !== r.costo_estimado && (
                              <p className="text-xs text-muted-foreground">estimado {bs(r.costo_estimado)}</p>
                            )}
                          </td>
                          <td className="px-4 py-3 text-right tabular-nums">{bs(r.total)}</td>
                          <td className="px-4 py-3 text-right">
                            {!factura.cerrada && (
                              <Button size="sm" variant="ghost" disabled={trabajando}
                                      onClick={() => ejecutar(() => apiDelete(`/acquisitions/receipts/${r.id}`), "Recepción deshecha")}
                                      aria-label={`Deshacer la recepción de ${r.titulo}`}>
                                <Undo2 className="h-4 w-4" />
                              </Button>
                            )}
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )}
            </section>
          </div>

          <aside className="space-y-4">
            <div className="rounded-lg border bg-card shadow-papel p-5">
              <div className="mb-3 flex items-center justify-between">
                <h3 className="font-semibold text-foreground">Totales</h3>
                {factura.cerrada ? <Badge variant="outline">Cerrada</Badge> : <Badge variant="secondary">Abierta</Badge>}
              </div>
              <dl className="space-y-1 text-sm">
                <div className="flex justify-between"><dt className="text-muted-foreground">Ejemplares</dt><dd className="tabular-nums">{factura.unidades}</dd></div>
                <div className="flex justify-between"><dt className="text-muted-foreground">Subtotal</dt><dd className="tabular-nums">{bs(factura.subtotal)}</dd></div>
                <div className="flex justify-between"><dt className="text-muted-foreground">Envío</dt><dd className="tabular-nums">{bs(factura.costo_envio)}</dd></div>
                <div className="flex justify-between border-t pt-1 font-medium"><dt>Total</dt><dd className="tabular-nums">{bs(factura.total)}</dd></div>
              </dl>
            </div>

            {!factura.cerrada && (
              <DatosFactura key={`${factura.id}-${factura.costo_envio}-${factura.fondo_envio_id}`}
                            factura={factura} fondos={fondos} onGuardado={cargar} />
            )}

            <div className="flex flex-wrap gap-2">
              <Button variant="outline" disabled={trabajando}
                      onClick={() => ejecutar(() => apiPost(`${base}/${factura.cerrada ? "reopen" : "close"}`),
                                              factura.cerrada ? "Factura reabierta" : "Factura cerrada")}>
                {factura.cerrada ? <LockOpen className="mr-2 h-4 w-4" /> : <Lock className="mr-2 h-4 w-4" />}
                {factura.cerrada ? "Reabrir" : "Cerrar factura"}
              </Button>
              {recepciones.length === 0 && (
                <Button variant="outline" disabled={trabajando}
                        onClick={async () => {
                          try {
                            await apiDelete(base)
                            toast.success("Factura eliminada")
                            router.push("/adquisiciones?vista=facturas")
                          } catch (e) {
                            toast.error("No se pudo eliminar", { description: mensajeDeError(e) })
                          }
                        }}>
                  <Trash2 className="mr-2 h-4 w-4" />
                  Eliminar
                </Button>
              )}
            </div>
          </aside>
        </div>
      </div>

      <RecibirDialog
        linea={recibiendo}
        proveedorId={factura.proveedor_id}
        facturaId={factura.id}
        onOpenChange={(v) => !v && setRecibiendo(null)}
        onRecibido={() => {
          setRecibiendo(null)
          cargar()
        }}
      />
    </AppLayout>
  )
}

function DatosFactura({ factura, fondos, onGuardado }: { factura: Factura; fondos: Fondo[]; onGuardado: () => void }) {
  const [envio, setEnvio] = useState(String(factura.costo_envio))
  const [fondo, setFondo] = useState<number | null>(factura.fondo_envio_id)
  const [notas, setNotas] = useState(factura.notas ?? "")
  const [guardando, setGuardando] = useState(false)

  async function guardar(e: React.FormEvent) {
    e.preventDefault()
    setGuardando(true)
    try {
      await apiPut(`/acquisitions/invoices/${factura.id}`, {
        costo_envio: Number(envio || 0), fondo_envio_id: fondo, notas,
      })
      toast.success("Factura actualizada")
      onGuardado()
    } catch (error) {
      toast.error("No se pudo guardar", { description: mensajeDeError(error) })
    } finally {
      setGuardando(false)
    }
  }

  return (
    <form onSubmit={guardar} className="space-y-3 rounded-lg border bg-card shadow-papel p-5">
      <h3 className="font-semibold text-foreground">Envío y notas</h3>
      <div className="space-y-2">
        <Label htmlFor="factura-envio">Costo de envío (Bs.)</Label>
        <Input id="factura-envio" type="number" min={0} step="0.01" value={envio} onChange={(e) => setEnvio(e.target.value)} />
      </div>
      <div className="space-y-2">
        <Label htmlFor="factura-fondo">Se carga al fondo</Label>
        <FondoSelect id="factura-fondo" fondos={fondos} valor={fondo} onChange={setFondo} />
      </div>
      <div className="space-y-2">
        <Label htmlFor="factura-notas">Notas</Label>
        <Textarea id="factura-notas" rows={2} value={notas} onChange={(e) => setNotas(e.target.value)} />
      </div>
      <Button type="submit" size="sm" disabled={guardando}>
        {guardando ? <Loader2 className="mr-2 h-4 w-4 animate-spin" /> : <Save className="mr-2 h-4 w-4" />}
        Guardar
      </Button>
    </form>
  )
}
