"use client"

import { Suspense, useCallback, useEffect, useRef, useState } from "react"
import Link from "next/link"
import { usePathname, useRouter, useSearchParams } from "next/navigation"
import { ArrowRight, BookmarkCheck, Loader2, PackageCheck, Plus, RefreshCw, ScanBarcode, Send, X } from "lucide-react"
import { toast } from "sonner"

import { useSesion } from "@/components/auth/sesion-provider"
import { avisarDevolucion } from "@/components/circulacion/aviso-devolucion"
import { AppLayout } from "@/components/layout/app-layout"
import { Header } from "@/components/layout/header"
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
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs"
import { Textarea } from "@/components/ui/textarea"
import { apiGet, apiPost, mensajeDeError } from "@/lib/api"
import type {
  MotivoTraslado,
  ResultadoDevolucion,
  ResumenTraslados,
  Traslado,
  VistaTraslados,
} from "@/lib/types"
import { cn } from "@/lib/utils"

const VISTAS: VistaTraslados[] = ["por_recibir", "por_enviar", "enviados", "historial"]

const MOTIVO: Record<MotivoTraslado, string> = {
  reserva: "Reserva",
  retorno: "Vuelve a su sede",
  manual: "Manual",
}

export default function TrasladosPage() {
  return (
    <AppLayout>
      <Header title="Traslados" description="Ejemplares que viajan entre sedes" />
      <Suspense fallback={null}>
        <GestionDeTraslados />
      </Suspense>
    </AppLayout>
  )
}

function GestionDeTraslados() {
  const router = useRouter()
  const pathname = usePathname()
  const params = useSearchParams()
  const { tienePermiso } = useSesion()
  const { sedes, sedeId, sede } = useSedes()
  const puedeOperar = tienePermiso("circulacion")

  const vistaUrl = params.get("vista") as VistaTraslados | null
  const vista: VistaTraslados = vistaUrl && VISTAS.includes(vistaUrl) ? vistaUrl : "por_recibir"
  const [todasLasSedes, setTodasLasSedes] = useState(false)
  const [filas, setFilas] = useState<Traslado[] | null>(null)
  const [resumen, setResumen] = useState<ResumenTraslados | null>(null)
  const [cargando, setCargando] = useState(false)
  const [nuevo, setNuevo] = useState(false)
  const [trabajando, setTrabajando] = useState<number | null>(null)

  // Solo la última petición pinta: al cambiar de pestaña rápido, la lista de otra vista
  // que llega tarde no queda bajo la pestaña activa.
  const ultima = useRef(0)
  const cargar = useCallback(async () => {
    const id = ++ultima.current
    setCargando(true)
    try {
      const [f, r] = await Promise.all([
        apiGet<Traslado[]>(`/circulation/transfers?vista=${vista}&todas_las_sedes=${todasLasSedes}`),
        apiGet<ResumenTraslados>("/circulation/transfers/summary"),
      ])
      if (id !== ultima.current) return
      setFilas(f)
      setResumen(r)
    } catch (error) {
      if (id === ultima.current) {
        toast.error("No se pudieron cargar los traslados", { description: mensajeDeError(error) })
      }
    } finally {
      if (id === ultima.current) setCargando(false)
    }
  }, [vista, todasLasSedes])

  useEffect(() => {
    cargar()
  }, [cargar, sedeId])

  function irA(v: string) {
    setFilas(null)
    const p = new URLSearchParams(params.toString())
    p.set("vista", v)
    router.replace(`${pathname}?${p}`, { scroll: false })
  }

  async function operar(t: Traslado, accion: "receive" | "send" | "cancel") {
    setTrabajando(t.id)
    try {
      const r = await apiPost<
        Traslado & { resultado?: Pick<ResultadoDevolucion, "accion" | "reserva" | "traslado"> }
      >(
        `/circulation/transfers/${t.id}/${accion}`,
      )
      if (accion === "receive" && r.resultado) {
        avisarDevolucion({
          mensaje: "Traslado recibido",
          multa_aplicada: 0,
          nuevo_estado_item: "",
          recuperado: false,
          reintegro: 0,
          lector_reintegro: null,
          ...r.resultado,
        })
      } else {
        toast.success(accion === "send" ? "Marcado como enviado" : "Traslado cancelado", {
          description: `${t.barcode} · ${t.title}`,
        })
      }
      await cargar()
    } catch (error) {
      toast.error("No se pudo completar", { description: mensajeDeError(error) })
    } finally {
      setTrabajando(null)
    }
  }

  if (sedes.length > 0 && sedes.length < 2) {
    return (
      <div className="p-6">
        <div className="mx-auto max-w-xl rounded-lg border border-dashed bg-card p-8 text-center">
          <p className="font-medium text-foreground">La biblioteca tiene una sola sede</p>
          <p className="mt-1 text-sm text-muted-foreground">
            Los traslados aparecen cuando hay más de una. Se agregan en{" "}
            <Link href="/configuracion/sedes" className="text-primary hover:underline">
              Configuración › Sedes
            </Link>
            .
          </p>
        </div>
      </div>
    )
  }

  return (
    <div className="space-y-6 p-6">
      <div className="flex flex-col gap-4 lg:flex-row lg:items-end lg:justify-between">
        {puedeOperar ? <RecibirEscaneando onHecho={cargar} /> : <div />}
        <div className="flex flex-wrap items-center gap-4">
          <div className="flex items-center gap-2">
            <Switch id="traslados-todas" checked={todasLasSedes} onCheckedChange={setTodasLasSedes} />
            <Label htmlFor="traslados-todas" className="font-normal">
              Todas las sedes{!todasLasSedes && sede ? ` (ahora: ${sede.nombre})` : ""}
            </Label>
          </div>
          <Button variant="outline" onClick={cargar} disabled={cargando}>
            <RefreshCw className={cn("mr-2 h-4 w-4", cargando && "animate-spin")} />
            Actualizar
          </Button>
          <Button variant="outline" asChild>
            <Link href="/circulacion/reservas">
              <BookmarkCheck className="mr-2 h-4 w-4" />
              Reservas
            </Link>
          </Button>
          {puedeOperar && (
            <Button onClick={() => setNuevo(true)}>
              <Plus className="mr-2 h-4 w-4" />
              Nuevo traslado
            </Button>
          )}
        </div>
      </div>

      <Tabs value={vista} onValueChange={irA}>
        <TabsList>
          <TabsTrigger value="por_recibir">
            Por recibir <Contador n={resumen?.por_recibir} />
          </TabsTrigger>
          <TabsTrigger value="por_enviar">
            Por enviar <Contador n={resumen?.por_enviar} alerta />
          </TabsTrigger>
          <TabsTrigger value="enviados">
            Enviados <Contador n={resumen?.enviados} />
          </TabsTrigger>
          <TabsTrigger value="historial">Historial</TabsTrigger>
        </TabsList>

        {VISTAS.map((v) => (
          <TabsContent key={v} value={v} className="mt-4">
            {filas === null ? (
              <div className="rounded-lg border bg-card shadow-papel py-12 text-center text-muted-foreground">
                <Loader2 className="mx-auto mb-2 h-5 w-5 animate-spin" />
                Cargando…
              </div>
            ) : (
              <TablaTraslados
                vista={v}
                filas={filas}
                puedeOperar={puedeOperar}
                trabajando={trabajando}
                onOperar={operar}
              />
            )}
          </TabsContent>
        ))}
      </Tabs>

      <NuevoTrasladoDialog open={nuevo} onOpenChange={setNuevo} onCreado={cargar} />
    </div>
  )
}

function Contador({ n, alerta = false }: { n?: number; alerta?: boolean }) {
  if (!n) return null
  return (
    <span
      className={cn(
        "ml-1.5 rounded-full px-1.5 text-xs tabular-nums",
        alerta ? "bg-aviso text-aviso-foreground" : "bg-muted-foreground/15",
      )}
    >
      {n}
    </span>
  )
}

const VACIO: Record<VistaTraslados, string> = {
  por_recibir: "No viene nada en camino a esta sede.",
  por_enviar: "No hay ejemplares esperando salir de esta sede.",
  enviados: "No hay envíos de esta sede sin recibir.",
  historial: "Todavía no hay traslados cerrados.",
}

function TablaTraslados({
  vista,
  filas,
  puedeOperar,
  trabajando,
  onOperar,
}: {
  vista: VistaTraslados
  filas: Traslado[]
  puedeOperar: boolean
  trabajando: number | null
  onOperar: (t: Traslado, accion: "receive" | "send" | "cancel") => void
}) {
  if (filas.length === 0) {
    return (
      <div className="rounded-lg border border-dashed bg-card py-12 text-center text-sm text-muted-foreground">
        {VACIO[vista]}
      </div>
    )
  }
  return (
    <div className="overflow-x-auto rounded-lg border border-border bg-card shadow-papel">
      <table className="w-full text-sm">
        <thead className="bg-muted/50 text-left text-muted-foreground">
          <tr>
            <th className="px-4 py-3 font-medium">Ejemplar</th>
            <th className="px-4 py-3 font-medium">Recorrido</th>
            <th className="px-4 py-3 font-medium">Motivo</th>
            <th className="px-4 py-3 font-medium">Fechas</th>
            <th className="px-4 py-3" />
          </tr>
        </thead>
        <tbody className="divide-y divide-border">
          {filas.map((t) => (
            <tr key={t.id} className="align-top">
              <td className="px-4 py-3">
                <p className="font-medium text-foreground">{t.title}</p>
                <p className="font-mono text-xs text-muted-foreground">
                  {t.barcode}
                  {t.callNumber && ` · ${t.callNumber}`}
                </p>
              </td>
              <td className="px-4 py-3">
                <span className="inline-flex items-center gap-1.5">
                  {t.from} <ArrowRight className="h-3.5 w-3.5" /> {t.to}
                </span>
              </td>
              <td className="px-4 py-3">
                <Badge variant={t.reason === "reserva" ? "default" : "secondary"}>{MOTIVO[t.reason]}</Badge>
                {t.reason === "reserva" && t.patron && (
                  <p className={cn("mt-1 text-xs", t.holdActive ? "text-muted-foreground" : "text-muted-foreground line-through")}>
                    {t.patron} ({t.patronId})
                  </p>
                )}
                {t.reason === "reserva" && !t.holdActive && vista !== "historial" && (
                  <p className="text-xs text-muted-foreground">La reserva ya no está activa</p>
                )}
                {t.comment && <p className="mt-1 text-xs italic text-muted-foreground">{t.comment}</p>}
              </td>
              <td className="px-4 py-3 text-xs text-muted-foreground">
                {t.status === "Solicitado" && <p>Pedido el {t.requestedOn}</p>}
                {t.sentOn && <p>Enviado el {t.sentOn}</p>}
                {t.daysInTransit ? <p>{t.daysInTransit} día(s) en camino</p> : null}
                {t.receivedOn && <p>Recibido el {t.receivedOn}</p>}
                {t.cancelledOn && <p>Cancelado el {t.cancelledOn}</p>}
                {vista === "historial" && (
                  <Badge variant={t.status === "Recibido" ? "secondary" : "outline"} className="mt-1">
                    {t.status}
                  </Badge>
                )}
              </td>
              <td className="px-4 py-3">
                {puedeOperar && vista !== "historial" && (
                  <div className="flex justify-end gap-2">
                    {vista === "por_recibir" && (
                      <Button size="sm" disabled={trabajando !== null} onClick={() => onOperar(t, "receive")}>
                        {trabajando === t.id ? <Loader2 className="mr-2 h-4 w-4 animate-spin" /> : <PackageCheck className="mr-2 h-4 w-4" />}
                        Recibir
                      </Button>
                    )}
                    {vista === "por_enviar" && (
                      <Button size="sm" disabled={trabajando !== null} onClick={() => onOperar(t, "send")}>
                        {trabajando === t.id ? <Loader2 className="mr-2 h-4 w-4 animate-spin" /> : <Send className="mr-2 h-4 w-4" />}
                        Enviar
                      </Button>
                    )}
                    <Button size="sm" variant="outline" disabled={trabajando !== null}
                            onClick={() => onOperar(t, "cancel")} aria-label={`Cancelar el traslado de ${t.barcode}`}>
                      <X className="h-4 w-4" />
                    </Button>
                  </div>
                )}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}

/** Escanear lo que llega: pasa por la devolución, que recibe el traslado y lo ubica. */
function RecibirEscaneando({ onHecho }: { onHecho: () => void }) {
  const [codigo, setCodigo] = useState("")
  const [enviando, setEnviando] = useState(false)

  async function recibir(e: React.FormEvent) {
    e.preventDefault()
    if (!codigo.trim()) return
    setEnviando(true)
    try {
      const res = await apiPost<ResultadoDevolucion>("/circulation/checkin", { codigo_barras: codigo.trim() })
      avisarDevolucion(res)
      setCodigo("")
      onHecho()
    } catch (error) {
      toast.error("No se pudo registrar", { description: mensajeDeError(error) })
    } finally {
      setEnviando(false)
    }
  }

  return (
    <form onSubmit={recibir} className="w-full space-y-1.5 lg:max-w-sm">
      <Label htmlFor="traslado-escanear">Escanear lo que llega</Label>
      <div className="flex gap-2">
        <div className="relative flex-1">
          <ScanBarcode className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
          <Input id="traslado-escanear" className="pl-9" placeholder="Código de barras" autoComplete="off"
                 value={codigo} onChange={(e) => setCodigo(e.target.value)} />
        </div>
        <Button type="submit" variant="outline" disabled={enviando || !codigo.trim()}>
          {enviando && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}
          Recibir
        </Button>
      </div>
    </form>
  )
}

function NuevoTrasladoDialog({
  open,
  onOpenChange,
  onCreado,
}: {
  open: boolean
  onOpenChange: (open: boolean) => void
  onCreado: () => void
}) {
  const { sedes, sedeId } = useSedes()
  const [codigo, setCodigo] = useState("")
  const [destino, setDestino] = useState("")
  const [comentario, setComentario] = useState("")
  const [enviando, setEnviando] = useState(false)
  const destinos = sedes.filter((s) => s.id !== sedeId)

  async function crear(e: React.FormEvent) {
    e.preventDefault()
    setEnviando(true)
    try {
      const t = await apiPost<Traslado>("/circulation/transfers", {
        codigo_barras: codigo.trim(),
        hacia_id: Number(destino),
        comentario: comentario.trim() || null,
      })
      toast.success(`Envíalo a ${t.to}`, { description: `${t.barcode} · ${t.title}` })
      setCodigo("")
      onCreado()
    } catch (error) {
      toast.error("No se pudo crear el traslado", { description: mensajeDeError(error) })
    } finally {
      setEnviando(false)
    }
  }

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-md">
        <form onSubmit={crear}>
          <DialogHeader>
            <DialogTitle>Nuevo traslado</DialogTitle>
            <DialogDescription>
              Un ejemplar disponible sale de su sede actual hacia otra. Al llegar se queda allí.
            </DialogDescription>
          </DialogHeader>
          <div className="space-y-4 py-4">
            <div className="space-y-2">
              <Label htmlFor="nuevo-traslado-codigo">Código de barras</Label>
              <Input id="nuevo-traslado-codigo" required autoFocus autoComplete="off" value={codigo}
                     onChange={(e) => setCodigo(e.target.value)} />
            </div>
            <div className="space-y-2">
              <Label htmlFor="nuevo-traslado-destino">Hacia</Label>
              <Select value={destino} onValueChange={setDestino}>
                <SelectTrigger id="nuevo-traslado-destino" className="w-full">
                  <SelectValue placeholder="Elige la sede" />
                </SelectTrigger>
                <SelectContent>
                  {destinos.map((s) => (
                    <SelectItem key={s.id} value={String(s.id)}>
                      {s.nombre}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
            <div className="space-y-2">
              <Label htmlFor="nuevo-traslado-comentario">Comentario</Label>
              <Textarea id="nuevo-traslado-comentario" rows={2} maxLength={500} value={comentario}
                        onChange={(e) => setComentario(e.target.value)} placeholder="Opcional" />
            </div>
          </div>
          <DialogFooter>
            <Button type="button" variant="outline" onClick={() => onOpenChange(false)}>
              Cerrar
            </Button>
            <Button type="submit" disabled={enviando || !codigo.trim() || !destino}>
              {enviando && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}
              Enviar
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  )
}
