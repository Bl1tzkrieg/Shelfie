"use client"

import { useCallback, useEffect, useState } from "react"
import { Loader2, Pencil, Plus } from "lucide-react"
import { toast } from "sonner"

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
import { Textarea } from "@/components/ui/textarea"
import { apiGet, apiPost, apiPut, mensajeDeError } from "@/lib/api"
import type { Proveedor } from "@/lib/types"
import { Vacio } from "./comun"

export function ProveedoresPanel() {
  const [proveedores, setProveedores] = useState<Proveedor[] | null>(null)
  const [editando, setEditando] = useState<Proveedor | "nuevo" | null>(null)

  const cargar = useCallback(async () => {
    try {
      setProveedores(await apiGet<Proveedor[]>("/acquisitions/suppliers"))
    } catch (e) {
      toast.error("No se pudieron cargar los proveedores", { description: mensajeDeError(e) })
    }
  }, [])

  useEffect(() => {
    cargar()
  }, [cargar])

  return (
    <div className="space-y-4">
      <div className="flex justify-end">
        <Button onClick={() => setEditando("nuevo")}>
          <Plus className="mr-2 h-4 w-4" />
          Nuevo proveedor
        </Button>
      </div>
      {proveedores === null ? (
        <div className="py-12 text-center text-muted-foreground"><Loader2 className="mx-auto h-5 w-5 animate-spin" /></div>
      ) : proveedores.length === 0 ? (
        <Vacio>Todavía no hay proveedores.</Vacio>
      ) : (
        <div className="overflow-x-auto rounded-lg border bg-card">
          <table className="w-full text-sm">
            <thead className="bg-muted/50 text-left text-muted-foreground">
              <tr>
                <th className="px-4 py-3 font-medium">Proveedor</th>
                <th className="px-4 py-3 font-medium">Contacto</th>
                <th className="px-4 py-3 text-right font-medium">Descuento</th>
                <th className="px-4 py-3 text-right font-medium">Entrega</th>
                <th className="px-4 py-3 text-right font-medium">Pedidos en curso</th>
                <th className="px-4 py-3" />
              </tr>
            </thead>
            <tbody className="divide-y divide-border">
              {proveedores.map((p) => (
                <tr key={p.id} className={p.activo ? "" : "text-muted-foreground"}>
                  <td className="px-4 py-3">
                    <p className="font-medium text-foreground">
                      {p.nombre} {!p.activo && <Badge variant="outline" className="ml-1">Inactivo</Badge>}
                    </p>
                    {p.rif && <p className="font-mono text-xs text-muted-foreground">{p.rif}</p>}
                  </td>
                  <td className="px-4 py-3 text-muted-foreground">
                    {[p.contacto, p.email, p.telefono].filter(Boolean).join(" · ") || "—"}
                  </td>
                  <td className="px-4 py-3 text-right tabular-nums">{p.descuento} %</td>
                  <td className="px-4 py-3 text-right tabular-nums">
                    {p.dias_entrega !== null ? `${p.dias_entrega} días` : "—"}
                  </td>
                  <td className="px-4 py-3 text-right tabular-nums">{p.pedidos_vivos ?? 0}</td>
                  <td className="px-4 py-3 text-right">
                    <Button variant="ghost" size="icon" onClick={() => setEditando(p)} aria-label={`Editar ${p.nombre}`}>
                      <Pencil className="h-4 w-4" />
                    </Button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
      <Dialog open={editando !== null} onOpenChange={(v) => !v && setEditando(null)}>
        <DialogContent className="sm:max-w-lg">
          {editando !== null && (
            <ProveedorFormulario proveedor={editando === "nuevo" ? null : editando}
                                 onCancel={() => setEditando(null)}
                                 onSaved={() => { setEditando(null); cargar() }} />
          )}
        </DialogContent>
      </Dialog>
    </div>
  )
}

function ProveedorFormulario({ proveedor, onCancel, onSaved }: {
  proveedor: Proveedor | null
  onCancel: () => void
  onSaved: () => void
}) {
  const [f, setF] = useState({
    nombre: proveedor?.nombre ?? "",
    rif: proveedor?.rif ?? "",
    contacto: proveedor?.contacto ?? "",
    email: proveedor?.email ?? "",
    telefono: proveedor?.telefono ?? "",
    direccion: proveedor?.direccion ?? "",
    descuento: String(proveedor?.descuento ?? 0),
    dias_entrega: proveedor?.dias_entrega != null ? String(proveedor.dias_entrega) : "",
    notas: proveedor?.notas ?? "",
  })
  const [activo, setActivo] = useState(proveedor?.activo ?? true)
  const [guardando, setGuardando] = useState(false)
  const campo = (k: keyof typeof f) => (e: React.ChangeEvent<HTMLInputElement | HTMLTextAreaElement>) =>
    setF((x) => ({ ...x, [k]: e.target.value }))

  async function guardar(e: React.FormEvent) {
    e.preventDefault()
    setGuardando(true)
    const datos = {
      ...f,
      email: f.email.trim() || null,
      descuento: Number(f.descuento || 0),
      dias_entrega: f.dias_entrega === "" ? null : Number(f.dias_entrega),
      activo,
    }
    try {
      if (proveedor) await apiPut(`/acquisitions/suppliers/${proveedor.id}`, datos)
      else await apiPost("/acquisitions/suppliers", datos)
      toast.success(proveedor ? "Proveedor actualizado" : "Proveedor creado", { description: f.nombre })
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
        <DialogTitle>{proveedor ? `Editar ${proveedor.nombre}` : "Nuevo proveedor"}</DialogTitle>
        <DialogDescription>El descuento se propone en cada línea; los días de entrega marcan los atrasos.</DialogDescription>
      </DialogHeader>
      <div className="grid gap-4 py-4 sm:grid-cols-2">
        <div className="space-y-2 sm:col-span-2">
          <Label htmlFor="prov-nombre">Nombre</Label>
          <Input id="prov-nombre" required value={f.nombre} onChange={campo("nombre")} />
        </div>
        <div className="space-y-2">
          <Label htmlFor="prov-rif">RIF</Label>
          <Input id="prov-rif" value={f.rif} placeholder="J-12345678-9" onChange={campo("rif")} />
        </div>
        <div className="space-y-2">
          <Label htmlFor="prov-contacto">Persona de contacto</Label>
          <Input id="prov-contacto" value={f.contacto} onChange={campo("contacto")} />
        </div>
        <div className="space-y-2">
          <Label htmlFor="prov-email">Correo</Label>
          <Input id="prov-email" type="email" value={f.email} onChange={campo("email")} />
        </div>
        <div className="space-y-2">
          <Label htmlFor="prov-telefono">Teléfono</Label>
          <Input id="prov-telefono" value={f.telefono} onChange={campo("telefono")} />
        </div>
        <div className="space-y-2 sm:col-span-2">
          <Label htmlFor="prov-direccion">Dirección</Label>
          <Input id="prov-direccion" value={f.direccion} onChange={campo("direccion")} />
        </div>
        <div className="space-y-2">
          <Label htmlFor="prov-descuento">Descuento habitual (%)</Label>
          <Input id="prov-descuento" type="number" min={0} max={100} step="0.01" value={f.descuento} onChange={campo("descuento")} />
        </div>
        <div className="space-y-2">
          <Label htmlFor="prov-dias">Días de entrega</Label>
          <Input id="prov-dias" type="number" min={0} value={f.dias_entrega} placeholder="Sin plazo" onChange={campo("dias_entrega")} />
        </div>
        <div className="space-y-2 sm:col-span-2">
          <Label htmlFor="prov-notas">Notas</Label>
          <Textarea id="prov-notas" rows={2} value={f.notas} onChange={campo("notas")} />
        </div>
        {proveedor && (
          <div className="flex items-center gap-3 sm:col-span-2">
            <Switch id="prov-activo" checked={activo} onCheckedChange={setActivo} />
            <Label htmlFor="prov-activo">Activo (recibe pedidos nuevos)</Label>
          </div>
        )}
      </div>
      <DialogFooter>
        <Button type="button" variant="outline" onClick={onCancel}>Cancelar</Button>
        <Button type="submit" disabled={guardando || !f.nombre.trim()}>
          {guardando && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}
          {proveedor ? "Guardar" : "Crear proveedor"}
        </Button>
      </DialogFooter>
    </form>
  )
}
