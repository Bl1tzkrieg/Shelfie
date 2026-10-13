"use client"

import { useState } from "react"
import { Loader2, PackageCheck } from "lucide-react"
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
import { Switch } from "@/components/ui/switch"
import { apiPost, mensajeDeError } from "@/lib/api"
import type { Fasciculo, ResultadoDevolucion, Suscripcion } from "@/lib/types"

type Respuesta = Suscripcion & {
  recibido: Fasciculo
  destino: Pick<ResultadoDevolucion, "accion" | "reserva" | "traslado"> | null
}

/** Recibir un número: opcionalmente con código de barras propio y signatura. */
export function RecibirFasciculoDialog({
  fasciculo,
  titulo,
  crearEjemplar,
  onOpenChange,
  onRecibido,
}: {
  fasciculo: Fasciculo | null
  titulo: string
  crearEjemplar: boolean
  onOpenChange: (open: boolean) => void
  onRecibido: () => void
}) {
  return (
    <Dialog open={fasciculo !== null} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-md">
        {fasciculo && (
          <Formulario fasciculo={fasciculo} titulo={titulo} crearEjemplar={crearEjemplar}
                      onCancel={() => onOpenChange(false)} onRecibido={onRecibido} />
        )}
      </DialogContent>
    </Dialog>
  )
}

export function avisarRecepcion(r: Respuesta) {
  const destino = r.destino
  const extra =
    destino?.accion === "espera" && destino.reserva
      ? ` Apártalo para ${destino.reserva.lector} (${destino.reserva.carnet}).`
      : destino?.traslado
        ? ` Envíalo a ${destino.traslado.hacia}.`
        : ""
  toast.success(`Recibido: ${r.recibido.numero}`, {
    description:
      (r.recibido.codigo_barras ? `Ejemplar ${r.recibido.codigo_barras}.` : "Sin ejemplar.") +
      extra +
      (r.proximo ? ` Próximo: ${r.proximo.numero} (${r.proximo.fecha_esperada}).` : ""),
    duration: extra ? 10000 : undefined,
  })
}

function Formulario({
  fasciculo,
  titulo,
  crearEjemplar,
  onCancel,
  onRecibido,
}: {
  fasciculo: Fasciculo
  titulo: string
  crearEjemplar: boolean
  onCancel: () => void
  onRecibido: () => void
}) {
  const [crear, setCrear] = useState(crearEjemplar)
  const [codigo, setCodigo] = useState("")
  const [signatura, setSignatura] = useState("")
  const [enviando, setEnviando] = useState(false)

  async function recibir(e: React.FormEvent) {
    e.preventDefault()
    setEnviando(true)
    try {
      const r = await apiPost<Respuesta>(`/serials/issues/${fasciculo.id}/receive`, {
        crear_ejemplar: crear,
        codigo_barras: codigo.trim() || null,
        signatura: signatura.trim() || null,
      })
      avisarRecepcion(r)
      onRecibido()
    } catch (error) {
      toast.error("No se pudo recibir", { description: mensajeDeError(error) })
    } finally {
      setEnviando(false)
    }
  }

  return (
    <form onSubmit={recibir}>
      <DialogHeader>
        <DialogTitle>Recibir {fasciculo.numero}</DialogTitle>
        <DialogDescription>{titulo}</DialogDescription>
      </DialogHeader>
      <div className="space-y-4 py-4">
        <div className="flex items-center gap-3">
          <Switch id="fasc-crear" checked={crear} onCheckedChange={setCrear} />
          <Label htmlFor="fasc-crear">Dar de alta el ejemplar</Label>
        </div>
        {crear && (
          <>
            <div className="space-y-2">
              <Label htmlFor="fasc-codigo">Código de barras</Label>
              <Input id="fasc-codigo" autoFocus value={codigo} placeholder="Vacío: se genera solo"
                     onChange={(e) => setCodigo(e.target.value)} />
            </div>
            <div className="space-y-2">
              <Label htmlFor="fasc-signatura">Signatura topográfica</Label>
              <Input id="fasc-signatura" value={signatura} placeholder="Opcional"
                     onChange={(e) => setSignatura(e.target.value)} />
            </div>
          </>
        )}
      </div>
      <DialogFooter>
        <Button type="button" variant="outline" onClick={onCancel}>Cancelar</Button>
        <Button type="submit" disabled={enviando}>
          {enviando ? <Loader2 className="mr-2 h-4 w-4 animate-spin" /> : <PackageCheck className="mr-2 h-4 w-4" />}
          Recibir
        </Button>
      </DialogFooter>
    </form>
  )
}
