"use client"

import { useState } from "react"
import { Loader2 } from "lucide-react"
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
import { Textarea } from "@/components/ui/textarea"
import { apiPatch, mensajeDeError } from "@/lib/api"
import type { ReservaGestion } from "@/lib/types"

function manana() {
  const d = new Date()
  d.setDate(d.getDate() + 1)
  return d.toLocaleDateString("en-CA")
}

/** Sede de retiro, suspensión, fecha límite y notas de una reserva. */
export function EditarReservaDialog({
  reserva,
  onOpenChange,
  onSaved,
}: {
  reserva: ReservaGestion | null
  onOpenChange: (open: boolean) => void
  onSaved: () => void
}) {
  return (
    <Dialog open={reserva !== null} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-md">
        {reserva && <Formulario reserva={reserva} onSaved={onSaved} onCancel={() => onOpenChange(false)} />}
      </DialogContent>
    </Dialog>
  )
}

function Formulario({
  reserva,
  onSaved,
  onCancel,
}: {
  reserva: ReservaGestion
  onSaved: () => void
  onCancel: () => void
}) {
  const { sedes } = useSedes()
  const pendiente = reserva.status === "Pendiente"
  const puntos = sedes.filter((s) => s.punto_retiro || s.id === reserva.pickupBranchId)
  const [retiro, setRetiro] = useState(reserva.pickupBranchId ? String(reserva.pickupBranchId) : "")
  const [suspendida, setSuspendida] = useState(reserva.suspended)
  const [hasta, setHasta] = useState(reserva.suspendedUntil ?? "")
  const [limite, setLimite] = useState(reserva.notNeededAfter ?? "")
  const [notas, setNotas] = useState(reserva.notes ?? "")
  const [guardando, setGuardando] = useState(false)

  async function guardar(e: React.FormEvent) {
    e.preventDefault()
    setGuardando(true)
    const cambios: Record<string, unknown> = { fecha_limite: limite || null, notas }
    if (pendiente) {
      cambios.suspendida = suspendida
      cambios.suspendida_hasta = suspendida && hasta ? hasta : null
      if (retiro && Number(retiro) !== reserva.pickupBranchId) {
        cambios.biblioteca_retiro_id = Number(retiro)
      }
    }
    try {
      await apiPatch(`/circulation/holds/${reserva.id}`, cambios)
      toast.success("Reserva actualizada", { description: `${reserva.userName} · ${reserva.title}` })
      onSaved()
    } catch (error) {
      toast.error("No se pudo actualizar la reserva", { description: mensajeDeError(error) })
    } finally {
      setGuardando(false)
    }
  }

  return (
    <form onSubmit={guardar}>
      <DialogHeader>
        <DialogTitle>Editar reserva</DialogTitle>
        <DialogDescription>
          {reserva.userName} ({reserva.userId}) · {reserva.title}
        </DialogDescription>
      </DialogHeader>
      <div className="space-y-4 py-4">
        {puntos.length > 1 && (
          <div className="space-y-2">
            <Label htmlFor="reserva-retiro">Sede de retiro</Label>
            <Select value={retiro} onValueChange={setRetiro} disabled={!pendiente}>
              <SelectTrigger id="reserva-retiro" className="w-full">
                <SelectValue placeholder="Sin sede" />
              </SelectTrigger>
              <SelectContent>
                {puntos.map((s) => (
                  <SelectItem key={s.id} value={String(s.id)}>
                    {s.nombre}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
            {!pendiente && (
              <p className="text-xs text-muted-foreground">
                Ya tiene un ejemplar asignado: la sede no se puede cambiar.
              </p>
            )}
          </div>
        )}

        <div className="space-y-3 rounded-lg border border-border p-3">
          <div className="flex items-start gap-3">
            <Switch id="reserva-suspendida" checked={suspendida} onCheckedChange={setSuspendida}
                    disabled={!pendiente} />
            <div className="space-y-1">
              <Label htmlFor="reserva-suspendida">Suspendida</Label>
              <p className="text-xs text-muted-foreground">
                Conserva su turno, pero no se le aparta ningún ejemplar mientras tanto.
              </p>
            </div>
          </div>
          {suspendida && (
            <div className="space-y-2 pl-12">
              <Label htmlFor="reserva-hasta">Reanudar el</Label>
              <Input id="reserva-hasta" type="date" min={manana()} value={hasta}
                     onChange={(e) => setHasta(e.target.value)} disabled={!pendiente} />
              <p className="text-xs text-muted-foreground">Vacío: hasta reanudarla a mano.</p>
            </div>
          )}
        </div>

        <div className="space-y-2">
          <Label htmlFor="reserva-limite">No la necesita después del</Label>
          <Input id="reserva-limite" type="date" value={limite}
                 onChange={(e) => setLimite(e.target.value)} />
          <p className="text-xs text-muted-foreground">
            Si sigue pendiente pasada esa fecha, expira sola.
          </p>
        </div>

        <div className="space-y-2">
          <Label htmlFor="reserva-notas">Notas</Label>
          <Textarea id="reserva-notas" rows={2} maxLength={500} value={notas}
                    onChange={(e) => setNotas(e.target.value)} />
        </div>
      </div>
      <DialogFooter>
        <Button type="button" variant="outline" onClick={onCancel}>
          Cancelar
        </Button>
        <Button type="submit" disabled={guardando}>
          {guardando && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}
          Guardar
        </Button>
      </DialogFooter>
    </form>
  )
}
