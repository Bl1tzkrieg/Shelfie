"use client"

import { useCallback, useEffect, useState } from "react"
import { Loader2, RotateCw, Send } from "lucide-react"
import { toast } from "sonner"

import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle } from "@/components/ui/dialog"
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table"
import { ToggleGroup, ToggleGroupItem } from "@/components/ui/toggle-group"
import { apiGet, apiPost, mensajeDeError } from "@/lib/api"
import type { Aviso, CorridaTarea, EstadoAviso } from "@/lib/types"

const VARIANTE: Record<EstadoAviso, "default" | "secondary" | "destructive" | "outline"> = {
  Enviado: "secondary",
  Pendiente: "outline",
  Fallido: "destructive",
}

export function EstadoAvisoBadge({ estado }: { estado: EstadoAviso }) {
  return <Badge variant={VARIANTE[estado]}>{estado}</Badge>
}

/** La cola de correos: qué salió, qué espera y qué falló (con el motivo). */
export function ColaAvisos({ puedeEditar, onCambio }: { puedeEditar: boolean; onCambio: () => void }) {
  const [filtro, setFiltro] = useState<"" | EstadoAviso>("")
  const [avisos, setAvisos] = useState<Aviso[] | null>(null)
  const [abierto, setAbierto] = useState<Aviso | null>(null)
  const [ocupado, setOcupado] = useState<number | "cola" | null>(null)

  const cargar = useCallback(async () => {
    try {
      setAvisos(await apiGet<Aviso[]>(`/notices/queue${filtro ? `?estado=${filtro}` : ""}`))
    } catch (e) {
      toast.error("No se pudo cargar la cola", { description: mensajeDeError(e) })
    }
  }, [filtro])

  useEffect(() => {
    cargar()
  }, [cargar])

  async function enviarCola() {
    setOcupado("cola")
    try {
      const r = await apiPost<CorridaTarea>("/notices/queue/send")
      const res = (r.resultado ?? {}) as { enviados?: number; pendientes?: number; nota?: string }
      if (r.ok) toast.success(`${res.enviados ?? 0} enviado(s)`, { description: res.nota ?? `${res.pendientes ?? 0} quedan pendientes` })
      else toast.error("La tarea falló", { description: r.error ?? undefined })
      await cargar()
      onCambio()
    } catch (e) {
      toast.error("No se pudo enviar", { description: mensajeDeError(e) })
    } finally {
      setOcupado(null)
    }
  }

  async function reintentar(a: Aviso) {
    setOcupado(a.id)
    try {
      const r = await apiPost<Aviso>(`/notices/queue/${a.id}/retry`)
      if (r.estado === "Enviado") toast.success("Aviso enviado", { description: r.destinatario })
      else toast.error("Sigue sin salir", { description: r.error ?? undefined })
      setAbierto(null)
      await cargar()
      onCambio()
    } catch (e) {
      toast.error("No se pudo reintentar", { description: mensajeDeError(e) })
    } finally {
      setOcupado(null)
    }
  }

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <ToggleGroup type="single" variant="outline" value={filtro}
                     onValueChange={(v) => setFiltro((v || "") as "" | EstadoAviso)}>
          <ToggleGroupItem value="" className="px-3">Todos</ToggleGroupItem>
          <ToggleGroupItem value="Pendiente" className="px-3">Pendientes</ToggleGroupItem>
          <ToggleGroupItem value="Enviado" className="px-3">Enviados</ToggleGroupItem>
          <ToggleGroupItem value="Fallido" className="px-3">Fallidos</ToggleGroupItem>
        </ToggleGroup>
        {puedeEditar && (
          <Button onClick={enviarCola} disabled={ocupado !== null}>
            {ocupado === "cola" ? <Loader2 className="mr-2 h-4 w-4 animate-spin" /> : <Send className="mr-2 h-4 w-4" />}
            Enviar pendientes ahora
          </Button>
        )}
      </div>

      {!avisos ? (
        <Loader2 className="mx-auto my-8 h-5 w-5 animate-spin text-muted-foreground" />
      ) : avisos.length === 0 ? (
        <p className="rounded-lg border border-dashed py-12 text-center text-sm text-muted-foreground">
          {filtro ? "No hay avisos en ese estado." : "Todavía no se generó ningún aviso."}
        </p>
      ) : (
        <div className="overflow-x-auto rounded-lg border bg-card">
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Creado</TableHead>
                <TableHead>Aviso</TableHead>
                <TableHead>Para</TableHead>
                <TableHead>Asunto</TableHead>
                <TableHead>Estado</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {avisos.map((a) => (
                <TableRow key={a.id} className="cursor-pointer" onClick={() => setAbierto(a)}>
                  <TableCell className="whitespace-nowrap tabular-nums">{a.creado}</TableCell>
                  <TableCell className="whitespace-nowrap">{a.tipo}</TableCell>
                  <TableCell>
                    {a.lector ?? a.destinatario}
                    {a.lector && <span className="block text-xs text-muted-foreground">{a.destinatario}</span>}
                  </TableCell>
                  <TableCell className="max-w-xs truncate">{a.asunto}</TableCell>
                  <TableCell>
                    <EstadoAvisoBadge estado={a.estado} />
                    {a.estado !== "Enviado" && a.intentos > 0 && (
                      <span className="ml-2 text-xs text-muted-foreground">{a.intentos} intento(s)</span>
                    )}
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </div>
      )}

      <Dialog open={!!abierto} onOpenChange={(v) => !v && setAbierto(null)}>
        <DialogContent className="sm:max-w-xl">
          {abierto && (
            <>
              <DialogHeader>
                <DialogTitle>{abierto.asunto}</DialogTitle>
                <DialogDescription>
                  {abierto.tipo} · para {abierto.destinatario} · creado el {abierto.creado}
                  {abierto.enviado && ` · enviado el ${abierto.enviado}`}
                </DialogDescription>
              </DialogHeader>
              {abierto.error && (
                <p className="rounded-md bg-destructive/10 px-3 py-2 text-sm text-destructive">{abierto.error}</p>
              )}
              <pre className="max-h-96 overflow-auto whitespace-pre-wrap rounded-md bg-muted p-4 font-sans text-sm text-foreground">
                {abierto.cuerpo}
              </pre>
              {puedeEditar && abierto.estado !== "Enviado" && (
                <div className="flex justify-end">
                  <Button onClick={() => reintentar(abierto)} disabled={ocupado !== null}>
                    {ocupado === abierto.id ? <Loader2 className="mr-2 h-4 w-4 animate-spin" /> : <RotateCw className="mr-2 h-4 w-4" />}
                    Reintentar ahora
                  </Button>
                </div>
              )}
            </>
          )}
        </DialogContent>
      </Dialog>
    </div>
  )
}
