"use client"

import { useCallback, useEffect, useState } from "react"
import Link from "next/link"
import { Globe, Link2, Loader2, Lock, Plus, Trash2 } from "lucide-react"
import { toast } from "sonner"

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
import { Input } from "@/components/ui/input"
import { Switch } from "@/components/ui/switch"
import { apiDelete, apiGet, apiPatch, apiPost, mensajeDeError } from "@/lib/api"
import type { ListaLector } from "@/lib/opac"

export function ListasLector() {
  const [listas, setListas] = useState<ListaLector[] | null>(null)
  const [nombre, setNombre] = useState("")
  const [ocupada, setOcupada] = useState<number | "nueva" | null>(null)
  const [borrando, setBorrando] = useState<ListaLector | null>(null)

  const cargar = useCallback(async () => {
    try {
      setListas(await apiGet<ListaLector[]>("/opac/account/lists"))
    } catch (e) {
      toast.error("No se pudieron cargar tus listas", { description: mensajeDeError(e) })
    }
  }, [])

  useEffect(() => {
    cargar()
  }, [cargar])

  async function hacer(id: number | "nueva", accion: () => Promise<unknown>, aviso?: string) {
    setOcupada(id)
    try {
      await accion()
      if (aviso) toast.success(aviso)
      await cargar()
    } catch (e) {
      toast.error("No se pudo guardar", { description: mensajeDeError(e) })
    } finally {
      setOcupada(null)
    }
  }

  async function copiarEnlace(l: ListaLector) {
    const url = `${window.location.origin}/opac/listas/${l.id}`
    try {
      await navigator.clipboard.writeText(url)
      toast.success("Enlace copiado", { description: url })
    } catch {
      toast.info("Enlace de la lista", { description: url })
    }
  }

  return (
    <div className="space-y-4">
      <form
        className="flex max-w-md gap-2"
        onSubmit={(e) => {
          e.preventDefault()
          hacer("nueva", () => apiPost("/opac/account/lists", { nombre: nombre.trim() }), "Lista creada").then(() => setNombre(""))
        }}
      >
        <Input aria-label="Nombre de la lista nueva" placeholder="Nombre de una lista nueva" maxLength={100}
               value={nombre} onChange={(e) => setNombre(e.target.value)} />
        <Button type="submit" disabled={!nombre.trim() || ocupada !== null}>
          {ocupada === "nueva" ? <Loader2 className="mr-2 h-4 w-4 animate-spin" /> : <Plus className="mr-2 h-4 w-4" />}
          Crear
        </Button>
      </form>

      {!listas ? (
        <Loader2 className="mx-auto my-8 h-5 w-5 animate-spin text-muted-foreground" />
      ) : listas.length === 0 ? (
        <p className="py-8 text-center text-muted-foreground">
          Guarda títulos en listas desde su ficha: para la tesis, para leer en vacaciones…
        </p>
      ) : (
        <ul className="divide-y divide-border rounded-lg border border-border bg-card">
          {listas.map((l) => (
            <li key={l.id} className="flex flex-wrap items-center gap-3 px-4 py-3">
              {l.publica ? <Globe className="h-4 w-4 text-primary" aria-label="Pública" />
                : <Lock className="h-4 w-4 text-muted-foreground" aria-label="Privada" />}
              <Link href={`/opac/listas/${l.id}`} className="min-w-0 flex-1 font-medium hover:text-primary hover:underline">
                {l.nombre}
                <span className="ml-2 text-sm font-normal tabular-nums text-muted-foreground">
                  {l.cantidad} título{l.cantidad === 1 ? "" : "s"}
                </span>
              </Link>
              <label className="flex items-center gap-2 text-sm text-muted-foreground">
                <Switch checked={l.publica} disabled={ocupada !== null}
                        onCheckedChange={(v) => hacer(l.id, () => apiPatch(`/opac/account/lists/${l.id}`, { publica: v }),
                                                      v ? "Ahora cualquiera con el enlace puede verla" : "Ahora solo tú la ves")} />
                Pública
              </label>
              {l.publica && (
                <Button size="sm" variant="ghost" onClick={() => copiarEnlace(l)} aria-label={`Copiar enlace de ${l.nombre}`}>
                  <Link2 className="h-4 w-4" />
                </Button>
              )}
              <Button size="sm" variant="ghost" className="text-destructive hover:text-destructive" disabled={ocupada !== null}
                      aria-label={`Borrar ${l.nombre}`}
                      onClick={() => setBorrando(l)}>
                <Trash2 className="h-4 w-4" />
              </Button>
            </li>
          ))}
        </ul>
      )}

      <AlertDialog open={!!borrando} onOpenChange={(v) => !v && setBorrando(null)}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>¿Borrar «{borrando?.nombre}»?</AlertDialogTitle>
            <AlertDialogDescription>
              Se quita la lista con sus {borrando?.cantidad} títulos guardados. Los títulos siguen en el catálogo.
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel>Conservarla</AlertDialogCancel>
            <AlertDialogAction
              onClick={() => borrando && hacer(borrando.id, () => apiDelete(`/opac/account/lists/${borrando.id}`),
                                                `Borraste «${borrando.nombre}»`)}>
              Borrar lista
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </div>
  )
}
