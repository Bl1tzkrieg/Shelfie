"use client"

import { useCallback, useEffect, useState } from "react"
import Link from "next/link"
import { ArrowLeft, Loader2, MapPin, Pencil, Plus, Trash2 } from "lucide-react"
import { toast } from "sonner"

import { AppLayout } from "@/components/layout/app-layout"
import { Header } from "@/components/layout/header"
import { useSedes } from "@/components/layout/sede-provider"
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
import { Badge } from "@/components/ui/badge"
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
import { apiDelete, apiGet, apiPost, apiPut, mensajeDeError } from "@/lib/api"
import type { Sede } from "@/lib/types"

type Formulario = {
  codigo: string
  nombre: string
  direccion: string
  telefono: string
  email: string
  punto_retiro: boolean
}

const VACIO: Formulario = {
  codigo: "",
  nombre: "",
  direccion: "",
  telefono: "",
  email: "",
  punto_retiro: true,
}

export default function SedesPage() {
  const { recargarSedes, sedeId } = useSedes()
  const [sedes, setSedes] = useState<Sede[] | null>(null)
  const [editando, setEditando] = useState<Sede | "nueva" | null>(null)
  const [aEliminar, setAEliminar] = useState<Sede | null>(null)

  const cargar = useCallback(async () => {
    try {
      setSedes(await apiGet<Sede[]>("/settings/branches?con_uso=true"))
    } catch (error) {
      toast.error("No se pudieron cargar las sedes", { description: mensajeDeError(error) })
    }
  }, [])

  useEffect(() => {
    cargar()
  }, [cargar])

  async function alGuardar() {
    setEditando(null)
    await Promise.all([cargar(), recargarSedes()])
  }

  async function eliminar() {
    if (!aEliminar) return
    try {
      await apiDelete(`/settings/branches/${aEliminar.id}`)
      toast.success("Sede eliminada", { description: aEliminar.nombre })
      await Promise.all([cargar(), recargarSedes()])
    } catch (error) {
      toast.error("No se pudo eliminar", { description: mensajeDeError(error) })
    } finally {
      setAEliminar(null)
    }
  }

  return (
    <AppLayout permiso="configuracion">
      <Header title="Sedes" description="Bibliotecas de la institución" />

      <div className="p-6">
        <div className="mx-auto max-w-5xl space-y-6">
          <div className="flex items-center justify-between gap-4">
            <Link
              href="/configuracion"
              className="inline-flex items-center gap-1 text-sm text-muted-foreground hover:text-foreground"
            >
              <ArrowLeft className="h-4 w-4" />
              Configuración
            </Link>
            <Button onClick={() => setEditando("nueva")}>
              <Plus className="mr-2 h-4 w-4" />
              Nueva sede
            </Button>
          </div>

          {sedes === null ? (
            <div className="rounded-lg border bg-card py-16 text-center text-muted-foreground">
              Cargando sedes…
            </div>
          ) : (
            <div className="overflow-hidden rounded-lg border border-border bg-card">
              <table className="w-full text-sm">
                <thead className="bg-muted/50 text-left text-muted-foreground">
                  <tr>
                    <th className="px-4 py-3 font-medium">Sede</th>
                    <th className="px-4 py-3 font-medium">Contacto</th>
                    <th className="px-4 py-3 text-right font-medium">Ejemplares</th>
                    <th className="px-4 py-3 text-right font-medium">Lectores</th>
                    <th className="px-4 py-3 font-medium">Reservas</th>
                    <th className="px-4 py-3" />
                  </tr>
                </thead>
                <tbody className="divide-y divide-border">
                  {sedes.map((s) => (
                    <tr key={s.id} className="align-top">
                      <td className="px-4 py-3">
                        <p className="font-medium text-foreground">
                          {s.nombre}
                          {s.id === sedeId && (
                            <span className="ml-2 inline-flex items-center gap-1 text-xs font-normal text-primary">
                              <MapPin className="h-3 w-3" />
                              estás aquí
                            </span>
                          )}
                        </p>
                        <p className="font-mono text-xs text-muted-foreground">{s.codigo}</p>
                      </td>
                      <td className="px-4 py-3 text-muted-foreground">
                        {[s.direccion, s.telefono, s.email].filter(Boolean).join(" · ") || "—"}
                      </td>
                      <td className="px-4 py-3 text-right tabular-nums">{s.ejemplares ?? 0}</td>
                      <td className="px-4 py-3 text-right tabular-nums">{s.lectores ?? 0}</td>
                      <td className="px-4 py-3">
                        {s.punto_retiro ? (
                          <Badge variant="secondary">Punto de retiro</Badge>
                        ) : (
                          <span className="text-muted-foreground">No se retiran</span>
                        )}
                      </td>
                      <td className="px-4 py-3">
                        <div className="flex justify-end gap-1">
                          <Button variant="ghost" size="icon" onClick={() => setEditando(s)}
                                  aria-label={`Editar ${s.nombre}`}>
                            <Pencil className="h-4 w-4" />
                          </Button>
                          <Button variant="ghost" size="icon" onClick={() => setAEliminar(s)}
                                  aria-label={`Eliminar ${s.nombre}`}
                                  disabled={sedes.length === 1}>
                            <Trash2 className="h-4 w-4" />
                          </Button>
                        </div>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>
      </div>

      <Dialog open={editando !== null} onOpenChange={(v) => !v && setEditando(null)}>
        <DialogContent className="sm:max-w-lg">
          {editando !== null && (
            <SedeFormulario sede={editando === "nueva" ? null : editando} onSaved={alGuardar}
                            onCancel={() => setEditando(null)} />
          )}
        </DialogContent>
      </Dialog>

      <AlertDialog open={aEliminar !== null} onOpenChange={(v) => !v && setAEliminar(null)}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>¿Eliminar {aEliminar?.nombre}?</AlertDialogTitle>
            <AlertDialogDescription>
              Solo se puede eliminar una sede sin ejemplares, lectores, préstamos, reservas,
              traslados ni reglas de circulación.
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel>Cancelar</AlertDialogCancel>
            <AlertDialogAction
              onClick={eliminar}
              className="bg-destructive text-destructive-foreground hover:bg-destructive/90"
            >
              Eliminar
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </AppLayout>
  )
}

function SedeFormulario({
  sede,
  onSaved,
  onCancel,
}: {
  sede: Sede | null
  onSaved: () => void
  onCancel: () => void
}) {
  const [form, setForm] = useState<Formulario>(
    sede
      ? {
          codigo: sede.codigo,
          nombre: sede.nombre,
          direccion: sede.direccion ?? "",
          telefono: sede.telefono ?? "",
          email: sede.email ?? "",
          punto_retiro: sede.punto_retiro,
        }
      : VACIO,
  )
  const [guardando, setGuardando] = useState(false)
  const campo = (clave: keyof Formulario) => (e: React.ChangeEvent<HTMLInputElement>) =>
    setForm((f) => ({ ...f, [clave]: e.target.value }))

  async function guardar(e: React.FormEvent) {
    e.preventDefault()
    setGuardando(true)
    try {
      if (sede) await apiPut(`/settings/branches/${sede.id}`, form)
      else await apiPost("/settings/branches", form)
      toast.success(sede ? "Sede actualizada" : "Sede creada", { description: form.nombre })
      onSaved()
    } catch (error) {
      toast.error("No se pudo guardar la sede", { description: mensajeDeError(error) })
    } finally {
      setGuardando(false)
    }
  }

  return (
    <form onSubmit={guardar}>
      <DialogHeader>
        <DialogTitle>{sede ? `Editar ${sede.nombre}` : "Nueva sede"}</DialogTitle>
        <DialogDescription>
          El código identifica la sede en los ejemplares (952 $a/$b en MARC).
        </DialogDescription>
      </DialogHeader>
      <div className="grid gap-4 py-4 sm:grid-cols-3">
        <div className="space-y-2">
          <Label htmlFor="sede-codigo">Código</Label>
          <Input id="sede-codigo" required maxLength={10} value={form.codigo}
                 onChange={campo("codigo")} className="font-mono uppercase" placeholder="NORTE" />
        </div>
        <div className="space-y-2 sm:col-span-2">
          <Label htmlFor="sede-nombre">Nombre</Label>
          <Input id="sede-nombre" required value={form.nombre} onChange={campo("nombre")}
                 placeholder="Biblioteca Sede Norte" />
        </div>
        <div className="space-y-2 sm:col-span-3">
          <Label htmlFor="sede-direccion">Dirección</Label>
          <Input id="sede-direccion" value={form.direccion} onChange={campo("direccion")} />
        </div>
        <div className="space-y-2">
          <Label htmlFor="sede-telefono">Teléfono</Label>
          <Input id="sede-telefono" value={form.telefono} onChange={campo("telefono")} />
        </div>
        <div className="space-y-2 sm:col-span-2">
          <Label htmlFor="sede-email">Correo</Label>
          <Input id="sede-email" type="email" value={form.email} onChange={campo("email")} />
        </div>
        <div className="flex items-start gap-3 sm:col-span-3">
          <Switch id="sede-retiro" checked={form.punto_retiro}
                  onCheckedChange={(v) => setForm((f) => ({ ...f, punto_retiro: v }))} />
          <div className="space-y-1">
            <Label htmlFor="sede-retiro">Punto de retiro de reservas</Label>
            <p className="text-xs text-muted-foreground">
              Los lectores pueden elegir esta sede para retirar lo que reservan.
            </p>
          </div>
        </div>
      </div>
      <DialogFooter>
        <Button type="button" variant="outline" onClick={onCancel}>
          Cancelar
        </Button>
        <Button type="submit" disabled={guardando || !form.codigo.trim() || !form.nombre.trim()}>
          {guardando && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}
          {sede ? "Guardar" : "Crear sede"}
        </Button>
      </DialogFooter>
    </form>
  )
}
