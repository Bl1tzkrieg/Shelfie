"use client"

import { useCallback, useEffect, useState } from "react"
import Link from "next/link"
import { useRouter } from "next/navigation"
import { Loader2, Plus } from "lucide-react"
import { toast } from "sonner"

import { useSedes } from "@/components/layout/sede-provider"
import { Button } from "@/components/ui/button"
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select"
import { Textarea } from "@/components/ui/textarea"
import { apiGet, apiPost, mensajeDeError } from "@/lib/api"
import type { Pedido, Proveedor } from "@/lib/types"
import { cn } from "@/lib/utils"
import { bs, EstadoPedidoBadge, fechaCorta, Vacio } from "./comun"

const FILTROS = [
  { valor: "Abierta,Cerrada", texto: "En curso" },
  { valor: "Abierta", texto: "Abiertos" },
  { valor: "Cerrada", texto: "Por recibir" },
  { valor: "Recibida", texto: "Recibidos" },
  { valor: "Cancelada", texto: "Cancelados" },
  { valor: "", texto: "Todos" },
]

export function PedidosPanel() {
  const [filtro, setFiltro] = useState("Abierta,Cerrada")
  const [pedidos, setPedidos] = useState<Pedido[] | null>(null)
  const [nuevo, setNuevo] = useState(false)

  const cargar = useCallback(async () => {
    try {
      setPedidos(await apiGet<Pedido[]>(`/acquisitions/orders${filtro ? `?estado=${filtro}` : ""}`))
    } catch (e) {
      toast.error("No se pudieron cargar los pedidos", { description: mensajeDeError(e) })
    }
  }, [filtro])

  useEffect(() => {
    cargar()
  }, [cargar])

  return (
    <div className="space-y-4">
      <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
        <div className="flex flex-wrap gap-1.5" role="group" aria-label="Filtrar pedidos">
          {FILTROS.map((f) => (
            <Button key={f.texto} size="sm" variant={filtro === f.valor ? "default" : "outline"}
                    aria-pressed={filtro === f.valor} onClick={() => setFiltro(f.valor)}>
              {f.texto}
            </Button>
          ))}
        </div>
        <Button onClick={() => setNuevo(true)}>
          <Plus className="mr-2 h-4 w-4" />
          Nuevo pedido
        </Button>
      </div>

      {pedidos === null ? (
        <div className="py-12 text-center text-muted-foreground"><Loader2 className="mx-auto h-5 w-5 animate-spin" /></div>
      ) : pedidos.length === 0 ? (
        <Vacio>No hay pedidos con este filtro.</Vacio>
      ) : (
        <div className="overflow-x-auto rounded-lg border bg-card shadow-papel">
          <table className="w-full text-sm">
            <thead className="bg-muted/50 text-left text-muted-foreground">
              <tr>
                <th className="px-4 py-3 font-medium">Pedido</th>
                <th className="px-4 py-3 font-medium">Proveedor</th>
                <th className="px-4 py-3 font-medium">Estado</th>
                <th className="px-4 py-3 text-right font-medium">Títulos</th>
                <th className="px-4 py-3 text-right font-medium">Recibidos</th>
                <th className="px-4 py-3 text-right font-medium">Total estimado</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-border">
              {pedidos.map((p) => (
                <tr key={p.id} className="hover:bg-muted/30">
                  <td className="px-4 py-3">
                    <Link href={`/adquisiciones/pedidos/${p.id}`} className="font-medium text-foreground hover:underline">
                      {p.nombre}
                    </Link>
                    <p className="text-xs text-muted-foreground">
                      #{p.id} · creado el {fechaCorta(p.fecha_emision)}
                      {p.fecha_cierre && ` · enviado el ${fechaCorta(p.fecha_cierre)}`}
                    </p>
                  </td>
                  <td className="px-4 py-3">{p.proveedor_nombre}</td>
                  <td className="px-4 py-3">
                    <EstadoPedidoBadge estado={p.estado} />
                    {p.dias_atraso && (
                      <span className="ml-2 text-xs font-medium text-destructive">{p.dias_atraso} d atraso</span>
                    )}
                  </td>
                  <td className="px-4 py-3 text-right tabular-nums">{p.titulos}</td>
                  <td className={cn("px-4 py-3 text-right tabular-nums", p.recibidos < p.ejemplares && p.estado === "Cerrada" && "text-aviso-foreground")}>
                    {p.recibidos} / {p.ejemplares}
                  </td>
                  <td className="px-4 py-3 text-right tabular-nums">{bs(p.total)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      <NuevoPedidoDialog open={nuevo} onOpenChange={setNuevo} />
    </div>
  )
}

function NuevoPedidoDialog({ open, onOpenChange }: { open: boolean; onOpenChange: (v: boolean) => void }) {
  const router = useRouter()
  const { sedes, sedeId } = useSedes()
  const [proveedores, setProveedores] = useState<Proveedor[]>([])
  const [proveedor, setProveedor] = useState("")
  const [nombre, setNombre] = useState("")
  const [sede, setSede] = useState("")
  const [observaciones, setObservaciones] = useState("")
  const [enviando, setEnviando] = useState(false)

  useEffect(() => {
    if (!open) return
    apiGet<Proveedor[]>("/acquisitions/suppliers")
      .then((p) => setProveedores(p.filter((x) => x.activo)))
      .catch(() => setProveedores([]))
  }, [open])

  async function crear(e: React.FormEvent) {
    e.preventDefault()
    setEnviando(true)
    try {
      const p = await apiPost<Pedido>("/acquisitions/orders", {
        proveedor_id: Number(proveedor),
        nombre: nombre.trim() || null,
        observaciones: observaciones.trim() || null,
        biblioteca_entrega_id: sede ? Number(sede) : sedeId,
      })
      toast.success("Pedido creado", { description: "Agrégale los títulos." })
      router.push(`/adquisiciones/pedidos/${p.id}`)
    } catch (error) {
      toast.error("No se pudo crear el pedido", { description: mensajeDeError(error) })
      setEnviando(false)
    }
  }

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-md">
        <form onSubmit={crear}>
          <DialogHeader>
            <DialogTitle>Nuevo pedido</DialogTitle>
            <DialogDescription>Se arma abierto; al cerrarlo se considera enviado al proveedor.</DialogDescription>
          </DialogHeader>
          <div className="space-y-4 py-4">
            <div className="space-y-2">
              <Label htmlFor="pedido-proveedor">Proveedor</Label>
              <Select value={proveedor} onValueChange={setProveedor}>
                <SelectTrigger id="pedido-proveedor" className="w-full">
                  <SelectValue placeholder={proveedores.length ? "Elige el proveedor" : "No hay proveedores activos"} />
                </SelectTrigger>
                <SelectContent>
                  {proveedores.map((p) => (
                    <SelectItem key={p.id} value={String(p.id)}>{p.nombre}</SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
            <div className="space-y-2">
              <Label htmlFor="pedido-nombre">Nombre</Label>
              <Input id="pedido-nombre" value={nombre} placeholder="Ej.: Novedades de agronomía, marzo"
                     onChange={(e) => setNombre(e.target.value)} />
            </div>
            {sedes.length > 1 && (
              <div className="space-y-2">
                <Label htmlFor="pedido-sede">Se entrega en</Label>
                <Select value={sede || (sedeId ? String(sedeId) : "")} onValueChange={setSede}>
                  <SelectTrigger id="pedido-sede" className="w-full"><SelectValue /></SelectTrigger>
                  <SelectContent>
                    {sedes.map((s) => <SelectItem key={s.id} value={String(s.id)}>{s.nombre}</SelectItem>)}
                  </SelectContent>
                </Select>
              </div>
            )}
            <div className="space-y-2">
              <Label htmlFor="pedido-observaciones">Observaciones</Label>
              <Textarea id="pedido-observaciones" rows={2} value={observaciones}
                        onChange={(e) => setObservaciones(e.target.value)} />
            </div>
          </div>
          <DialogFooter>
            <Button type="button" variant="outline" onClick={() => onOpenChange(false)}>Cancelar</Button>
            <Button type="submit" disabled={enviando || !proveedor}>
              {enviando && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}
              Crear pedido
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  )
}
