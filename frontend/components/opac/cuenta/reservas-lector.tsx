"use client"

import { useCallback, useEffect, useState } from "react"
import Link from "next/link"
import { Loader2 } from "lucide-react"
import { toast } from "sonner"

import { useLector } from "@/components/opac/lector-provider"
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
} from "@/components/ui/alert-dialog"
import { Button } from "@/components/ui/button"
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select"
import { apiDelete, apiGet, apiPatch, mensajeDeError } from "@/lib/api"
import { fechaCorta, type ReservaLector, type SedePublica } from "@/lib/opac"

function estado(r: ReservaLector) {
  if (r.status === "EnEspera") return { texto: `Listo para retirar en ${r.pickupBranch ?? "la biblioteca"}, hasta el ${r.pickupBy}`, destacado: true }
  if (r.status === "EnTransito") return { texto: `En camino a ${r.pickupBranch ?? "tu sede"}`, destacado: false }
  if (r.suspended) return { texto: r.suspendedUntil ? `Pausada hasta el ${fechaCorta(r.suspendedUntil)}` : "Pausada", destacado: false }
  return { texto: `Turno ${r.priority} · se retira en ${r.pickupBranch ?? "tu sede"}`, destacado: false }
}

export function ReservasLector() {
  const { recargar } = useLector()
  const [reservas, setReservas] = useState<ReservaLector[] | null>(null)
  const [sedes, setSedes] = useState<SedePublica[]>([])
  const [ocupada, setOcupada] = useState<string | null>(null)
  const [cancelando, setCancelando] = useState<ReservaLector | null>(null)

  const cargar = useCallback(async () => {
    try {
      setReservas(await apiGet<ReservaLector[]>("/opac/account/holds"))
    } catch (e) {
      toast.error("No se pudieron cargar tus reservas", { description: mensajeDeError(e) })
    }
  }, [])

  useEffect(() => {
    cargar()
    apiGet<SedePublica[]>("/opac/branches").then(setSedes).catch(() => setSedes([]))
  }, [cargar])

  async function cambiar(r: ReservaLector, datos: Record<string, unknown>, aviso: string) {
    setOcupada(r.id)
    try {
      await apiPatch(`/opac/account/holds/${r.id}`, datos)
      toast.success(aviso, { description: r.title })
      await cargar()
    } catch (e) {
      toast.error("No se pudo cambiar la reserva", { description: mensajeDeError(e) })
    } finally {
      setOcupada(null)
    }
  }

  async function cancelar(r: ReservaLector) {
    setOcupada(r.id)
    try {
      await apiDelete(`/opac/account/holds/${r.id}`)
      toast.success("Reserva cancelada", { description: r.title })
      await Promise.all([cargar(), recargar()])
    } catch (e) {
      toast.error("No se pudo cancelar", { description: mensajeDeError(e) })
    } finally {
      setOcupada(null)
      setCancelando(null)
    }
  }

  if (!reservas) return <Loader2 className="mx-auto my-8 h-5 w-5 animate-spin text-muted-foreground" />
  if (reservas.length === 0) {
    return (
      <p className="py-8 text-center text-muted-foreground">
        No tienes reservas. <Link href="/opac" className="text-primary hover:underline">Busca algo para leer</Link>.
      </p>
    )
  }

  return (
    <>
      <ul className="space-y-3">
        {reservas.map((r) => {
          const e = estado(r)
          const pendiente = r.status === "Pendiente"
          return (
            <li key={r.id} className={e.destacado ? "rounded-lg border border-accent/50 bg-accent/10 p-4" : "rounded-lg border border-border bg-card p-4"}>
              <div className="flex flex-col gap-3 sm:flex-row sm:items-start">
                <div className="min-w-0 flex-1">
                  <Link href={`/opac/registro/${r.biblioId}`} className="font-medium text-foreground hover:text-primary hover:underline">
                    {r.title}
                  </Link>
                  {r.author && <p className="text-sm text-muted-foreground">{r.author}</p>}
                  <p className={e.destacado ? "mt-1 text-sm font-medium text-foreground" : "mt-1 text-sm text-foreground"}>{e.texto}</p>
                  <p className="text-xs text-muted-foreground">
                    Reservado el {r.reservedOn}
                    {r.notNeededAfter && ` · no lo necesitas después del ${fechaCorta(r.notNeededAfter)}`}
                  </p>
                </div>
                <div className="flex flex-wrap items-center gap-2">
                  {pendiente && sedes.length > 1 && (
                    <Select value={r.pickupBranchId ? String(r.pickupBranchId) : ""} disabled={ocupada === r.id}
                            onValueChange={(v) => cambiar(r, { biblioteca_retiro_id: Number(v) }, "Sede de retiro cambiada")}>
                      <SelectTrigger size="sm" className="w-40" aria-label={`Sede de retiro de ${r.title}`}>
                        <SelectValue placeholder="Sede de retiro" />
                      </SelectTrigger>
                      <SelectContent>
                        {sedes.map((s) => <SelectItem key={s.id} value={String(s.id)}>{s.nombre}</SelectItem>)}
                      </SelectContent>
                    </Select>
                  )}
                  {pendiente && (
                    <Button size="sm" variant="outline" disabled={ocupada === r.id}
                            onClick={() => cambiar(r, { suspendida: !r.suspended },
                                                   r.suspended ? "Reserva reanudada" : "Reserva pausada")}>
                      {r.suspended ? "Reanudar" : "Pausar"}
                    </Button>
                  )}
                  <Button size="sm" variant="ghost" className="text-destructive hover:text-destructive"
                          disabled={ocupada === r.id} onClick={() => setCancelando(r)}>
                    Cancelar
                  </Button>
                </div>
              </div>
            </li>
          )
        })}
      </ul>

      <AlertDialog open={!!cancelando} onOpenChange={(v) => !v && setCancelando(null)}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>¿Cancelar la reserva?</AlertDialogTitle>
            <AlertDialogDescription>
              {cancelando?.title}. Si vuelves a reservarlo, quedarás al final de la cola.
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel>Conservarla</AlertDialogCancel>
            <AlertDialogAction onClick={() => cancelando && cancelar(cancelando)}>Cancelar reserva</AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </>
  )
}
