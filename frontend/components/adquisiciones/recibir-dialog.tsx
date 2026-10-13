"use client"

import { useEffect, useState } from "react"
import { Loader2, PackageCheck } from "lucide-react"
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
import type { Factura, LineaPedido, OpcionesRegla, ResultadoRecepcion } from "@/lib/types"
import { bs } from "./comun"

const NUEVA = "nueva"

function hoyIso() {
  return new Date().toLocaleDateString("en-CA")
}

/**
 * Recibir unidades de una línea contra una factura. Desde la factura, esa factura
 * viene dada; desde el pedido se elige una abierta del proveedor o se crea en el acto.
 */
export function RecibirDialog({
  linea,
  proveedorId,
  facturaId,
  onOpenChange,
  onRecibido,
}: {
  linea: LineaPedido | null
  proveedorId: number
  facturaId?: number
  onOpenChange: (open: boolean) => void
  onRecibido: (r: ResultadoRecepcion) => void
}) {
  return (
    <Dialog open={linea !== null} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-lg">
        {linea && (
          <Formulario linea={linea} proveedorId={proveedorId} facturaId={facturaId}
                      onCancel={() => onOpenChange(false)} onRecibido={onRecibido} />
        )}
      </DialogContent>
    </Dialog>
  )
}

function Formulario({
  linea,
  proveedorId,
  facturaId,
  onCancel,
  onRecibido,
}: {
  linea: LineaPedido
  proveedorId: number
  facturaId?: number
  onCancel: () => void
  onRecibido: (r: ResultadoRecepcion) => void
}) {
  const { sedes } = useSedes()
  const [facturas, setFacturas] = useState<Factura[]>([])
  const [tipos, setTipos] = useState<OpcionesRegla["tipos_item"]>([])
  const [factura, setFactura] = useState<string>(facturaId ? String(facturaId) : "")
  const [numero, setNumero] = useState("")
  const [fecha, setFecha] = useState(hoyIso())
  const [cantidad, setCantidad] = useState(String(linea.pendiente))
  const [costo, setCosto] = useState(String(linea.costo_estimado))
  const [tipo, setTipo] = useState("LIB")
  const [sede, setSede] = useState(
    linea.biblioteca_entrega_id ? String(linea.biblioteca_entrega_id) : "",
  )
  const [signatura, setSignatura] = useState("")
  const [codigos, setCodigos] = useState("")
  const [enviando, setEnviando] = useState(false)

  useEffect(() => {
    apiGet<OpcionesRegla>("/circulation-rules/options")
      .then((o) => setTipos(o.tipos_item))
      .catch(() => setTipos([]))
    if (facturaId) return
    apiGet<Factura[]>(`/acquisitions/invoices?proveedor_id=${proveedorId}&abiertas=true`)
      .then((f) => {
        setFacturas(f)
        setFactura(f.length ? String(f[0].id) : NUEVA)
      })
      .catch(() => setFactura(NUEVA))
  }, [facturaId, proveedorId])

  const listaCodigos = codigos.split(/[\s,;]+/).map((c) => c.trim()).filter(Boolean)
  const n = Number(cantidad)
  const cantidadValida = Number.isInteger(n) && n >= 1 && n <= linea.pendiente
  const codigosValidos = listaCodigos.length === 0 || listaCodigos.length === n

  async function recibir(e: React.FormEvent) {
    e.preventDefault()
    setEnviando(true)
    try {
      let id = factura
      if (id === NUEVA) {
        const nueva = await apiPost<Factura>("/acquisitions/invoices", {
          proveedor_id: proveedorId,
          numero: numero.trim(),
          fecha,
        })
        id = String(nueva.id)
        setFacturas((f) => [nueva, ...f])
        setFactura(id)
      }
      const r = await apiPost<ResultadoRecepcion>(`/acquisitions/invoices/${id}/receive`, {
        linea_id: linea.id,
        cantidad: n,
        costo_unitario: Number(costo),
        tipo_item_codigo: tipo,
        biblioteca_id: sede ? Number(sede) : null,
        signatura: signatura.trim() || null,
        codigos_barras: listaCodigos.length ? listaCodigos : null,
      })
      const apartados = r.ejemplares.filter((x) => x.accion !== "disponible")
      toast.success(`Recibido: ${r.cantidad} de ${linea.titulo}`, {
        description:
          r.ejemplares.map((x) => x.codigo_barras).join(", ") +
          (apartados.length
            ? `. ${apartados.length} ejemplar(es) van a reservas: ${apartados
                .map((x) => `${x.codigo_barras} → ${x.reserva?.lector ?? x.traslado?.hacia}`)
                .join("; ")}.`
            : "."),
        duration: apartados.length ? 12000 : undefined,
      })
      onRecibido(r)
    } catch (error) {
      toast.error("No se pudo recibir", { description: mensajeDeError(error) })
    } finally {
      setEnviando(false)
    }
  }

  return (
    <form onSubmit={recibir}>
      <DialogHeader>
        <DialogTitle>Recibir</DialogTitle>
        <DialogDescription>
          {linea.titulo} · faltan {linea.pendiente} de {linea.cantidad} · estimado {bs(linea.costo_estimado)} c/u
        </DialogDescription>
      </DialogHeader>
      <div className="grid gap-4 py-4 sm:grid-cols-2">
        {!facturaId && (
          <div className="space-y-2 sm:col-span-2">
            <Label htmlFor="recibir-factura">Factura</Label>
            <Select value={factura} onValueChange={setFactura}>
              <SelectTrigger id="recibir-factura" className="w-full">
                <SelectValue placeholder="Elige la factura" />
              </SelectTrigger>
              <SelectContent>
                {facturas.map((f) => (
                  <SelectItem key={f.id} value={String(f.id)}>
                    {f.numero} · {f.fecha} · {bs(f.total)}
                  </SelectItem>
                ))}
                <SelectItem value={NUEVA}>Nueva factura…</SelectItem>
              </SelectContent>
            </Select>
          </div>
        )}
        {factura === NUEVA && (
          <>
            <div className="space-y-2">
              <Label htmlFor="recibir-numero">Número de factura</Label>
              <Input id="recibir-numero" required value={numero} onChange={(e) => setNumero(e.target.value)} />
            </div>
            <div className="space-y-2">
              <Label htmlFor="recibir-fecha">Fecha</Label>
              <Input id="recibir-fecha" type="date" required value={fecha} onChange={(e) => setFecha(e.target.value)} />
            </div>
          </>
        )}
        <div className="space-y-2">
          <Label htmlFor="recibir-cantidad">Cantidad</Label>
          <Input id="recibir-cantidad" type="number" min={1} max={linea.pendiente} required
                 value={cantidad} onChange={(e) => setCantidad(e.target.value)} />
        </div>
        <div className="space-y-2">
          <Label htmlFor="recibir-costo">Costo real por unidad (Bs.)</Label>
          <Input id="recibir-costo" type="number" min={0} step="0.01" required
                 value={costo} onChange={(e) => setCosto(e.target.value)} />
        </div>
        <div className="space-y-2">
          <Label htmlFor="recibir-tipo">Tipo de ítem</Label>
          <Select value={tipo} onValueChange={setTipo}>
            <SelectTrigger id="recibir-tipo" className="w-full">
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              {(tipos.length ? tipos : [{ id: 0, codigo: "LIB", nombre: "Libro" }]).map((t) => (
                <SelectItem key={t.codigo} value={t.codigo}>
                  {t.nombre}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        </div>
        {sedes.length > 1 && (
          <div className="space-y-2">
            <Label htmlFor="recibir-sede">Sede</Label>
            <Select value={sede} onValueChange={setSede}>
              <SelectTrigger id="recibir-sede" className="w-full">
                <SelectValue placeholder="La del pedido" />
              </SelectTrigger>
              <SelectContent>
                {sedes.map((s) => (
                  <SelectItem key={s.id} value={String(s.id)}>
                    {s.nombre}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>
        )}
        <div className="space-y-2 sm:col-span-2">
          <Label htmlFor="recibir-signatura">Signatura topográfica</Label>
          <Input id="recibir-signatura" value={signatura} placeholder="Opcional"
                 onChange={(e) => setSignatura(e.target.value)} />
        </div>
        <div className="space-y-2 sm:col-span-2">
          <Label htmlFor="recibir-codigos">Códigos de barras</Label>
          <Textarea id="recibir-codigos" rows={2} value={codigos}
                    placeholder="Vacío: se generan solos. Si no, uno por cada ejemplar."
                    onChange={(e) => setCodigos(e.target.value)}
                    aria-describedby="recibir-codigos-ayuda" />
          <p id="recibir-codigos-ayuda" className={codigosValidos ? "text-xs text-muted-foreground" : "text-xs text-destructive"}>
            {listaCodigos.length
              ? `${listaCodigos.length} código(s) para ${cantidadValida ? n : "?"} ejemplar(es)`
              : "Se generarán con el número de pedido y de línea."}
          </p>
        </div>
      </div>
      <DialogFooter>
        <Button type="button" variant="outline" onClick={onCancel}>
          Cancelar
        </Button>
        <Button type="submit"
                disabled={enviando || !cantidadValida || !codigosValidos || !factura ||
                          (factura === NUEVA && !numero.trim())}>
          {enviando ? <Loader2 className="mr-2 h-4 w-4 animate-spin" /> : <PackageCheck className="mr-2 h-4 w-4" />}
          Recibir
        </Button>
      </DialogFooter>
    </form>
  )
}
