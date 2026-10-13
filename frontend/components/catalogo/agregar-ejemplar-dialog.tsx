"use client"

import { useEffect, useState } from "react"
import { Loader2, Plus } from "lucide-react"
import { toast } from "sonner"

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
import type { OpcionesRegla } from "@/lib/types"

interface AgregarEjemplarDialogProps {
  biblioId: string
  titulo: string
  open: boolean
  onOpenChange: (open: boolean) => void
  onSuccess: () => void
}

/** Un ejemplar más para un título ya catalogado. */
export function AgregarEjemplarDialog({ open, onOpenChange, ...props }: AgregarEjemplarDialogProps) {
  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-md">
        {open && <Formulario {...props} onClose={() => onOpenChange(false)} />}
      </DialogContent>
    </Dialog>
  )
}

function Formulario({
  biblioId,
  titulo,
  onClose,
  onSuccess,
}: Omit<AgregarEjemplarDialogProps, "open" | "onOpenChange"> & { onClose: () => void }) {
  const [tipos, setTipos] = useState<OpcionesRegla["tipos_item"]>([])
  const [form, setForm] = useState({ codigo_barras: "", tipo: "LIB", signatura: "", precio: "" })
  const [enviando, setEnviando] = useState(false)
  // Tras guardar, el formulario queda listo para el siguiente (varias copias seguidas).
  const [agregados, setAgregados] = useState(0)

  useEffect(() => {
    apiGet<OpcionesRegla>("/circulation-rules/options")
      .then((o) => setTipos(o.tipos_item))
      .catch(() => setTipos([]))
  }, [])

  async function guardar(e: React.FormEvent) {
    e.preventDefault()
    setEnviando(true)
    try {
      await apiPost(`/catalog/items/${biblioId}/ejemplares`, {
        codigo_barras: form.codigo_barras.trim(),
        tipo_item_codigo: form.tipo,
        signatura_topografica: form.signatura.trim() || null,
        precio_reposicion: form.precio ? Number(form.precio) : null,
      })
      toast.success("Ejemplar agregado", { description: form.codigo_barras.trim() })
      setAgregados((n) => n + 1)
      setForm((f) => ({ ...f, codigo_barras: "" }))
      onSuccess()
    } catch (error) {
      toast.error("No se pudo agregar el ejemplar", { description: mensajeDeError(error) })
    } finally {
      setEnviando(false)
    }
  }

  return (
    <form onSubmit={guardar}>
      <DialogHeader>
        <DialogTitle>Agregar ejemplar</DialogTitle>
        <DialogDescription>
          {titulo}
          {agregados > 0 && ` · ${agregados} agregado(s) en esta sesión`}
        </DialogDescription>
      </DialogHeader>
      <div className="space-y-4 py-4">
        <div className="space-y-2">
          <Label htmlFor="ejemplar-codigo">Código de barras</Label>
          <Input id="ejemplar-codigo" required autoFocus autoComplete="off" value={form.codigo_barras}
                 onChange={(e) => setForm((f) => ({ ...f, codigo_barras: e.target.value }))} />
        </div>
        <div className="grid gap-4 sm:grid-cols-2">
          <div className="space-y-2">
            <Label htmlFor="ejemplar-tipo">Tipo de ítem</Label>
            <Select value={form.tipo} onValueChange={(v) => setForm((f) => ({ ...f, tipo: v }))}>
              <SelectTrigger id="ejemplar-tipo" className="w-full">
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
          <div className="space-y-2">
            <Label htmlFor="ejemplar-precio">Precio de reposición (Bs.)</Label>
            <Input id="ejemplar-precio" type="number" min={0} step="0.01" value={form.precio}
                   placeholder="Por defecto"
                   onChange={(e) => setForm((f) => ({ ...f, precio: e.target.value }))} />
          </div>
        </div>
        <div className="space-y-2">
          <Label htmlFor="ejemplar-signatura">Signatura topográfica</Label>
          <Input id="ejemplar-signatura" value={form.signatura} placeholder="630 R6 2024"
                 onChange={(e) => setForm((f) => ({ ...f, signatura: e.target.value }))} />
        </div>
      </div>
      <DialogFooter>
        <Button type="button" variant="outline" onClick={onClose}>
          {agregados > 0 ? "Listo" : "Cancelar"}
        </Button>
        <Button type="submit" disabled={enviando || !form.codigo_barras.trim()}>
          {enviando ? <Loader2 className="mr-2 h-4 w-4 animate-spin" /> : <Plus className="mr-2 h-4 w-4" />}
          Agregar
        </Button>
      </DialogFooter>
    </form>
  )
}
