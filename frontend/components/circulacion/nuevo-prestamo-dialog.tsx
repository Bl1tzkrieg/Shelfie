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

interface NuevoPrestamoDialogProps {
  /** Se invoca tras un préstamo exitoso para refrescar el listado. */
  onSuccess?: () => void
  /** Precarga el código de barras (ej. al prestar desde una ficha del catálogo). */
  codigoBarrasInicial?: string
  trigger?: React.ReactNode
}

export function NuevoPrestamoDialog({
  onSuccess,
  codigoBarrasInicial = "",
  trigger,
}: NuevoPrestamoDialogProps) {
  const [open, setOpen] = useState(false)
  const [enviando, setEnviando] = useState(false)
  const [codigoBarras, setCodigoBarras] = useState(codigoBarrasInicial)
  const [nroCarnet, setNroCarnet] = useState("")

  function reiniciar() {
    setCodigoBarras(codigoBarrasInicial)
    setNroCarnet("")
  }

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault()
    if (enviando) return

    setEnviando(true)
    try {
      await apiPost("/circulation/checkout", {
        codigo_barras: codigoBarras.trim(),
        nro_carnet: nroCarnet.trim(),
      })
      toast.success("Préstamo registrado", {
        description: `${codigoBarras.trim()} entregado a ${nroCarnet.trim()}`,
      })
      setOpen(false)
      reiniciar()
      onSuccess?.()
    } catch (error) {
      toast.error("No se pudo registrar el préstamo", {
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
        if (!v) reiniciar()
      }}
    >
      <DialogTrigger asChild>
        {trigger ?? (
          <Button>
            <Plus className="mr-2 h-4 w-4" />
            Nuevo Préstamo
          </Button>
        )}
      </DialogTrigger>
      <DialogContent className="sm:max-w-md">
        <form onSubmit={handleSubmit}>
          <DialogHeader>
            <DialogTitle>Registrar préstamo</DialogTitle>
            <DialogDescription>
              El sistema valida disponibilidad, tope de préstamos y multas pendientes
              antes de entregar el ejemplar.
            </DialogDescription>
          </DialogHeader>

          <div className="space-y-4 py-4">
            <div className="space-y-2">
              <Label htmlFor="prestamo-carnet">Carnet del lector</Label>
              <Input
                id="prestamo-carnet"
                value={nroCarnet}
                onChange={(e) => setNroCarnet(e.target.value)}
                placeholder="20260001"
                required
                autoFocus
              />
            </div>
            <div className="space-y-2">
              <Label htmlFor="prestamo-barcode">Código de barras del ejemplar</Label>
              <Input
                id="prestamo-barcode"
                value={codigoBarras}
                onChange={(e) => setCodigoBarras(e.target.value)}
                placeholder="SHELFIE-001"
                required
              />
            </div>
          </div>

          <DialogFooter>
            <Button
              type="button"
              variant="outline"
              onClick={() => setOpen(false)}
              disabled={enviando}
            >
              Cancelar
            </Button>
            <Button type="submit" disabled={enviando || !codigoBarras.trim() || !nroCarnet.trim()}>
              {enviando && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}
              Registrar préstamo
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  )
}
