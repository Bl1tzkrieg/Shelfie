"use client"

import { useEffect, useState } from "react"
import { Loader2, Save, Trash2 } from "lucide-react"
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
import { Switch } from "@/components/ui/switch"
import { apiDelete, apiGet, apiPatch, mensajeDeError } from "@/lib/api"
import type { Ejemplar, OpcionesRegla } from "@/lib/types"

/** Estados que maneja la circulación: mientras el ejemplar esté así, no se da de baja. */
const EN_CIRCULACION = ["Prestado", "Reservado", "EnTransito"]

interface Props {
  biblioId: string
  ejemplar: Ejemplar | null
  onClose: () => void
  onSuccess: () => void
}

/** Corregir un ejemplar, darlo de baja (Retirado) o borrarlo si se cargó por error. */
export function EditarEjemplarDialog({ ejemplar, onClose, ...props }: Props) {
  return (
    <Dialog open={ejemplar !== null} onOpenChange={(abierto) => !abierto && onClose()}>
      <DialogContent className="sm:max-w-md">
        {ejemplar && <Formulario key={ejemplar.id} ejemplar={ejemplar} onClose={onClose} {...props} />}
      </DialogContent>
    </Dialog>
  )
}

function Formulario({ biblioId, ejemplar, onClose, onSuccess }: Props & { ejemplar: Ejemplar }) {
  const { sedes } = useSedes()
  const [tipos, setTipos] = useState<OpcionesRegla["tipos_item"]>([])
  const [form, setForm] = useState({
    codigo_barras: ejemplar.barcode,
    tipo: ejemplar.itemType ?? "LIB",
    signatura: ejemplar.location ?? "",
    enumeracion: ejemplar.enumeration ?? "",
    precio: ejemplar.price != null ? String(ejemplar.price) : "",
    sede: ejemplar.homeBranchId ? String(ejemplar.homeBranchId) : "",
    retirado: ejemplar.status === "Retirado",
  })
  const [trabajando, setTrabajando] = useState<"guardar" | "eliminar" | null>(null)
  const [confirmarBorrado, setConfirmarBorrado] = useState(false)
  const circulando = EN_CIRCULACION.includes(ejemplar.status)
  const ruta = `/catalog/items/${biblioId}/ejemplares/${ejemplar.id}`

  useEffect(() => {
    apiGet<OpcionesRegla>("/circulation-rules/options")
      .then((o) => setTipos(o.tipos_item))
      .catch(() => setTipos([]))
  }, [])

  async function guardar(e: React.FormEvent) {
    e.preventDefault()
    setTrabajando("guardar")
    try {
      const cambioDeEstado = form.retirado !== (ejemplar.status === "Retirado")
      await apiPatch(ruta, {
        codigo_barras: form.codigo_barras.trim(),
        tipo_item_codigo: form.tipo,
        signatura_topografica: form.signatura.trim() || null,
        enumeracion: form.enumeracion.trim() || null,
        precio_reposicion: form.precio ? Number(form.precio) : null,
        ...(form.sede ? { biblioteca_propia_id: Number(form.sede) } : {}),
        ...(cambioDeEstado ? { estado: form.retirado ? "Retirado" : "Disponible" } : {}),
      })
      toast.success("Ejemplar actualizado", { description: form.codigo_barras.trim() })
      onSuccess()
      onClose()
    } catch (error) {
      toast.error("No se pudo actualizar", { description: mensajeDeError(error) })
    } finally {
      setTrabajando(null)
    }
  }

  async function eliminar() {
    setTrabajando("eliminar")
    try {
      await apiDelete(ruta)
      toast.success("Ejemplar eliminado", { description: ejemplar.barcode })
      onSuccess()
      onClose()
    } catch (error) {
      toast.error("No se pudo eliminar", { description: mensajeDeError(error) })
      setConfirmarBorrado(false)
    } finally {
      setTrabajando(null)
    }
  }

  const set = (campo: keyof typeof form) => (e: React.ChangeEvent<HTMLInputElement>) =>
    setForm((f) => ({ ...f, [campo]: e.target.value }))

  return (
    <form onSubmit={guardar}>
      <DialogHeader>
        <DialogTitle>Editar ejemplar</DialogTitle>
        <DialogDescription>
          {ejemplar.barcode} · {ejemplar.status}
        </DialogDescription>
      </DialogHeader>
      <div className="space-y-4 py-4">
        <div className="grid gap-4 sm:grid-cols-2">
          <div className="space-y-2">
            <Label htmlFor="editar-codigo">Código de barras</Label>
            <Input id="editar-codigo" required autoComplete="off" value={form.codigo_barras}
                   onChange={set("codigo_barras")} />
          </div>
          <div className="space-y-2">
            <Label htmlFor="editar-tipo">Tipo de ítem</Label>
            <Select value={form.tipo} onValueChange={(v) => setForm((f) => ({ ...f, tipo: v }))}>
              <SelectTrigger id="editar-tipo" className="w-full"><SelectValue /></SelectTrigger>
              <SelectContent>
                {(tipos.length ? tipos : [{ id: 0, codigo: form.tipo, nombre: form.tipo }]).map((t) => (
                  <SelectItem key={t.codigo} value={t.codigo}>{t.nombre}</SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>
        </div>
        <div className="grid gap-4 sm:grid-cols-2">
          <div className="space-y-2">
            <Label htmlFor="editar-signatura">Signatura topográfica</Label>
            <Input id="editar-signatura" value={form.signatura} onChange={set("signatura")} />
          </div>
          <div className="space-y-2">
            <Label htmlFor="editar-enumeracion">Numeración</Label>
            <Input id="editar-enumeracion" value={form.enumeracion} placeholder="Vol. 3, Núm. 2"
                   onChange={set("enumeracion")} />
          </div>
        </div>
        <div className="grid gap-4 sm:grid-cols-2">
          {sedes.length > 0 && (
            <div className="space-y-2">
              <Label htmlFor="editar-sede">Sede propia</Label>
              <Select value={form.sede} onValueChange={(v) => setForm((f) => ({ ...f, sede: v }))}>
                <SelectTrigger id="editar-sede" className="w-full"><SelectValue placeholder="Sin sede" /></SelectTrigger>
                <SelectContent>
                  {sedes.map((s) => <SelectItem key={s.id} value={String(s.id)}>{s.nombre}</SelectItem>)}
                </SelectContent>
              </Select>
            </div>
          )}
          <div className="space-y-2">
            <Label htmlFor="editar-precio">Precio de reposición (Bs.)</Label>
            <Input id="editar-precio" type="number" min={0} step="0.01" value={form.precio}
                   placeholder="Por defecto" onChange={set("precio")} />
          </div>
        </div>
        <div className="flex items-start gap-3 rounded-lg border border-border p-3">
          <Switch id="editar-retirado" checked={form.retirado} disabled={circulando}
                  onCheckedChange={(v) => setForm((f) => ({ ...f, retirado: v }))}
                  aria-describedby="editar-retirado-ayuda" />
          <div className="space-y-1">
            <Label htmlFor="editar-retirado">Dado de baja (retirado)</Label>
            <p id="editar-retirado-ayuda" className="text-xs text-muted-foreground">
              {circulando
                ? "Está en circulación: primero hay que devolverlo, cancelar la reserva o recibir el traslado."
                : ejemplar.status === "Perdido" && !form.retirado
                  ? "Si apareció, pásalo por Devoluciones: así se reintegra lo que pagó el lector."
                  : "No se presta ni se puede reservar, pero conserva su historial."}
            </p>
          </div>
        </div>
      </div>
      <DialogFooter className="gap-2 sm:justify-between">
        {confirmarBorrado ? (
          <Button type="button" variant="destructive" disabled={trabajando !== null} onClick={eliminar}>
            {trabajando === "eliminar" && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}
            Sí, eliminar
          </Button>
        ) : (
          <Button type="button" variant="ghost" className="text-destructive" disabled={circulando}
                  title="Solo si se cargó por error: con préstamos en su historial, dalo de baja"
                  onClick={() => setConfirmarBorrado(true)}>
            <Trash2 className="mr-2 h-4 w-4" />
            Eliminar
          </Button>
        )}
        <div className="flex gap-2">
          <Button type="button" variant="outline" onClick={onClose}>Cancelar</Button>
          <Button type="submit" disabled={trabajando !== null || !form.codigo_barras.trim()}>
            {trabajando === "guardar" ? <Loader2 className="mr-2 h-4 w-4 animate-spin" /> : <Save className="mr-2 h-4 w-4" />}
            Guardar
          </Button>
        </div>
      </DialogFooter>
    </form>
  )
}
