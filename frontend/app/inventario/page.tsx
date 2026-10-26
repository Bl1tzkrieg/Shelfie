"use client"

import { useCallback, useEffect, useState } from "react"
import Link from "next/link"
import { useRouter } from "next/navigation"
import { ClipboardCheck, Loader2, Plus } from "lucide-react"
import { toast } from "sonner"

import { useSesion } from "@/components/auth/sesion-provider"
import { alcance } from "@/components/inventario/alcance"
import { AppLayout } from "@/components/layout/app-layout"
import { Header } from "@/components/layout/header"
import { useSedes } from "@/components/layout/sede-provider"
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
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select"
import { Switch } from "@/components/ui/switch"
import { apiGet, apiPost, mensajeDeError } from "@/lib/api"
import type { InventarioDetalle, InventarioResumen, OpcionesRegla } from "@/lib/types"
import { cn } from "@/lib/utils"

const TODAS = "todas"

export default function InventariosPage() {
  const { tienePermiso } = useSesion()
  const [inventarios, setInventarios] = useState<InventarioResumen[] | null>(null)
  const [nuevo, setNuevo] = useState(false)

  const cargar = useCallback(async () => {
    try {
      setInventarios(await apiGet<InventarioResumen[]>("/inventories"))
    } catch (e) {
      toast.error("No se pudieron cargar los inventarios", { description: mensajeDeError(e) })
    }
  }, [])

  useEffect(() => {
    cargar()
  }, [cargar])

  return (
    <AppLayout>
      <Header title="Inventario" description="Lo que hay en el estante, comparado con lo que debería haber" />
      <div className="space-y-4 p-4 sm:p-6">
        {tienePermiso("catalogo") && (
          <div className="flex justify-end">
            <Button onClick={() => setNuevo(true)}><Plus className="mr-2 h-4 w-4" />Nuevo inventario</Button>
          </div>
        )}
        {!inventarios ? (
          <Loader2 className="mx-auto mt-8 h-5 w-5 animate-spin text-muted-foreground" />
        ) : inventarios.length === 0 ? (
          <div className="rounded-lg border border-dashed border-border py-12 text-center text-muted-foreground">
            <ClipboardCheck className="mx-auto mb-3 h-8 w-8" aria-hidden />
            Todavía no hay inventarios. Empieza uno por sede o por un tramo de signaturas.
          </div>
        ) : (
          <ul className="divide-y divide-border rounded-lg border border-border bg-card shadow-papel">
            {inventarios.map((i) => (
              <li key={i.id}>
                <Link href={`/inventario/${i.id}`} className="flex flex-col gap-1 px-4 py-3 hover:bg-muted/30 sm:flex-row sm:items-center sm:justify-between">
                  <div className="min-w-0">
                    <p className="truncate font-medium text-foreground">{i.nombre}</p>
                    <p className="text-sm text-muted-foreground">
                      {alcance(i)} · {i.lecturas} lectura{i.lecturas === 1 ? "" : "s"}
                      {i.creado_por && ` · ${i.creado_por}`}
                    </p>
                  </div>
                  <div className="flex items-center gap-3 text-sm">
                    <span className="text-muted-foreground tabular-nums">{i.fecha_cierre ?? i.fecha_inicio}</span>
                    <span className={cn("rounded-full px-2.5 py-0.5 text-xs font-medium",
                                        i.estado === "Abierto" ? "bg-primary/10 text-primary" : "bg-muted text-muted-foreground")}>
                      {i.estado}
                    </span>
                  </div>
                </Link>
              </li>
            ))}
          </ul>
        )}
      </div>
      <NuevoInventarioDialog open={nuevo} onOpenChange={setNuevo} />
    </AppLayout>
  )
}

function NuevoInventarioDialog({ open, onOpenChange }: { open: boolean; onOpenChange: (v: boolean) => void }) {
  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-md">
        {open && <FormularioInventario onCerrar={() => onOpenChange(false)} />}
      </DialogContent>
    </Dialog>
  )
}

function FormularioInventario({ onCerrar }: { onCerrar: () => void }) {
  const router = useRouter()
  const { sedes, sedeId } = useSedes()
  const [tipos, setTipos] = useState<OpcionesRegla["tipos_item"]>([])
  const [form, setForm] = useState({
    nombre: "", sede: sedeId ? String(sedeId) : TODAS, tipo: TODAS, desde: "", hasta: "", devolver: false,
  })
  const [enviando, setEnviando] = useState(false)

  useEffect(() => {
    apiGet<OpcionesRegla>("/circulation-rules/options").then((o) => setTipos(o.tipos_item)).catch(() => setTipos([]))
  }, [])

  async function crear(e: React.FormEvent) {
    e.preventDefault()
    setEnviando(true)
    try {
      const inv = await apiPost<InventarioDetalle>("/inventories", {
        nombre: form.nombre.trim() || null,
        biblioteca_id: form.sede === TODAS ? null : Number(form.sede),
        tipo_item_codigo: form.tipo === TODAS ? null : form.tipo,
        signatura_desde: form.desde.trim() || null,
        signatura_hasta: form.hasta.trim() || null,
        devolver_prestados: form.devolver,
      })
      toast.success("Inventario abierto", { description: `${inv.esperados} ejemplares esperados` })
      router.push(`/inventario/${inv.id}`)
    } catch (error) {
      toast.error("No se pudo abrir el inventario", { description: mensajeDeError(error) })
      setEnviando(false)
    }
  }

  return (
    <form onSubmit={crear}>
      <DialogHeader>
        <DialogTitle>Nuevo inventario</DialogTitle>
        <DialogDescription>
          Se esperan los ejemplares disponibles del alcance que elijas. Lo que no se lea quedará como faltante.
        </DialogDescription>
      </DialogHeader>
      <div className="space-y-4 py-4">
        <div className="space-y-2">
          <Label htmlFor="inv-nombre">Nombre (opcional)</Label>
          <Input id="inv-nombre" value={form.nombre} maxLength={120} placeholder="Se arma con la sede, el tramo y la fecha"
                 onChange={(e) => setForm((f) => ({ ...f, nombre: e.target.value }))} />
        </div>
        <div className="grid gap-4 sm:grid-cols-2">
          <div className="space-y-2">
            <Label htmlFor="inv-sede">Sede</Label>
            <Select value={form.sede} onValueChange={(v) => setForm((f) => ({ ...f, sede: v }))}>
              <SelectTrigger id="inv-sede" className="w-full"><SelectValue /></SelectTrigger>
              <SelectContent>
                <SelectItem value={TODAS}>Todas</SelectItem>
                {sedes.map((s) => <SelectItem key={s.id} value={String(s.id)}>{s.nombre}</SelectItem>)}
              </SelectContent>
            </Select>
          </div>
          <div className="space-y-2">
            <Label htmlFor="inv-tipo">Tipo de ítem</Label>
            <Select value={form.tipo} onValueChange={(v) => setForm((f) => ({ ...f, tipo: v }))}>
              <SelectTrigger id="inv-tipo" className="w-full"><SelectValue /></SelectTrigger>
              <SelectContent>
                <SelectItem value={TODAS}>Todos</SelectItem>
                {tipos.map((t) => <SelectItem key={t.codigo} value={t.codigo}>{t.nombre}</SelectItem>)}
              </SelectContent>
            </Select>
          </div>
          <div className="space-y-2">
            <Label htmlFor="inv-desde">Signatura desde</Label>
            <Input id="inv-desde" value={form.desde} placeholder="600" onChange={(e) => setForm((f) => ({ ...f, desde: e.target.value }))} />
          </div>
          <div className="space-y-2">
            <Label htmlFor="inv-hasta">Signatura hasta</Label>
            <Input id="inv-hasta" value={form.hasta} placeholder="699" onChange={(e) => setForm((f) => ({ ...f, hasta: e.target.value }))} />
          </div>
        </div>
        <div className="flex items-start gap-3 rounded-lg border border-border p-3">
          <Switch id="inv-devolver" checked={form.devolver} onCheckedChange={(v) => setForm((f) => ({ ...f, devolver: v }))}
                  aria-describedby="inv-devolver-ayuda" />
          <div className="space-y-0.5">
            <Label htmlFor="inv-devolver">Devolver los prestados que aparezcan</Label>
            <p id="inv-devolver-ayuda" className="text-xs text-muted-foreground">
              Si está en el estante, no puede estar prestado: se registra la devolución (con la multa si estaba vencido).
            </p>
          </div>
        </div>
      </div>
      <DialogFooter>
        <Button type="button" variant="outline" onClick={onCerrar}>Cancelar</Button>
        <Button type="submit" disabled={enviando}>
          {enviando && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}Abrir inventario
        </Button>
      </DialogFooter>
    </form>
  )
}
