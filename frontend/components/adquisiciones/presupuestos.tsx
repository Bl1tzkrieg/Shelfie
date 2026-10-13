"use client"

import { useCallback, useEffect, useState } from "react"
import { Loader2, Lock, LockOpen, MoreHorizontal, Pencil, Plus, Trash2 } from "lucide-react"
import { toast } from "sonner"

import { useSedes } from "@/components/layout/sede-provider"
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
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select"
import { Switch } from "@/components/ui/switch"
import { apiDelete, apiGet, apiPost, apiPut, mensajeDeError } from "@/lib/api"
import type { Fondo, Presupuesto } from "@/lib/types"
import { BarraFondo, bs, fechaCorta, Vacio } from "./comun"

type EdicionFondo = { presupuesto: Presupuesto; fondo: Fondo | null }

export function PresupuestosPanel() {
  const [presupuestos, setPresupuestos] = useState<Presupuesto[] | null>(null)
  const [editando, setEditando] = useState<Presupuesto | "nuevo" | null>(null)
  const [fondo, setFondo] = useState<EdicionFondo | null>(null)

  const cargar = useCallback(async () => {
    try {
      setPresupuestos(await apiGet<Presupuesto[]>("/acquisitions/budgets"))
    } catch (e) {
      toast.error("No se pudieron cargar los presupuestos", { description: mensajeDeError(e) })
    }
  }, [])

  useEffect(() => {
    cargar()
  }, [cargar])

  async function accion(promesa: Promise<unknown>, aviso: string) {
    try {
      await promesa
      toast.success(aviso)
      cargar()
    } catch (error) {
      toast.error("No se pudo completar", { description: mensajeDeError(error) })
    }
  }

  return (
    <div className="space-y-4">
      <div className="flex justify-end">
        <Button onClick={() => setEditando("nuevo")}>
          <Plus className="mr-2 h-4 w-4" />
          Nuevo presupuesto
        </Button>
      </div>
      {presupuestos === null ? (
        <div className="py-12 text-center text-muted-foreground"><Loader2 className="mx-auto h-5 w-5 animate-spin" /></div>
      ) : presupuestos.length === 0 ? (
        <Vacio>Sin presupuestos. Crea uno para el ejercicio y repártelo en fondos (por área, sede o colección).</Vacio>
      ) : (
        presupuestos.map((p) => (
          <section key={p.id} className="rounded-lg border bg-card">
            <div className="flex flex-col gap-2 border-b px-5 py-4 sm:flex-row sm:items-start sm:justify-between">
              <div>
                <h3 className="flex flex-wrap items-center gap-2 font-semibold text-foreground">
                  {p.nombre}
                  {!p.activo && <Badge variant="outline">Inactivo</Badge>}
                  {p.bloqueado && <Badge variant="secondary"><Lock className="mr-1 h-3 w-3" />Bloqueado</Badge>}
                </h3>
                <p className="text-sm text-muted-foreground">
                  {fechaCorta(p.fecha_inicio)} – {fechaCorta(p.fecha_fin)} · {bs(p.monto_total)} ·{" "}
                  {bs(p.sin_asignar)} sin asignar · gastado {bs(p.gastado)}
                </p>
              </div>
              <div className="flex gap-2">
                <Button size="sm" variant="outline" disabled={p.bloqueado}
                        onClick={() => setFondo({ presupuesto: p, fondo: null })}>
                  <Plus className="mr-2 h-4 w-4" />
                  Fondo
                </Button>
                <DropdownMenu>
                  <DropdownMenuTrigger asChild>
                    <Button size="sm" variant="ghost" aria-label={`Acciones de ${p.nombre}`}>
                      <MoreHorizontal className="h-4 w-4" />
                    </Button>
                  </DropdownMenuTrigger>
                  <DropdownMenuContent align="end">
                    <DropdownMenuItem disabled={p.bloqueado} onClick={() => setEditando(p)}>
                      <Pencil className="mr-2 h-4 w-4" /> Editar
                    </DropdownMenuItem>
                    <DropdownMenuItem onClick={() => accion(
                      apiPut(`/acquisitions/budgets/${p.id}`, { bloqueado: !p.bloqueado }),
                      p.bloqueado ? "Presupuesto desbloqueado" : "Presupuesto bloqueado")}>
                      {p.bloqueado ? <LockOpen className="mr-2 h-4 w-4" /> : <Lock className="mr-2 h-4 w-4" />}
                      {p.bloqueado ? "Desbloquear" : "Bloquear (cierre)"}
                    </DropdownMenuItem>
                    <DropdownMenuItem onClick={() => accion(
                      apiPut(`/acquisitions/budgets/${p.id}`, { activo: !p.activo }),
                      p.activo ? "Presupuesto desactivado" : "Presupuesto activado")}>
                      {p.activo ? "Desactivar" : "Activar"}
                    </DropdownMenuItem>
                    <DropdownMenuSeparator />
                    <DropdownMenuItem className="text-destructive focus:text-destructive"
                                      onClick={() => accion(apiDelete(`/acquisitions/budgets/${p.id}`), "Presupuesto eliminado")}>
                      <Trash2 className="mr-2 h-4 w-4" /> Eliminar
                    </DropdownMenuItem>
                  </DropdownMenuContent>
                </DropdownMenu>
              </div>
            </div>
            {p.fondos.length === 0 ? (
              <p className="px-5 py-6 text-sm text-muted-foreground">Sin fondos todavía.</p>
            ) : (
              <ul className="divide-y divide-border">
                {p.fondos.map((f) => (
                  <li key={f.id} className="grid gap-3 px-5 py-3 sm:grid-cols-[minmax(0,14rem)_1fr_auto] sm:items-center">
                    <div>
                      <p className="font-medium text-foreground">
                        <span className="font-mono text-xs text-muted-foreground">{f.codigo}</span> {f.nombre}
                      </p>
                      <p className="text-xs text-muted-foreground">
                        Asignado {bs(f.asignado)}
                        {f.biblioteca && ` · ${f.biblioteca}`}
                        {!f.activo && " · inactivo"}
                      </p>
                    </div>
                    <BarraFondo fondo={f} />
                    <div className="flex gap-1">
                      <Button variant="ghost" size="icon" disabled={p.bloqueado}
                              onClick={() => setFondo({ presupuesto: p, fondo: f })} aria-label={`Editar fondo ${f.codigo}`}>
                        <Pencil className="h-4 w-4" />
                      </Button>
                      <Button variant="ghost" size="icon" disabled={p.bloqueado}
                              onClick={() => accion(apiDelete(`/acquisitions/funds/${f.id}`), "Fondo eliminado")}
                              aria-label={`Eliminar fondo ${f.codigo}`}>
                        <Trash2 className="h-4 w-4" />
                      </Button>
                    </div>
                  </li>
                ))}
              </ul>
            )}
          </section>
        ))
      )}

      <Dialog open={editando !== null} onOpenChange={(v) => !v && setEditando(null)}>
        <DialogContent className="sm:max-w-md">
          {editando !== null && (
            <PresupuestoFormulario presupuesto={editando === "nuevo" ? null : editando}
                                   onCancel={() => setEditando(null)}
                                   onSaved={() => { setEditando(null); cargar() }} />
          )}
        </DialogContent>
      </Dialog>
      <Dialog open={fondo !== null} onOpenChange={(v) => !v && setFondo(null)}>
        <DialogContent className="sm:max-w-md">
          {fondo !== null && (
            <FondoFormulario {...fondo} onCancel={() => setFondo(null)}
                             onSaved={() => { setFondo(null); cargar() }} />
          )}
        </DialogContent>
      </Dialog>
    </div>
  )
}

function PresupuestoFormulario({ presupuesto, onCancel, onSaved }: {
  presupuesto: Presupuesto | null
  onCancel: () => void
  onSaved: () => void
}) {
  const ano = new Date().getFullYear()
  const [nombre, setNombre] = useState(presupuesto?.nombre ?? `Ejercicio ${ano}`)
  const [inicio, setInicio] = useState(presupuesto?.fecha_inicio ?? `${ano}-01-01`)
  const [fin, setFin] = useState(presupuesto?.fecha_fin ?? `${ano}-12-31`)
  const [monto, setMonto] = useState(presupuesto ? String(presupuesto.monto_total) : "")
  const [guardando, setGuardando] = useState(false)

  async function guardar(e: React.FormEvent) {
    e.preventDefault()
    setGuardando(true)
    const datos = { nombre, fecha_inicio: inicio, fecha_fin: fin, monto_total: Number(monto) }
    try {
      if (presupuesto) await apiPut(`/acquisitions/budgets/${presupuesto.id}`, datos)
      else await apiPost("/acquisitions/budgets", datos)
      toast.success(presupuesto ? "Presupuesto actualizado" : "Presupuesto creado")
      onSaved()
    } catch (error) {
      toast.error("No se pudo guardar", { description: mensajeDeError(error) })
    } finally {
      setGuardando(false)
    }
  }

  return (
    <form onSubmit={guardar}>
      <DialogHeader>
        <DialogTitle>{presupuesto ? "Editar presupuesto" : "Nuevo presupuesto"}</DialogTitle>
        <DialogDescription>Período y monto total; después se reparte en fondos.</DialogDescription>
      </DialogHeader>
      <div className="grid gap-4 py-4 sm:grid-cols-2">
        <div className="space-y-2 sm:col-span-2">
          <Label htmlFor="pres-nombre">Nombre</Label>
          <Input id="pres-nombre" required value={nombre} onChange={(e) => setNombre(e.target.value)} />
        </div>
        <div className="space-y-2">
          <Label htmlFor="pres-inicio">Desde</Label>
          <Input id="pres-inicio" type="date" required value={inicio} onChange={(e) => setInicio(e.target.value)} />
        </div>
        <div className="space-y-2">
          <Label htmlFor="pres-fin">Hasta</Label>
          <Input id="pres-fin" type="date" required value={fin} onChange={(e) => setFin(e.target.value)} />
        </div>
        <div className="space-y-2 sm:col-span-2">
          <Label htmlFor="pres-monto">Monto total (Bs.)</Label>
          <Input id="pres-monto" type="number" min={0} step="0.01" required value={monto}
                 onChange={(e) => setMonto(e.target.value)} />
        </div>
      </div>
      <DialogFooter>
        <Button type="button" variant="outline" onClick={onCancel}>Cancelar</Button>
        <Button type="submit" disabled={guardando || !nombre.trim() || monto === ""}>
          {guardando && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}
          Guardar
        </Button>
      </DialogFooter>
    </form>
  )
}

const TODAS = "todas"

function FondoFormulario({ presupuesto, fondo, onCancel, onSaved }: EdicionFondo & {
  onCancel: () => void
  onSaved: () => void
}) {
  const { sedes } = useSedes()
  const [codigo, setCodigo] = useState(fondo?.codigo ?? "")
  const [nombre, setNombre] = useState(fondo?.nombre ?? "")
  const [monto, setMonto] = useState(fondo ? String(fondo.asignado) : "")
  const [sede, setSede] = useState(fondo?.biblioteca_id ? String(fondo.biblioteca_id) : TODAS)
  const [activo, setActivo] = useState(fondo?.activo ?? true)
  const [guardando, setGuardando] = useState(false)
  const libre = presupuesto.sin_asignar + (fondo?.asignado ?? 0)

  async function guardar(e: React.FormEvent) {
    e.preventDefault()
    setGuardando(true)
    const datos = {
      codigo, nombre, monto_asignado: Number(monto), activo,
      biblioteca_id: sede === TODAS ? null : Number(sede),
    }
    try {
      if (fondo) await apiPut(`/acquisitions/funds/${fondo.id}`, datos)
      else await apiPost(`/acquisitions/budgets/${presupuesto.id}/funds`, datos)
      toast.success(fondo ? "Fondo actualizado" : "Fondo creado", { description: `${codigo.toUpperCase()} · ${nombre}` })
      onSaved()
    } catch (error) {
      toast.error("No se pudo guardar el fondo", { description: mensajeDeError(error) })
    } finally {
      setGuardando(false)
    }
  }

  return (
    <form onSubmit={guardar}>
      <DialogHeader>
        <DialogTitle>{fondo ? `Editar fondo ${fondo.codigo}` : "Nuevo fondo"}</DialogTitle>
        <DialogDescription>{presupuesto.nombre} · quedan {bs(libre)} por asignar</DialogDescription>
      </DialogHeader>
      <div className="grid gap-4 py-4 sm:grid-cols-3">
        <div className="space-y-2">
          <Label htmlFor="fondo-codigo">Código</Label>
          <Input id="fondo-codigo" required maxLength={20} className="font-mono uppercase" value={codigo}
                 placeholder="AGRO" onChange={(e) => setCodigo(e.target.value)} />
        </div>
        <div className="space-y-2 sm:col-span-2">
          <Label htmlFor="fondo-nombre">Nombre</Label>
          <Input id="fondo-nombre" required value={nombre} placeholder="Agronomía"
                 onChange={(e) => setNombre(e.target.value)} />
        </div>
        <div className="space-y-2 sm:col-span-3">
          <Label htmlFor="fondo-monto">Monto asignado (Bs.)</Label>
          <Input id="fondo-monto" type="number" min={0} max={libre} step="0.01" required value={monto}
                 onChange={(e) => setMonto(e.target.value)} />
        </div>
        {sedes.length > 1 && (
          <div className="space-y-2 sm:col-span-3">
            <Label htmlFor="fondo-sede">Sede</Label>
            <Select value={sede} onValueChange={setSede}>
              <SelectTrigger id="fondo-sede" className="w-full"><SelectValue /></SelectTrigger>
              <SelectContent>
                <SelectItem value={TODAS}>Todas</SelectItem>
                {sedes.map((s) => <SelectItem key={s.id} value={String(s.id)}>{s.nombre}</SelectItem>)}
              </SelectContent>
            </Select>
          </div>
        )}
        {fondo && (
          <div className="flex items-center gap-3 sm:col-span-3">
            <Switch id="fondo-activo" checked={activo} onCheckedChange={setActivo} />
            <Label htmlFor="fondo-activo">Activo (acepta pedidos nuevos)</Label>
          </div>
        )}
      </div>
      <DialogFooter>
        <Button type="button" variant="outline" onClick={onCancel}>Cancelar</Button>
        <Button type="submit" disabled={guardando || !codigo.trim() || !nombre.trim() || monto === ""}>
          {guardando && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}
          Guardar
        </Button>
      </DialogFooter>
    </form>
  )
}
