"use client"

import { useState } from "react"
import { Plus, Loader2 } from "lucide-react"
import { toast } from "sonner"

import { Button } from "@/components/ui/button"
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from "@/components/ui/dialog"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { apiPost, mensajeDeError } from "@/lib/api"

interface AgregarMaterialDialogProps {
  onSuccess?: () => void
}

const VACIO = {
  titulo: "",
  autor: "",
  isbn: "",
  ano_publicacion: "",
  materia: "",
  codigo_barras: "",
  signatura_topografica: "",
}

export function AgregarMaterialDialog({ onSuccess }: AgregarMaterialDialogProps) {
  const [open, setOpen] = useState(false)
  const [enviando, setEnviando] = useState(false)
  const [form, setForm] = useState(VACIO)

  function set(campo: keyof typeof VACIO, valor: string) {
    setForm((f) => ({ ...f, [campo]: valor }))
  }

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault()
    if (enviando) return

    setEnviando(true)
    try {
      await apiPost("/catalog/items", {
        titulo: form.titulo.trim(),
        autor: form.autor.trim() || null,
        isbn: form.isbn.trim() || null,
        ano_publicacion: form.ano_publicacion ? Number(form.ano_publicacion) : null,
        materia: form.materia.trim() || null,
        codigo_barras: form.codigo_barras.trim(),
        signatura_topografica: form.signatura_topografica.trim() || null,
      })
      toast.success("Material catalogado", { description: form.titulo.trim() })
      setOpen(false)
      setForm(VACIO)
      onSuccess?.()
    } catch (error) {
      toast.error("No se pudo catalogar el material", {
        description: mensajeDeError(error),
      })
    } finally {
      setEnviando(false)
    }
  }

  return (
    <Dialog
      open={open}
      onOpenChange={(v) => {
        setOpen(v)
        if (!v) setForm(VACIO)
      }}
    >
      <DialogTrigger asChild>
        <Button className="shrink-0">
          <Plus className="mr-2 h-4 w-4" />
          Agregar Material
        </Button>
      </DialogTrigger>
      <DialogContent className="sm:max-w-lg">
        <form onSubmit={handleSubmit}>
          <DialogHeader>
            <DialogTitle>Catalogar material</DialogTitle>
            <DialogDescription>
              Si el ISBN ya existe en el catálogo, el ejemplar se suma al título existente
              en lugar de duplicarlo.
            </DialogDescription>
          </DialogHeader>

          <div className="grid gap-4 py-4 sm:grid-cols-2">
            <div className="space-y-2 sm:col-span-2">
              <Label htmlFor="mat-titulo">Título *</Label>
              <Input
                id="mat-titulo"
                value={form.titulo}
                onChange={(e) => set("titulo", e.target.value)}
                required
                autoFocus
              />
            </div>
            <div className="space-y-2">
              <Label htmlFor="mat-autor">Autor</Label>
              <Input
                id="mat-autor"
                value={form.autor}
                onChange={(e) => set("autor", e.target.value)}
              />
            </div>
            <div className="space-y-2">
              <Label htmlFor="mat-isbn">ISBN</Label>
              <Input
                id="mat-isbn"
                value={form.isbn}
                onChange={(e) => set("isbn", e.target.value)}
              />
            </div>
            <div className="space-y-2">
              <Label htmlFor="mat-ano">Año de publicación</Label>
              <Input
                id="mat-ano"
                type="number"
                value={form.ano_publicacion}
                onChange={(e) => set("ano_publicacion", e.target.value)}
              />
            </div>
            <div className="space-y-2">
              <Label htmlFor="mat-materia">Materia</Label>
              <Input
                id="mat-materia"
                value={form.materia}
                onChange={(e) => set("materia", e.target.value)}
                placeholder="Fitotecnia"
              />
            </div>
            <div className="space-y-2">
              <Label htmlFor="mat-barcode">Código de barras *</Label>
              <Input
                id="mat-barcode"
                value={form.codigo_barras}
                onChange={(e) => set("codigo_barras", e.target.value)}
                placeholder="SHELFIE-007"
                required
              />
            </div>
            <div className="space-y-2">
              <Label htmlFor="mat-signatura">Signatura topográfica</Label>
              <Input
                id="mat-signatura"
                value={form.signatura_topografica}
                onChange={(e) => set("signatura_topografica", e.target.value)}
                placeholder="S619 L84"
              />
            </div>
          </div>

          <DialogFooter>
            <Button type="button" variant="outline" onClick={() => setOpen(false)} disabled={enviando}>
              Cancelar
            </Button>
            <Button
              type="submit"
              disabled={enviando || !form.titulo.trim() || !form.codigo_barras.trim()}
            >
              {enviando && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}
              Catalogar
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  )
}
