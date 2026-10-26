"use client"

import { useCallback, useEffect, useMemo, useState } from "react"
import Link from "next/link"
import { useParams } from "next/navigation"
import { ArrowLeft, Ban, Loader2, Mail, MoreHorizontal, PackageCheck, Pencil, Plus, RefreshCw } from "lucide-react"
import { toast } from "sonner"

import { AppLayout } from "@/components/layout/app-layout"
import { Header } from "@/components/layout/header"
import { EstadoFasciculoBadge, fechaIso } from "@/components/seriadas/comun"
import { RecibirFasciculoDialog } from "@/components/seriadas/recibir-fasciculo-dialog"
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
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
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
import { Textarea } from "@/components/ui/textarea"
import { apiGet, apiPost, apiPut, mensajeDeError } from "@/lib/api"
import type { Fasciculo, Suscripcion } from "@/lib/types"

type Dialogo = "editar" | "renovar" | "especial" | "cancelar" | null

export default function SuscripcionPage() {
  const { id } = useParams<{ id: string }>()
  const [s, setS] = useState<Suscripcion | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [dialogo, setDialogo] = useState<Dialogo>(null)
  const [recibiendo, setRecibiendo] = useState<Fasciculo | null>(null)

  const cargar = useCallback(async () => {
    try {
      setS(await apiGet<Suscripcion>(`/serials/subscriptions/${id}`))
    } catch (e) {
      setError(mensajeDeError(e))
    }
  }, [id])

  useEffect(() => {
    cargar()
  }, [cargar])

  const porAno = useMemo(() => {
    const grupos = new Map<string, Fasciculo[]>()
    for (const f of s?.fasciculos ?? []) {
      const ano = f.fecha_esperada?.slice(0, 4) ?? "Sin fecha"
      grupos.set(ano, [...(grupos.get(ano) ?? []), f])
    }
    return [...grupos.entries()]
  }, [s])

  async function reclamarPorCorreo() {
    if (!s?.proveedor_id) return
    try {
      const r = await apiPost<{ reclamados: number; destinatario?: string }>(
        `/serials/suppliers/${s.proveedor_id}/claim?suscripcion_id=${s.id}`)
      toast.success(r.reclamados ? `Reclamo enviado a ${r.destinatario}` : "No había números por reclamar",
                    { description: r.reclamados ? `${r.reclamados} número(s) quedan como reclamados` : undefined })
      setS(await apiGet<Suscripcion>(`/serials/subscriptions/${s.id}`))
    } catch (e) {
      toast.error("No se pudo reclamar", { description: mensajeDeError(e) })
    }
  }

  async function accion(ruta: string, aviso: string, cuerpo: unknown = {}) {
    try {
      setS(await apiPost<Suscripcion>(ruta, cuerpo))
      toast.success(aviso)
    } catch (e) {
      toast.error("No se pudo completar", { description: mensajeDeError(e) })
    }
  }

  if (!s) {
    return (
      <AppLayout permiso="seriadas">
        <Header title="Suscripción" />
        <div className="p-6 text-center text-muted-foreground">
          {error ? `No se pudo cargar: ${error}` : <Loader2 className="mx-auto h-5 w-5 animate-spin" />}
        </div>
      </AppLayout>
    )
  }

  const activa = s.estado === "Activa"
  const atrasados = (s.fasciculos ?? []).filter((f) => f.dias_atraso)

  return (
    <AppLayout permiso="seriadas">
      <Header title={s.titulo} description={`${s.periodicidad}${s.issn ? ` · ISSN ${s.issn}` : ""}`} />
      <div className="space-y-6 p-6">
        <Link href="/seriadas" className="inline-flex items-center gap-1 text-sm text-muted-foreground hover:text-foreground">
          <ArrowLeft className="h-4 w-4" />
          Seriadas
        </Link>

        <div className="flex flex-col gap-4 rounded-lg border bg-card shadow-papel p-5 lg:flex-row lg:items-start lg:justify-between">
          <dl className="grid gap-x-8 gap-y-2 text-sm sm:grid-cols-2 lg:grid-cols-3">
            <div><dt className="text-muted-foreground">Estado</dt><dd className="flex gap-1">
              <Badge variant={activa ? "secondary" : "outline"}>{s.estado}</Badge>
              {s.por_vencer && <Badge variant="outline">Por renovar</Badge>}
            </dd></div>
            <div><dt className="text-muted-foreground">Numeración</dt><dd className="font-mono text-xs">{s.numeracion || "—"}{s.numeros_por_volumen ? ` · ${s.numeros_por_volumen} por volumen` : ""}</dd></div>
            <div><dt className="text-muted-foreground">Próximo</dt><dd>{s.proximo ? `${s.proximo.numero} · ${fechaIso(s.proximo.fecha_esperada)}` : "—"}</dd></div>
            <div><dt className="text-muted-foreground">Proveedor</dt><dd>{s.proveedor_nombre ?? "Sin proveedor"}</dd></div>
            <div><dt className="text-muted-foreground">Vigencia</dt><dd>{fechaIso(s.fecha_inicio)} – {s.fecha_fin ? fechaIso(s.fecha_fin) : "sin fin"}</dd></div>
            <div><dt className="text-muted-foreground">Reclamar a los</dt><dd>{s.dias_gracia} días de la fecha esperada</dd></div>
            {s.biblioteca && <div><dt className="text-muted-foreground">La recibe</dt><dd>{s.biblioteca}</dd></div>}
            {s.biblio_id && <div><dt className="text-muted-foreground">Catálogo</dt><dd><Link href={`/catalogo/${s.biblio_id}`} className="text-primary hover:underline">Ver la ficha y sus ejemplares</Link></dd></div>}
            {s.notas && <div className="sm:col-span-2 lg:col-span-3"><dt className="text-muted-foreground">Notas</dt><dd>{s.notas}</dd></div>}
          </dl>
          <div className="flex shrink-0 flex-wrap gap-2">
            <Button variant="outline" onClick={() => setDialogo("especial")}>
              <Plus className="mr-2 h-4 w-4" />
              Número especial
            </Button>
            <Button variant="outline" onClick={() => setDialogo("editar")}>
              <Pencil className="mr-2 h-4 w-4" />
              Editar
            </Button>
            {(!activa || s.por_vencer) && (
              <Button variant="outline" onClick={() => setDialogo("renovar")}>
                <RefreshCw className="mr-2 h-4 w-4" />
                Renovar
              </Button>
            )}
            {activa && (
              <Button variant="outline" onClick={() => setDialogo("cancelar")}>
                <Ban className="mr-2 h-4 w-4" />
                Cancelar
              </Button>
            )}
          </div>
        </div>

        {atrasados.length > 0 && s.proveedor_email && (
          <div className="flex flex-col gap-2 rounded-lg border border-destructive/40 bg-destructive/5 p-4 sm:flex-row sm:items-center sm:justify-between">
            <p className="text-sm text-foreground">
              {atrasados.length} número(s) atrasado(s): {atrasados.map((f) => f.numero).join(", ")}.
            </p>
            <Button size="sm" variant="outline" onClick={reclamarPorCorreo}>
              <Mail className="mr-2 h-4 w-4" />
              Reclamar por correo
            </Button>
          </div>
        )}

        <section className="space-y-4">
          <h3 className="font-semibold text-foreground">Kardex</h3>
          {porAno.length === 0 ? (
            <div className="rounded-lg border border-dashed bg-card py-12 text-center text-sm text-muted-foreground">
              Sin fascículos. {s.frecuencia_unidad === "irregular" && "Registra cada número con «Número especial»."}
            </div>
          ) : (
            porAno.map(([ano, lista]) => (
              <div key={ano} className="overflow-hidden rounded-lg border bg-card shadow-papel">
                <div className="flex items-baseline justify-between border-b bg-muted/40 px-4 py-2">
                  <span className="font-semibold text-foreground">{ano}</span>
                  <span className="text-xs text-muted-foreground">
                    {lista.filter((f) => f.estado === "Recibido").length} de {lista.length} recibidos
                  </span>
                </div>
                <ul className="divide-y divide-border">
                  {lista.map((f) => {
                    const abierto = f.estado === "Esperado" || f.estado === "Reclamado"
                    return (
                      <li key={f.id} className="flex flex-col gap-2 px-4 py-2.5 text-sm sm:flex-row sm:items-center sm:justify-between">
                        <div className="min-w-0">
                          <p className="font-medium text-foreground">{f.numero}</p>
                          <p className="text-xs text-muted-foreground">
                            Esperado el {fechaIso(f.fecha_esperada)}
                            {f.fecha_recepcion && ` · llegó el ${f.fecha_recepcion}`}
                            {f.codigo_barras && ` · ${f.codigo_barras}`}
                            {f.reclamos > 0 && ` · ${f.reclamos} reclamo(s)`}
                            {f.notas && ` · ${f.notas}`}
                          </p>
                        </div>
                        <div className="flex items-center gap-2">
                          <EstadoFasciculoBadge estado={f.estado} atraso={f.dias_atraso} />
                          {abierto && (
                            <>
                              <Button size="sm" onClick={() => setRecibiendo(f)} aria-label={`Recibir ${f.numero}`}>
                                <PackageCheck className="mr-2 h-4 w-4" />
                                Recibir
                              </Button>
                              <DropdownMenu>
                                <DropdownMenuTrigger asChild>
                                  <Button size="sm" variant="ghost" aria-label={`Más acciones para ${f.numero}`}>
                                    <MoreHorizontal className="h-4 w-4" />
                                  </Button>
                                </DropdownMenuTrigger>
                                <DropdownMenuContent align="end">
                                  <DropdownMenuItem onClick={() => accion(`/serials/issues/${f.id}/claim`, "Reclamo registrado")}>
                                    Marcar reclamado
                                  </DropdownMenuItem>
                                  <DropdownMenuItem onClick={() => accion(`/serials/issues/${f.id}/missing`, "Marcado como faltante")}>
                                    No llegará (faltante)
                                  </DropdownMenuItem>
                                </DropdownMenuContent>
                              </DropdownMenu>
                            </>
                          )}
                        </div>
                      </li>
                    )
                  })}
                </ul>
              </div>
            ))
          )}
        </section>
      </div>

      <RecibirFasciculoDialog
        fasciculo={recibiendo}
        titulo={s.titulo}
        crearEjemplar={s.crear_ejemplares}
        onOpenChange={(v) => !v && setRecibiendo(null)}
        onRecibido={() => {
          setRecibiendo(null)
          cargar()
        }}
      />

      <Dialog open={dialogo === "editar" || dialogo === "renovar" || dialogo === "especial"}
              onOpenChange={(v) => !v && setDialogo(null)}>
        <DialogContent className="sm:max-w-md">
          {dialogo === "editar" && <Editar s={s} onListo={(n) => { setS(n); setDialogo(null) }} onCancel={() => setDialogo(null)} />}
          {dialogo === "renovar" && <Renovar s={s} onListo={(n) => { setS(n); setDialogo(null) }} onCancel={() => setDialogo(null)} />}
          {dialogo === "especial" && <Especial s={s} onListo={() => { setDialogo(null); cargar() }} onCancel={() => setDialogo(null)} />}
        </DialogContent>
      </Dialog>

      <AlertDialog open={dialogo === "cancelar"} onOpenChange={(v) => !v && setDialogo(null)}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>¿Cancelar la suscripción?</AlertDialogTitle>
            <AlertDialogDescription>
              Los números que se esperaban quedan como faltantes. Lo ya recibido sigue en el catálogo.
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel>Volver</AlertDialogCancel>
            <AlertDialogAction onClick={() => accion(`/serials/subscriptions/${s.id}/cancel`, "Suscripción cancelada")}>
              Cancelar suscripción
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </AppLayout>
  )
}

const SIN_PROVEEDOR = "ninguno"

function Editar({ s, onListo, onCancel }: { s: Suscripcion; onListo: (s: Suscripcion) => void; onCancel: () => void }) {
  const [proveedores, setProveedores] = useState<{ id: number; nombre: string }[]>([])
  const [proveedor, setProveedor] = useState(s.proveedor_id ? String(s.proveedor_id) : SIN_PROVEEDOR)
  const [fin, setFin] = useState(s.fecha_fin ?? "")
  const [gracia, setGracia] = useState(String(s.dias_gracia))
  const [notas, setNotas] = useState(s.notas ?? "")
  const [crear, setCrear] = useState(s.crear_ejemplares)
  const [guardando, setGuardando] = useState(false)

  useEffect(() => {
    apiGet<{ id: number; nombre: string }[]>("/serials/suppliers").then(setProveedores).catch(() => setProveedores([]))
  }, [])

  async function guardar(e: React.FormEvent) {
    e.preventDefault()
    setGuardando(true)
    try {
      onListo(await apiPut<Suscripcion>(`/serials/subscriptions/${s.id}`, {
        proveedor_id: proveedor === SIN_PROVEEDOR ? null : Number(proveedor),
        fecha_fin: fin || null,
        dias_gracia: Number(gracia || 0),
        notas,
        crear_ejemplares: crear,
      }))
      toast.success("Suscripción actualizada")
    } catch (error) {
      toast.error("No se pudo guardar", { description: mensajeDeError(error) })
    } finally {
      setGuardando(false)
    }
  }

  return (
    <form onSubmit={guardar}>
      <DialogHeader>
        <DialogTitle>Editar suscripción</DialogTitle>
        <DialogDescription>El patrón de numeración se conserva; afecta a los próximos números.</DialogDescription>
      </DialogHeader>
      <div className="space-y-4 py-4">
        <div className="space-y-2">
          <Label htmlFor="ed-proveedor">Proveedor</Label>
          <Select value={proveedor} onValueChange={setProveedor}>
            <SelectTrigger id="ed-proveedor" className="w-full"><SelectValue /></SelectTrigger>
            <SelectContent>
              <SelectItem value={SIN_PROVEEDOR}>Sin proveedor</SelectItem>
              {proveedores.map((p) => <SelectItem key={p.id} value={String(p.id)}>{p.nombre}</SelectItem>)}
            </SelectContent>
          </Select>
        </div>
        <div className="grid gap-4 sm:grid-cols-2">
          <div className="space-y-2">
            <Label htmlFor="ed-fin">Vence el</Label>
            <Input id="ed-fin" type="date" value={fin} onChange={(e) => setFin(e.target.value)} />
          </div>
          <div className="space-y-2">
            <Label htmlFor="ed-gracia">Días de gracia</Label>
            <Input id="ed-gracia" type="number" min={0} value={gracia} onChange={(e) => setGracia(e.target.value)} />
          </div>
        </div>
        <div className="flex items-center gap-3">
          <Switch id="ed-crear" checked={crear} onCheckedChange={setCrear} />
          <Label htmlFor="ed-crear">Dar de alta un ejemplar por número</Label>
        </div>
        <div className="space-y-2">
          <Label htmlFor="ed-notas">Notas</Label>
          <Textarea id="ed-notas" rows={2} value={notas} onChange={(e) => setNotas(e.target.value)} />
        </div>
      </div>
      <DialogFooter>
        <Button type="button" variant="outline" onClick={onCancel}>Cancelar</Button>
        <Button type="submit" disabled={guardando}>{guardando && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}Guardar</Button>
      </DialogFooter>
    </form>
  )
}

function Renovar({ s, onListo, onCancel }: { s: Suscripcion; onListo: (s: Suscripcion) => void; onCancel: () => void }) {
  const sugerida = (() => {
    const base = s.fecha_fin ? new Date(`${s.fecha_fin}T12:00:00`) : new Date()
    base.setFullYear(base.getFullYear() + 1)
    return base.toLocaleDateString("en-CA")
  })()
  const [fin, setFin] = useState(sugerida)
  const [guardando, setGuardando] = useState(false)

  async function renovar(e: React.FormEvent) {
    e.preventDefault()
    setGuardando(true)
    try {
      onListo(await apiPost<Suscripcion>(`/serials/subscriptions/${s.id}/renew`, { fecha_fin: fin || null }))
      toast.success("Suscripción renovada")
    } catch (error) {
      toast.error("No se pudo renovar", { description: mensajeDeError(error) })
    } finally {
      setGuardando(false)
    }
  }

  return (
    <form onSubmit={renovar}>
      <DialogHeader>
        <DialogTitle>Renovar suscripción</DialogTitle>
        <DialogDescription>Queda activa hasta la nueva fecha y se vuelve a esperar el próximo número.</DialogDescription>
      </DialogHeader>
      <div className="space-y-2 py-4">
        <Label htmlFor="ren-fin">Nueva fecha de fin</Label>
        <Input id="ren-fin" type="date" value={fin} onChange={(e) => setFin(e.target.value)} />
      </div>
      <DialogFooter>
        <Button type="button" variant="outline" onClick={onCancel}>Cancelar</Button>
        <Button type="submit" disabled={guardando}>{guardando && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}Renovar</Button>
      </DialogFooter>
    </form>
  )
}

function Especial({ s, onListo, onCancel }: { s: Suscripcion; onListo: () => void; onCancel: () => void }) {
  const [numero, setNumero] = useState("")
  const [fecha, setFecha] = useState(() => new Date().toLocaleDateString("en-CA"))
  const [guardando, setGuardando] = useState(false)

  async function crear(e: React.FormEvent) {
    e.preventDefault()
    setGuardando(true)
    try {
      await apiPost(`/serials/subscriptions/${s.id}/issues`, { numero: numero.trim(), fecha_esperada: fecha })
      toast.success("Número registrado", { description: numero })
      onListo()
    } catch (error) {
      toast.error("No se pudo registrar", { description: mensajeDeError(error) })
    } finally {
      setGuardando(false)
    }
  }

  return (
    <form onSubmit={crear}>
      <DialogHeader>
        <DialogTitle>Número especial</DialogTitle>
        <DialogDescription>Fuera del patrón: suplementos, números especiales o una publicación irregular.</DialogDescription>
      </DialogHeader>
      <div className="grid gap-4 py-4 sm:grid-cols-2">
        <div className="space-y-2 sm:col-span-2">
          <Label htmlFor="esp-numero">Número</Label>
          <Input id="esp-numero" required autoFocus value={numero} placeholder="Suplemento 2026" onChange={(e) => setNumero(e.target.value)} />
        </div>
        <div className="space-y-2">
          <Label htmlFor="esp-fecha">Se espera el</Label>
          <Input id="esp-fecha" type="date" value={fecha} onChange={(e) => setFecha(e.target.value)} />
        </div>
      </div>
      <DialogFooter>
        <Button type="button" variant="outline" onClick={onCancel}>Cancelar</Button>
        <Button type="submit" disabled={guardando || !numero.trim()}>{guardando && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}Registrar</Button>
      </DialogFooter>
    </form>
  )
}
