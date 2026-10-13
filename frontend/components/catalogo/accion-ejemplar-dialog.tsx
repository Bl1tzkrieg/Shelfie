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
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select"
import { useSedes } from "@/components/layout/sede-provider"
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
  // Vacío: la sede del lector (lo decide el backend).
  const [retiro, setRetiro] = useState("")
  const [limite, setLimite] = useState("")
  const [enviando, setEnviando] = useState(false)
  const { sedes } = useSedes()
  const puntosDeRetiro = sedes.filter((s) => s.punto_retiro)

  function limpiar() {
    setNroCarnet("")
    setRetiro("")
    setLimite("")
  }

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
          biblioteca_retiro_id: retiro ? Number(retiro) : null,
          fecha_limite: limite || null,
        })
        toast.success("Reserva registrada", { description: res.mensaje })
      }
      limpiar()
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
          limpiar()
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
                  El lector entra en la cola de <strong>{titulo}</strong>. Se le aparta el
                  primer ejemplar que se devuelva o que se saque del estante.
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
            {!esPrestamo && (
              <div className="grid gap-4 pt-2 sm:grid-cols-2">
                {puntosDeRetiro.length > 1 && (
                  <div className="space-y-2">
                    <Label htmlFor="accion-retiro">Retira en</Label>
                    <Select value={retiro} onValueChange={setRetiro}>
                      <SelectTrigger id="accion-retiro" className="w-full">
                        <SelectValue placeholder="Sede del lector" />
                      </SelectTrigger>
                      <SelectContent>
                        {puntosDeRetiro.map((s) => (
                          <SelectItem key={s.id} value={String(s.id)}>
                            {s.nombre}
                          </SelectItem>
                        ))}
                      </SelectContent>
                    </Select>
                  </div>
                )}
                <div className="space-y-2">
                  <Label htmlFor="accion-limite">No lo necesita después del</Label>
                  <Input id="accion-limite" type="date" value={limite}
                         onChange={(e) => setLimite(e.target.value)} />
                </div>
              </div>
            )}
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
