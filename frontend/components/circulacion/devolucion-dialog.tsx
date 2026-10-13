"use client"

import { useState } from "react"
import { ArrowRight, BookmarkCheck, Library, Loader2, RotateCcw, Truck } from "lucide-react"
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
import type { ResultadoDevolucion } from "@/lib/types"
import { cn } from "@/lib/utils"
import { avisarDevolucion, instruccionDevolucion, type TonoInstruccion } from "./aviso-devolucion"

/**
 * Devolución en mostrador por código de barras, como el checkin de Koha. Sirve
 * igual para un préstamo activo que para un ejemplar declarado perdido que apareció.
 */
export function DevolucionDialog({ onSuccess }: { onSuccess?: () => void }) {
  const [open, setOpen] = useState(false)
  const [codigo, setCodigo] = useState("")
  const [enviando, setEnviando] = useState(false)
  // Lo último escaneado: qué hacer con ese ejemplar, visible mientras se sigue escaneando.
  const [ultimo, setUltimo] = useState<{ codigo: string; res: ResultadoDevolucion } | null>(null)

  async function devolver(e: React.FormEvent) {
    e.preventDefault()
    if (enviando || !codigo.trim()) return
    setEnviando(true)
    try {
      const res = await apiPost<ResultadoDevolucion>("/circulation/checkin", {
        codigo_barras: codigo.trim(),
      })
      avisarDevolucion(res)
      setUltimo({ codigo: codigo.trim(), res })
      // El diálogo queda abierto para seguir escaneando la pila de devoluciones.
      setCodigo("")
      onSuccess?.()
    } catch (error) {
      toast.error("No se pudo registrar la devolución", { description: mensajeDeError(error) })
    } finally {
      setEnviando(false)
    }
  }

  return (
    <Dialog
      open={open}
      onOpenChange={(v) => {
        setOpen(v)
        if (!v) {
          setCodigo("")
          setUltimo(null)
        }
      }}
    >
      <DialogTrigger asChild>
        <Button variant="outline">
          <RotateCcw className="mr-2 h-4 w-4" />
          Devolución
        </Button>
      </DialogTrigger>
      <DialogContent className="sm:max-w-md">
        <form onSubmit={devolver}>
          <DialogHeader>
            <DialogTitle>Registrar devolución</DialogTitle>
            <DialogDescription>
              Escanea o escribe el código del ejemplar. Se cobra la multa si está vencido, se
              aparta si alguien lo reservó (o se envía a su sede de retiro), se reciben los
              traslados y, si estaba declarado perdido, se reintegra la reposición.
            </DialogDescription>
          </DialogHeader>
          <div className="space-y-2 py-4">
            <Label htmlFor="devolucion-codigo">Código de barras</Label>
            <Input
              id="devolucion-codigo"
              value={codigo}
              onChange={(e) => setCodigo(e.target.value)}
              placeholder="SHELFIE-001"
              autoComplete="off"
              autoFocus
              required
            />
            {ultimo && <Instruccion codigo={ultimo.codigo} res={ultimo.res} />}
          </div>
          <DialogFooter>
            <Button type="button" variant="outline" onClick={() => setOpen(false)}>
              Cerrar
            </Button>
            <Button type="submit" disabled={enviando || !codigo.trim()}>
              {enviando && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}
              Registrar
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  )
}

const ESTILO: Record<TonoInstruccion, { clase: string; icono: typeof Truck }> = {
  reserva: { clase: "border-primary/40 bg-primary/10 text-primary", icono: BookmarkCheck },
  traslado: { clase: "border-accent/50 bg-accent/15 text-accent-foreground", icono: Truck },
  estante: { clase: "border-border bg-muted text-foreground", icono: Library },
}

function Instruccion({ codigo, res }: { codigo: string; res: ResultadoDevolucion }) {
  const { titulo, detalle, tono } = instruccionDevolucion(res)
  const { clase, icono: Icono } = ESTILO[tono]
  return (
    <div role="status" aria-live="polite" className={cn("mt-3 flex gap-3 rounded-lg border p-3", clase)}>
      <Icono className="mt-0.5 h-5 w-5 shrink-0" />
      <div className="min-w-0 text-sm">
        <p className="flex items-center gap-1.5 font-semibold">
          <span className="font-mono text-xs opacity-80">{codigo}</span>
          <ArrowRight className="h-3.5 w-3.5" />
          {titulo}
        </p>
        <p className="mt-0.5 text-foreground/80">{detalle}</p>
      </div>
    </div>
  )
}
