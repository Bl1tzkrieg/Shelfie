"use client"

import { useState } from "react"
import { Loader2 } from "lucide-react"
import { toast } from "sonner"

import { MINIMO_CLAVE } from "@/components/auth/cambiar-clave-dialog"
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

/** Fija una contraseña nueva a otra persona (la olvidó). Cierra sus sesiones abiertas. */
export function RestablecerClaveDialog({
  carnet,
  nombre,
  open,
  onOpenChange,
}: {
  carnet: string
  nombre: string
  open: boolean
  onOpenChange: (v: boolean) => void
}) {
  const [nueva, setNueva] = useState("")
  const [enviando, setEnviando] = useState(false)

  async function guardar(e: React.FormEvent) {
    e.preventDefault()
    setEnviando(true)
    try {
      await apiPost(`/users/${encodeURIComponent(carnet)}/password`, { nueva })
      toast.success("Contraseña restablecida", { description: `Comunícasela a ${nombre} por un medio seguro.` })
      setNueva("")
      onOpenChange(false)
    } catch (error) {
      toast.error("No se pudo restablecer", { description: mensajeDeError(error) })
    } finally {
      setEnviando(false)
    }
  }

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-sm">
        <form onSubmit={guardar}>
          <DialogHeader>
            <DialogTitle>Restablecer contraseña</DialogTitle>
            <DialogDescription>
              {nombre} ({carnet}). Sus sesiones abiertas se cierran.
            </DialogDescription>
          </DialogHeader>
          <div className="space-y-2 py-4">
            <Label htmlFor="clave-restablecer">Contraseña nueva</Label>
            <Input id="clave-restablecer" type="text" autoComplete="off" required minLength={MINIMO_CLAVE}
                   value={nueva} onChange={(e) => setNueva(e.target.value)} />
            <p className="text-xs text-muted-foreground">Al menos {MINIMO_CLAVE} caracteres, distinta del carnet.</p>
          </div>
          <DialogFooter>
            <Button type="button" variant="outline" onClick={() => onOpenChange(false)}>Cancelar</Button>
            <Button type="submit" disabled={enviando || nueva.length < MINIMO_CLAVE}>
              {enviando && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}
              Restablecer
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  )
}
