"use client"

import { useCallback, useEffect, useState } from "react"
import Link from "next/link"
import { Loader2, RefreshCw } from "lucide-react"
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
import { apiGet, apiPost, mensajeDeError } from "@/lib/api"
import { formatoBs, type PrestamoLector } from "@/lib/opac"
import { cn } from "@/lib/utils"

export function PrestamosLector() {
  const { recargar } = useLector()
  const [prestamos, setPrestamos] = useState<PrestamoLector[] | null>(null)
  const [renovando, setRenovando] = useState<number | "todos" | null>(null)
  // Préstamo vencido esperando que el lector acepte el cargo por el atraso.
  const [confirmando, setConfirmando] = useState<PrestamoLector | null>(null)

  const cargar = useCallback(async () => {
    try {
      setPrestamos(await apiGet<PrestamoLector[]>("/opac/account/loans"))
    } catch (e) {
      toast.error("No se pudieron cargar tus préstamos", { description: mensajeDeError(e) })
    }
  }, [])

  useEffect(() => {
    cargar()
  }, [cargar])

  async function renovar(p: PrestamoLector, aceptarCargo = false) {
    setConfirmando(null)
    setRenovando(p.id)
    try {
      const r = await apiPost<{ mensaje: string }>(`/opac/account/loans/${p.id}/renew`,
                                                   { aceptar_cargo: aceptarCargo })
      toast.success(r.mensaje, { description: p.titulo })
      await Promise.all([cargar(), recargar()])
    } catch (e) {
      toast.error("No se pudo renovar", { description: mensajeDeError(e) })
    } finally {
      setRenovando(null)
    }
  }

  async function renovarTodos() {
    setRenovando("todos")
    try {
      const r = await apiPost<{ renovados: string[]; no_renovados: { titulo: string; motivo: string }[] }>(
        "/opac/account/loans/renew-all")
      if (r.renovados.length) toast.success(`Renovaste ${r.renovados.length} préstamo${r.renovados.length === 1 ? "" : "s"}`)
      for (const n of r.no_renovados) toast.warning(n.titulo, { description: n.motivo })
      await Promise.all([cargar(), recargar()])
    } catch (e) {
      toast.error("No se pudo renovar", { description: mensajeDeError(e) })
    } finally {
      setRenovando(null)
    }
  }

  if (!prestamos) return <Loader2 className="mx-auto my-8 h-5 w-5 animate-spin text-muted-foreground" />
  if (prestamos.length === 0) {
    return <p className="py-8 text-center text-muted-foreground">No tienes nada prestado ahora.</p>
  }

  // Los vencidos no se renuevan en bloque (tienen un cargo que el lector debe aceptar).
  const renovables = prestamos.filter((p) => p.renovable && !p.cargo_al_renovar).length
  return (
    <div className="space-y-3">
      {renovables > 1 && (
        <div className="flex justify-end">
          <Button variant="outline" size="sm" onClick={renovarTodos} disabled={renovando !== null}>
            {renovando === "todos" ? <Loader2 className="mr-2 h-4 w-4 animate-spin" /> : <RefreshCw className="mr-2 h-4 w-4" />}
            Renovar todo lo posible
          </Button>
        </div>
      )}
      <ul className="space-y-3">
        {prestamos.map((p) => (
          <li key={p.id} className={cn("flex flex-col gap-3 rounded-lg border bg-card shadow-papel p-4 sm:flex-row sm:items-center",
                                      p.vencido ? "border-destructive/40" : "border-border")}>
            <div className="min-w-0 flex-1">
              <Link href={`/opac/registro/${p.biblio_id}`} className="font-medium text-foreground hover:text-primary hover:underline">
                {p.titulo}
              </Link>
              <p className="text-sm text-muted-foreground">
                {[p.autor, p.numeracion].filter(Boolean).join(" · ")}
              </p>
              <p className={cn("mt-1 text-sm", p.vencido ? "font-medium text-destructive" : "text-foreground")}>
                {p.vencido
                  ? `Venció el ${p.vence} (${p.dias_atraso} día${p.dias_atraso === 1 ? "" : "s"} de atraso)`
                  : `Devuélvelo antes del ${p.vence}`}
              </p>
              <p className="text-xs text-muted-foreground">
                Renovado {p.renovaciones} de {p.renovaciones_permitidas} veces
                {!p.renovable && p.motivo && <> · {p.motivo}</>}
              </p>
            </div>
            <Button size="sm" variant="outline" disabled={!p.renovable || renovando !== null}
                    onClick={() => (p.cargo_al_renovar > 0 ? setConfirmando(p) : renovar(p))}
                    aria-label={`Renovar ${p.titulo}`}>
              {renovando === p.id && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}
              Renovar
            </Button>
          </li>
        ))}
      </ul>

      <AlertDialog open={!!confirmando} onOpenChange={(v) => !v && setConfirmando(null)}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>¿Renovar un préstamo vencido?</AlertDialogTitle>
            <AlertDialogDescription asChild>
              <div className="space-y-2">
                <p>
                  {confirmando?.titulo} venció el {confirmando?.vence}. Renovarlo cobra{" "}
                  <strong className="text-foreground">{formatoBs(confirmando?.cargo_al_renovar ?? 0)}</strong>{" "}
                  por el atraso.
                </p>
                {confirmando?.bloquearia && (
                  <p className="text-destructive">
                    Con ese cargo pasas la deuda máxima: hasta pagar en la biblioteca no podrás renovar
                    ni reservar nada más.
                  </p>
                )}
                <p>Si lo devuelves en la biblioteca, el atraso se cobra igual, pero sin renovarlo.</p>
              </div>
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel>No renovar</AlertDialogCancel>
            <AlertDialogAction onClick={() => confirmando && renovar(confirmando, true)}>
              Renovar y aceptar el cargo
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </div>
  )
}
