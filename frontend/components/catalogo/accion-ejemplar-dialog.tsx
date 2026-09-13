"use client"

import { useState } from "react"
import { Loader2 } from "lucide-react"
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
import { apiPost, mensajeDeError } from "@/lib/api"

export type AccionEjemplar = "prestar" | "reservar"

interface AccionEjemplarDialogProps {
  accion: AccionEjemplar | null
  titulo: string
  biblioId: string
  /** Código de barras del primer ejemplar libre; requerido para prestar. */
  codigoBarras?: string | null
  onClose: () => void
  onSuccess?: () => void
}

/**
 * Diálogo compartido por "Prestar" y "Reservar": ambos solo necesitan el carnet
 * del lector, y cambian el endpoint al que envían.
 */
export function AccionEjemplarDialog({
  accion,
  titulo,
  biblioId,
  codigoBarras,
  onClose,
  onSuccess,
}: AccionEjemplarDialogProps) {
  const [nroCarnet, setNroCarnet] = useState("")
  const [enviando, setEnviando] = useState(false)

  const esPrestamo = accion === "prestar"

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault()
    if (enviando || !accion) return

    setEnviando(true)
    try {
      if (esPrestamo) {
        await apiPost("/circulation/checkout", {
          codigo_barras: codigoBarras,
          nro_carnet: nroCarnet.trim(),
        })
        toast.success("Préstamo registrado", { description: titulo })
      } else {
        const res = await apiPost<{ mensaje: string }>("/catalog/reservations", {
          biblio_id: Number(biblioId),
          nro_carnet: nroCarnet.trim(),
        })
        toast.success("Reserva registrada", { description: res.mensaje })
      }
      setNroCarnet("")
      onClose()
      onSuccess?.()
    } catch (error) {
      toast.error(
        esPrestamo ? "No se pudo prestar" : "No se pudo reservar",
        { description: mensajeDeError(error) }
      )
    } finally {
      setEnviando(false)
    }
  }

  return (
    <Dialog
      open={accion !== null}
      onOpenChange={(v) => {
        if (!v) {
          setNroCarnet("")
          onClose()
        }
      }}
    >
      <DialogContent className="sm:max-w-md">
        <form onSubmit={handleSubmit}>
          <DialogHeader>
            <DialogTitle>{esPrestamo ? "Prestar ejemplar" : "Reservar título"}</DialogTitle>
            <DialogDescription>
              {esPrestamo ? (
                <>
                  Se entregará <strong>{titulo}</strong>
                  {codigoBarras ? ` (${codigoBarras})` : ""}.
                </>
              ) : (
                <>
                  No hay ejemplares libres de <strong>{titulo}</strong>. El lector quedará
                  en la cola y se le asignará el ejemplar cuando se devuelva.
                </>
              )}
            </DialogDescription>
          </DialogHeader>

          <div className="space-y-2 py-4">
            <Label htmlFor="accion-carnet">Carnet del lector</Label>
            <Input
              id="accion-carnet"
              value={nroCarnet}
              onChange={(e) => setNroCarnet(e.target.value)}
              placeholder="20260001"
              required
              autoFocus
            />
          </div>

          <DialogFooter>
            <Button type="button" variant="outline" onClick={onClose} disabled={enviando}>
              Cancelar
            </Button>
            <Button type="submit" disabled={enviando || !nroCarnet.trim()}>
              {enviando && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}
              {esPrestamo ? "Prestar" : "Reservar"}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  )
}
