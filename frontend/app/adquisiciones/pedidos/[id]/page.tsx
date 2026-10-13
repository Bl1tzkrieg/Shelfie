"use client"

import { useCallback, useEffect, useState } from "react"
import Link from "next/link"
import { useParams } from "next/navigation"
import { ArrowLeft, Ban, Loader2, MoreHorizontal, PackageCheck, Pencil, Plus, RotateCcw, Send, Trash2 } from "lucide-react"
import { toast } from "sonner"

import { bs, EstadoLineaBadge, EstadoPedidoBadge, fechaCorta } from "@/components/adquisiciones/comun"
import { LineaDialog } from "@/components/adquisiciones/linea-dialog"
import { RecibirDialog } from "@/components/adquisiciones/recibir-dialog"
import { AppLayout } from "@/components/layout/app-layout"
import { Header } from "@/components/layout/header"
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
} from "@/components/ui/alert-dialog"
import { Button } from "@/components/ui/button"
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu"
import { apiDelete, apiGet, apiPost, mensajeDeError } from "@/lib/api"
import type { Fondo, LineaPedido, Pedido, Proveedor } from "@/lib/types"

type Confirmacion = { titulo: string; texto: string; accion: () => Promise<Pedido>; boton: string }

export default function PedidoPage() {
  const { id } = useParams<{ id: string }>()
  const [pedido, setPedido] = useState<Pedido | null>(null)
  const [proveedor, setProveedor] = useState<Proveedor | null>(null)
  const [fondos, setFondos] = useState<Fondo[]>([])
  const [error, setError] = useState<string | null>(null)
  const [linea, setLinea] = useState<LineaPedido | "nueva" | null>(null)
  const [recibiendo, setRecibiendo] = useState<LineaPedido | null>(null)
  const [confirmar, setConfirmar] = useState<Confirmacion | null>(null)
  const [trabajando, setTrabajando] = useState(false)

  const cargar = useCallback(async () => {
    try {
      // Todo junto: el descuento del proveedor tiene que estar antes de agregar líneas.
      const [p, provs, f] = await Promise.all([
        apiGet<Pedido>(`/acquisitions/orders/${id}`),
        apiGet<Proveedor[]>("/acquisitions/suppliers"),
        apiGet<Fondo[]>("/acquisitions/funds"),
      ])
      setProveedor(provs.find((x) => x.id === p.proveedor_id) ?? null)
      setFondos(f)
      setPedido(p)
    } catch (e) {
      setError(mensajeDeError(e))
    }
  }, [id])

  useEffect(() => {
    cargar()
  }, [cargar])

  async function ejecutar(accion: () => Promise<Pedido>, aviso: string) {
    setTrabajando(true)
    try {
      setPedido(await accion())
      toast.success(aviso)
      apiGet<Fondo[]>("/acquisitions/funds").then(setFondos).catch(() => {})
    } catch (e) {
      toast.error("No se pudo completar", { description: mensajeDeError(e) })
    } finally {
      setTrabajando(false)
    }
  }

  if (!pedido) {
    return (
      <AppLayout permiso="adquisiciones">
        <Header title="Pedido" />
        <div className="p-6 text-center text-muted-foreground">
          {error ? `No se pudo cargar: ${error}` : <Loader2 className="mx-auto h-5 w-5 animate-spin" />}
        </div>
      </AppLayout>
    )
  }

  const abierta = pedido.estado === "Abierta"
  const cerrada = pedido.estado === "Cerrada"
  const lineas = pedido.lineas ?? []
  const base = `/acquisitions/orders/${pedido.id}`

  return (
    <AppLayout permiso="adquisiciones">
      <Header title={pedido.nombre} description={`Pedido #${pedido.id} a ${pedido.proveedor_nombre}`} />
      <div className="space-y-6 p-6">
        <Link href="/adquisiciones?vista=pedidos" className="inline-flex items-center gap-1 text-sm text-muted-foreground hover:text-foreground">
          <ArrowLeft className="h-4 w-4" />
          Pedidos
        </Link>

        <div className="flex flex-col gap-4 rounded-lg border bg-card p-5 lg:flex-row lg:items-start lg:justify-between">
          <div className="space-y-1">
            <div className="flex items-center gap-3">
              <EstadoPedidoBadge estado={pedido.estado} />
              {pedido.dias_atraso && (
                <span className="text-sm font-medium text-destructive">{pedido.dias_atraso} día(s) de atraso</span>
              )}
            </div>
            <p className="text-sm text-muted-foreground">
              Creado el {fechaCorta(pedido.fecha_emision)}
              {pedido.fecha_cierre && ` · enviado el ${fechaCorta(pedido.fecha_cierre)}`}
              {pedido.fecha_recepcion && ` · completado el ${fechaCorta(pedido.fecha_recepcion)}`}
              {pedido.biblioteca_entrega && ` · se entrega en ${pedido.biblioteca_entrega}`}
            </p>
            {pedido.observaciones && <p className="text-sm text-foreground">{pedido.observaciones}</p>}
            <p className="pt-1 text-sm">
              <span className="font-medium">{pedido.titulos}</span> título(s) ·{" "}
              <span className="font-medium">{pedido.recibidos}</span> de {pedido.ejemplares} ejemplar(es) recibidos ·
              estimado <span className="font-medium tabular-nums">{bs(pedido.total)}</span>
              {pedido.total_recibido > 0 && <> · facturado <span className="font-medium tabular-nums">{bs(pedido.total_recibido)}</span></>}
            </p>
          </div>
          <div className="flex flex-wrap gap-2">
            {abierta && (
              <>
                <Button variant="outline" onClick={() => setLinea("nueva")}>
                  <Plus className="mr-2 h-4 w-4" />
                  Agregar título
                </Button>
                <Button disabled={trabajando || lineas.length === 0}
                        onClick={() => setConfirmar({
                          titulo: "¿Cerrar y enviar el pedido?",
                          texto: "Ya no se le podrán agregar títulos; desde ahora se recibe lo que llegue.",
                          boton: "Cerrar y enviar",
                          accion: () => apiPost<Pedido>(`${base}/close`),
                        })}>
                  <Send className="mr-2 h-4 w-4" />
                  Cerrar y enviar
                </Button>
              </>
            )}
            {cerrada && pedido.recibidos === 0 && (
              <Button variant="outline" disabled={trabajando}
                      onClick={() => ejecutar(() => apiPost<Pedido>(`${base}/reopen`), "Pedido reabierto")}>
                <RotateCcw className="mr-2 h-4 w-4" />
                Reabrir
              </Button>
            )}
            {(abierta || cerrada) && pedido.recibidos === 0 && (
              <Button variant="outline" disabled={trabajando}
                      onClick={() => setConfirmar({
                        titulo: "¿Cancelar el pedido?",
                        texto: "Se libera todo lo comprometido de los fondos. Los registros creados al pedir quedan en el catálogo.",
                        boton: "Cancelar pedido",
                        accion: () => apiPost<Pedido>(`${base}/cancel`),
                      })}>
                <Ban className="mr-2 h-4 w-4" />
                Cancelar
              </Button>
            )}
          </div>
        </div>

        <div className="overflow-x-auto rounded-lg border bg-card">
          <table className="w-full text-sm">
            <thead className="bg-muted/50 text-left text-muted-foreground">
              <tr>
                <th className="px-4 py-3 font-medium">Título</th>
                <th className="px-4 py-3 font-medium">Fondo</th>
                <th className="px-4 py-3 text-right font-medium">Cant.</th>
                <th className="px-4 py-3 text-right font-medium">Costo c/u</th>
                <th className="px-4 py-3 text-right font-medium">Total</th>
                <th className="px-4 py-3 font-medium">Estado</th>
                <th className="px-4 py-3" />
              </tr>
            </thead>
            <tbody className="divide-y divide-border">
              {lineas.length === 0 && (
                <tr>
                  <td colSpan={7} className="px-4 py-10 text-center text-muted-foreground">
                    El pedido está vacío. Agrega los títulos que vas a comprar.
                  </td>
                </tr>
              )}
              {lineas.map((l) => (
                <tr key={l.id} className="align-top">
                  <td className="px-4 py-3">
                    {l.biblio_id ? (
                      <Link href={`/catalogo/${l.biblio_id}`} className="font-medium text-foreground hover:underline">{l.titulo}</Link>
                    ) : (
                      <span className="font-medium text-foreground">{l.titulo}</span>
                    )}
                    <p className="text-xs text-muted-foreground">
                      {[l.autor, l.isbn && `ISBN ${l.isbn}`].filter(Boolean).join(" · ")}
                    </p>
                    {l.notas && <p className="text-xs italic text-muted-foreground">{l.notas}</p>}
                  </td>
                  <td className="px-4 py-3 font-mono text-xs">{l.fondo ?? "—"}</td>
                  <td className="px-4 py-3 text-right tabular-nums">
                    {l.cantidad_recibida > 0 ? `${l.cantidad_recibida}/${l.cantidad}` : l.cantidad}
                  </td>
                  <td className="px-4 py-3 text-right tabular-nums">
                    {bs(l.costo_estimado)}
                    {l.descuento > 0 && <p className="text-xs text-muted-foreground">{bs(l.precio_unitario)} −{l.descuento} %</p>}
                  </td>
                  <td className="px-4 py-3 text-right tabular-nums">{bs(l.total_estimado)}</td>
                  <td className="px-4 py-3"><EstadoLineaBadge estado={l.estado} /></td>
                  <td className="px-4 py-3">
                    <div className="flex justify-end gap-1">
                      {cerrada && l.pendiente > 0 && (
                        <Button size="sm" onClick={() => setRecibiendo({ ...l, biblioteca_entrega_id: pedido.biblioteca_entrega_id })}>
                          <PackageCheck className="mr-2 h-4 w-4" />
                          Recibir
                        </Button>
                      )}
                      {(abierta || (cerrada && l.pendiente > 0)) && (
                        <DropdownMenu>
                          <DropdownMenuTrigger asChild>
                            <Button size="sm" variant="ghost" aria-label={`Acciones de ${l.titulo}`}>
                              <MoreHorizontal className="h-4 w-4" />
                            </Button>
                          </DropdownMenuTrigger>
                          <DropdownMenuContent align="end">
                            {abierta && (
                              <>
                                <DropdownMenuItem onClick={() => setLinea(l)}>
                                  <Pencil className="mr-2 h-4 w-4" /> Editar
                                </DropdownMenuItem>
                                <DropdownMenuItem className="text-destructive focus:text-destructive"
                                                  onClick={() => ejecutar(() => apiDelete<Pedido>(`${base}/lines/${l.id}`), "Título quitado")}>
                                  <Trash2 className="mr-2 h-4 w-4" /> Quitar
                                </DropdownMenuItem>
                              </>
                            )}
                            {cerrada && (
                              <DropdownMenuItem onClick={() => setConfirmar({
                                titulo: "¿Cancelar lo que falta?",
                                texto: `${l.pendiente} ejemplar(es) de "${l.titulo}" ya no llegarán; se libera lo comprometido del fondo.`,
                                boton: "Cancelar lo pendiente",
                                accion: () => apiPost<Pedido>(`${base}/lines/${l.id}/cancel`),
                              })}>
                                <Ban className="mr-2 h-4 w-4" /> Cancelar lo pendiente
                              </DropdownMenuItem>
                            )}
                          </DropdownMenuContent>
                        </DropdownMenu>
                      )}
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>

      <LineaDialog
        open={linea !== null}
        pedido={pedido}
        linea={linea === "nueva" ? null : linea}
        fondos={fondos}
        descuentoProveedor={proveedor?.descuento ?? 0}
        onOpenChange={(v) => !v && setLinea(null)}
        onGuardado={(p) => {
          setLinea(null)
          setPedido(p)
          apiGet<Fondo[]>("/acquisitions/funds").then(setFondos).catch(() => {})
        }}
      />
      <RecibirDialog
        linea={recibiendo}
        proveedorId={pedido.proveedor_id}
        onOpenChange={(v) => !v && setRecibiendo(null)}
        onRecibido={() => {
          setRecibiendo(null)
          cargar()
        }}
      />
      <AlertDialog open={confirmar !== null} onOpenChange={(v) => !v && setConfirmar(null)}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>{confirmar?.titulo}</AlertDialogTitle>
            <AlertDialogDescription>{confirmar?.texto}</AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel>Volver</AlertDialogCancel>
            <AlertDialogAction onClick={() => {
              if (confirmar) ejecutar(confirmar.accion, "Listo")
              setConfirmar(null)
            }}>
              {confirmar?.boton}
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </AppLayout>
  )
}
