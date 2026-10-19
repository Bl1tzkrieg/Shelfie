"use client"

import { useEffect, useState } from "react"
import { Loader2 } from "lucide-react"
import { toast } from "sonner"

import { useLector } from "@/components/opac/lector-provider"
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
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select"
import { apiGet, apiPost, mensajeDeError } from "@/lib/api"
import type { SedePublica } from "@/lib/opac"

interface ReservarDialogProps {
  biblioId: string
  titulo: string
  /** Reservas activas que ya tiene el título: el lector queda detrás. */
  enCola: number
  open: boolean
  onOpenChange: (v: boolean) => void
  onReservado: () => void
}

export function ReservarDialog({ open, onOpenChange, ...resto }: ReservarDialogProps) {
  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-md">
        {open && <Formulario {...resto} onCerrar={() => onOpenChange(false)} />}
      </DialogContent>
    </Dialog>
  )
}

function Formulario({ biblioId, titulo, enCola, onReservado, onCerrar }:
  Omit<ReservarDialogProps, "open" | "onOpenChange"> & { onCerrar: () => void }) {
  const { lector, recargar } = useLector()
  const [sedes, setSedes] = useState<SedePublica[]>([])
  const [retiro, setRetiro] = useState("")
  const [limite, setLimite] = useState("")
  const [enviando, setEnviando] = useState(false)

  useEffect(() => {
    apiGet<SedePublica[]>("/opac/branches").then((s) => {
      setSedes(s)
      // Se muestra elegida la que usaría la biblioteca: la sede del lector si allí se
      // retira, si no la primera donde se retira (antes decía «tu sede habitual» aunque no lo fuera).
      const propia = s.find((x) => x.nombre === lector?.sede)
      const primera = [...s].sort((a, b) => a.id - b.id)[0]
      const elegida = propia ?? primera
      if (elegida) setRetiro(String(elegida.id))
    }).catch(() => setSedes([]))
  }, [lector?.sede])

  async function reservar(e: React.FormEvent) {
    e.preventDefault()
    setEnviando(true)
    try {
      const r = await apiPost<{ mensaje: string }>("/opac/account/holds", {
        biblio_id: Number(biblioId),
        biblioteca_retiro_id: retiro ? Number(retiro) : null,
        fecha_limite: limite || null,
      })
      toast.success(r.mensaje, { description: "Sigue su estado en Mi cuenta, pestaña Reservas." })
      await recargar()
      onReservado()
      onCerrar()
    } catch (error) {
      toast.error("No se pudo reservar", { description: mensajeDeError(error) })
      setEnviando(false)
    }
  }

  return (
    <form onSubmit={reservar}>
      <DialogHeader>
        <DialogTitle>Reservar</DialogTitle>
        <DialogDescription>
          {titulo}
          {enCola > 0 && ` · ${enCola} persona${enCola === 1 ? "" : "s"} antes que tú`}
        </DialogDescription>
      </DialogHeader>
      <div className="space-y-4 py-4">
        {sedes.length > 1 && (
          <div className="space-y-2">
            <Label htmlFor="reserva-sede">¿Dónde lo retiras?</Label>
            <Select value={retiro} onValueChange={setRetiro}>
              <SelectTrigger id="reserva-sede" className="w-full">
                <SelectValue placeholder="Elige una sede" />
              </SelectTrigger>
              <SelectContent>
                {sedes.map((s) => (
                  <SelectItem key={s.id} value={String(s.id)}>{s.nombre}</SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>
        )}
        <div className="space-y-2">
          <Label htmlFor="reserva-limite">No lo necesito después del (opcional)</Label>
          <Input id="reserva-limite" type="date" value={limite} onChange={(e) => setLimite(e.target.value)} />
          <p className="text-xs text-muted-foreground">Si para esa fecha no llegó, la reserva se cancela sola.</p>
        </div>
      </div>
      <DialogFooter>
        <Button type="button" variant="outline" onClick={onCerrar}>Cancelar</Button>
        <Button type="submit" disabled={enviando}>
          {enviando && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}
          Reservar
        </Button>
      </DialogFooter>
    </form>
  )
}
