"use client"

import { useCallback, useEffect, useState } from "react"
import Link from "next/link"
import { useRouter } from "next/navigation"
import { Loader2, Plus } from "lucide-react"
import { toast } from "sonner"

import { Badge } from "@/components/ui/badge"
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
import { apiGet, apiPost, mensajeDeError } from "@/lib/api"
import type { Factura, Proveedor } from "@/lib/types"
import { bs, fechaCorta, Vacio } from "./comun"

export function FacturasPanel() {
  const [soloAbiertas, setSoloAbiertas] = useState(true)
  const [facturas, setFacturas] = useState<Factura[] | null>(null)
  const [nueva, setNueva] = useState(false)

  const cargar = useCallback(async () => {
    try {
      setFacturas(await apiGet<Factura[]>(`/acquisitions/invoices${soloAbiertas ? "?abiertas=true" : ""}`))
    } catch (e) {
      toast.error("No se pudieron cargar las facturas", { description: mensajeDeError(e) })
    }
  }, [soloAbiertas])

  useEffect(() => {
    cargar()
  }, [cargar])

  return (
    <div className="space-y-4">
      <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
        <div className="flex gap-1.5" role="group" aria-label="Filtrar facturas">
          <Button size="sm" variant={soloAbiertas ? "default" : "outline"} aria-pressed={soloAbiertas}
                  onClick={() => setSoloAbiertas(true)}>Abiertas</Button>
          <Button size="sm" variant={!soloAbiertas ? "default" : "outline"} aria-pressed={!soloAbiertas}
                  onClick={() => setSoloAbiertas(false)}>Todas</Button>
        </div>
        <Button onClick={() => setNueva(true)}>
          <Plus className="mr-2 h-4 w-4" />
          Recibir un envío
        </Button>
      </div>

      {facturas === null ? (
        <div className="py-12 text-center text-muted-foreground"><Loader2 className="mx-auto h-5 w-5 animate-spin" /></div>
      ) : facturas.length === 0 ? (
        <Vacio>{soloAbiertas ? "No hay facturas abiertas." : "Todavía no se registraron facturas."}</Vacio>
      ) : (
        <div className="overflow-x-auto rounded-lg border bg-card shadow-papel">
          <table className="w-full text-sm">
            <thead className="bg-muted/50 text-left text-muted-foreground">
              <tr>
                <th className="px-4 py-3 font-medium">Factura</th>
                <th className="px-4 py-3 font-medium">Proveedor</th>
                <th className="px-4 py-3 font-medium">Fecha</th>
                <th className="px-4 py-3 text-right font-medium">Ejemplares</th>
                <th className="px-4 py-3 text-right font-medium">Total</th>
                <th className="px-4 py-3 font-medium">Estado</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-border">
              {facturas.map((f) => (
                <tr key={f.id} className="hover:bg-muted/30">
                  <td className="px-4 py-3">
                    <Link href={`/adquisiciones/facturas/${f.id}`} className="font-medium text-foreground hover:underline">
                      {f.numero}
                    </Link>
                  </td>
                  <td className="px-4 py-3">{f.proveedor_nombre}</td>
                  <td className="px-4 py-3">{fechaCorta(f.fecha)}</td>
                  <td className="px-4 py-3 text-right tabular-nums">{f.unidades}</td>
                  <td className="px-4 py-3 text-right tabular-nums">{bs(f.total)}</td>
                  <td className="px-4 py-3">
                    {f.cerrada ? <Badge variant="outline">Cerrada</Badge> : <Badge variant="secondary">Abierta</Badge>}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      <NuevaFacturaDialog open={nueva} onOpenChange={setNueva} />
    </div>
  )
}

/** Recibir un envío = registrar su factura y luego recibir contra ella. */
function NuevaFacturaDialog({ open, onOpenChange }: { open: boolean; onOpenChange: (v: boolean) => void }) {
  const router = useRouter()
  const [proveedores, setProveedores] = useState<Proveedor[]>([])
  const [proveedor, setProveedor] = useState("")
  const [numero, setNumero] = useState("")
  const [fecha, setFecha] = useState(() => new Date().toLocaleDateString("en-CA"))
  const [enviando, setEnviando] = useState(false)

  useEffect(() => {
    if (!open) return
    apiGet<Proveedor[]>("/acquisitions/suppliers").then(setProveedores).catch(() => setProveedores([]))
  }, [open])

  async function crear(e: React.FormEvent) {
    e.preventDefault()
    setEnviando(true)
    try {
      const f = await apiPost<Factura>("/acquisitions/invoices", {
        proveedor_id: Number(proveedor),
        numero: numero.trim(),
        fecha,
      })
      router.push(`/adquisiciones/facturas/${f.id}`)
    } catch (error) {
      toast.error("No se pudo registrar la factura", { description: mensajeDeError(error) })
      setEnviando(false)
    }
  }

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-md">
        <form onSubmit={crear}>
          <DialogHeader>
            <DialogTitle>Recibir un envío</DialogTitle>
            <DialogDescription>
              Registra la factura que vino con el envío; después recibes contra ella lo que llegó.
            </DialogDescription>
          </DialogHeader>
          <div className="space-y-4 py-4">
            <div className="space-y-2">
              <Label htmlFor="factura-proveedor">Proveedor</Label>
              <Select value={proveedor} onValueChange={setProveedor}>
                <SelectTrigger id="factura-proveedor" className="w-full">
                  <SelectValue placeholder="Elige el proveedor" />
                </SelectTrigger>
                <SelectContent>
                  {proveedores.map((p) => (
                    <SelectItem key={p.id} value={String(p.id)}>
                      {p.nombre}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
            <div className="grid gap-4 sm:grid-cols-2">
              <div className="space-y-2">
                <Label htmlFor="factura-numero">Número de factura</Label>
                <Input id="factura-numero" required value={numero} onChange={(e) => setNumero(e.target.value)} />
              </div>
              <div className="space-y-2">
                <Label htmlFor="factura-fecha">Fecha</Label>
                <Input id="factura-fecha" type="date" required value={fecha} onChange={(e) => setFecha(e.target.value)} />
              </div>
            </div>
          </div>
          <DialogFooter>
            <Button type="button" variant="outline" onClick={() => onOpenChange(false)}>Cancelar</Button>
            <Button type="submit" disabled={enviando || !proveedor || !numero.trim()}>
              {enviando && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}
              Continuar
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  )
}
