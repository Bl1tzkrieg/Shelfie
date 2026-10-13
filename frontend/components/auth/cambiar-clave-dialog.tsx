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

export const MINIMO_CLAVE = 8

/**
 * Cambio de la propia contraseña. Las demás sesiones abiertas se cierran.
 * `ruta`: la de la intranet o la de la cuenta del lector en el OPAC.
 */
export function CambiarClaveDialog({ open, onOpenChange, ruta = "/auth/password" }:
  { open: boolean; onOpenChange: (v: boolean) => void; ruta?: string }) {
  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-sm">
        {open && <Formulario ruta={ruta} onListo={() => onOpenChange(false)} />}
      </DialogContent>
    </Dialog>
  )
}

function Formulario({ ruta, onListo }: { ruta: string; onListo: () => void }) {
  const [actual, setActual] = useState("")
  const [nueva, setNueva] = useState("")
  const [repetida, setRepetida] = useState("")
  const [enviando, setEnviando] = useState(false)
  const coinciden = nueva === repetida
  const valida = actual !== "" && nueva.length >= MINIMO_CLAVE && coinciden

  async function guardar(e: React.FormEvent) {
    e.preventDefault()
    setEnviando(true)
    try {
      await apiPost(ruta, { actual, nueva })
      toast.success("Contraseña cambiada", { description: "Las otras sesiones abiertas se cerraron." })
      onListo()
    } catch (error) {
      toast.error("No se pudo cambiar", { description: mensajeDeError(error) })
    } finally {
      setEnviando(false)
    }
  }

  return (
    <form onSubmit={guardar}>
      <DialogHeader>
        <DialogTitle>Cambiar contraseña</DialogTitle>
        <DialogDescription>Al menos {MINIMO_CLAVE} caracteres, distinta del carnet.</DialogDescription>
      </DialogHeader>
      <div className="space-y-4 py-4">
        <div className="space-y-2">
          <Label htmlFor="clave-actual">Contraseña actual</Label>
          <Input id="clave-actual" type="password" autoComplete="current-password" required autoFocus
                 value={actual} onChange={(e) => setActual(e.target.value)} />
        </div>
        <div className="space-y-2">
          <Label htmlFor="clave-nueva">Contraseña nueva</Label>
          <Input id="clave-nueva" type="password" autoComplete="new-password" required minLength={MINIMO_CLAVE}
                 value={nueva} onChange={(e) => setNueva(e.target.value)} />
        </div>
        <div className="space-y-2">
          <Label htmlFor="clave-repetida">Repite la nueva</Label>
          <Input id="clave-repetida" type="password" autoComplete="new-password" required
                 value={repetida} onChange={(e) => setRepetida(e.target.value)}
                 aria-invalid={repetida !== "" && !coinciden} aria-describedby="clave-repetida-ayuda" />
          {repetida !== "" && !coinciden && (
            <p id="clave-repetida-ayuda" className="text-xs text-destructive">No coincide con la nueva.</p>
          )}
        </div>
      </div>
      <DialogFooter>
        <Button type="button" variant="outline" onClick={onListo}>Cancelar</Button>
        <Button type="submit" disabled={enviando || !valida}>
          {enviando && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}
          Cambiar
        </Button>
      </DialogFooter>
    </form>
  )
}
