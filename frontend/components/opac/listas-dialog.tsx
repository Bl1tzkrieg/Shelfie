"use client"

import { useCallback, useEffect, useState } from "react"
import { Loader2, Plus } from "lucide-react"
import { toast } from "sonner"

import { Button } from "@/components/ui/button"
import { Checkbox } from "@/components/ui/checkbox"
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog"
import { Input } from "@/components/ui/input"
import { apiDelete, apiGet, apiPost, mensajeDeError } from "@/lib/api"
import type { ListaLector } from "@/lib/opac"

/** Marca en qué listas propias está un título, y crea una nueva de paso. */
export function ListasDialog({ biblioId, titulo, open, onOpenChange }:
  { biblioId: string; titulo: string; open: boolean; onOpenChange: (v: boolean) => void }) {
  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-sm">
        <DialogHeader>
          <DialogTitle>Guardar en una lista</DialogTitle>
          <DialogDescription>{titulo}</DialogDescription>
        </DialogHeader>
        {open && <Contenido biblioId={biblioId} />}
      </DialogContent>
    </Dialog>
  )
}

function Contenido({ biblioId }: { biblioId: string }) {
  const [listas, setListas] = useState<ListaLector[] | null>(null)
  const [nueva, setNueva] = useState("")
  const [ocupado, setOcupado] = useState<number | "nueva" | null>(null)

  const cargar = useCallback(async () => {
    setListas(await apiGet<ListaLector[]>(`/opac/account/lists?biblio_id=${biblioId}`))
  }, [biblioId])

  useEffect(() => {
    cargar().catch((e) => toast.error("No se pudieron cargar tus listas", { description: mensajeDeError(e) }))
  }, [cargar])

  async function alternar(lista: ListaLector) {
    setOcupado(lista.id)
    try {
      if (lista.contiene) await apiDelete(`/opac/account/lists/${lista.id}/titles/${biblioId}`)
      else await apiPost(`/opac/account/lists/${lista.id}/titles`, { biblio_id: Number(biblioId) })
      await cargar()
    } catch (e) {
      toast.error("No se pudo guardar", { description: mensajeDeError(e) })
    } finally {
      setOcupado(null)
    }
  }

  async function crear(e: React.FormEvent) {
    e.preventDefault()
    if (!nueva.trim()) return
    setOcupado("nueva")
    try {
      const lista = await apiPost<ListaLector>("/opac/account/lists", { nombre: nueva.trim() })
      await apiPost(`/opac/account/lists/${lista.id}/titles`, { biblio_id: Number(biblioId) })
      toast.success(`Guardado en «${lista.nombre}»`)
      setNueva("")
      await cargar()
    } catch (e) {
      toast.error("No se pudo crear la lista", { description: mensajeDeError(e) })
    } finally {
      setOcupado(null)
    }
  }

  if (!listas) {
    return <Loader2 className="mx-auto my-6 h-5 w-5 animate-spin text-muted-foreground" />
  }

  return (
    <div className="space-y-4">
      {listas.length > 0 ? (
        <ul className="space-y-1">
          {listas.map((l) => (
            <li key={l.id}>
              <label className="flex cursor-pointer items-center gap-3 rounded-md px-2 py-2 hover:bg-muted">
                <Checkbox checked={!!l.contiene} disabled={ocupado !== null}
                          onCheckedChange={() => alternar(l)} />
                <span className="flex-1 text-sm">{l.nombre}</span>
                <span className="text-xs tabular-nums text-muted-foreground">{l.cantidad}</span>
              </label>
            </li>
          ))}
        </ul>
      ) : (
        <p className="text-sm text-muted-foreground">Todavía no tienes listas. Crea la primera:</p>
      )}
      <form onSubmit={crear} className="flex gap-2">
        <Input aria-label="Nombre de la lista nueva" placeholder="Nueva lista" maxLength={100}
               value={nueva} onChange={(e) => setNueva(e.target.value)} />
        <Button type="submit" variant="outline" disabled={!nueva.trim() || ocupado !== null}>
          {ocupado === "nueva" ? <Loader2 className="h-4 w-4 animate-spin" /> : <Plus className="h-4 w-4" />}
          <span className="sr-only">Crear</span>
        </Button>
      </form>
    </div>
  )
}
