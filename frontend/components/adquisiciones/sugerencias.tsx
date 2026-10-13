"use client"

import { useCallback, useEffect, useState } from "react"
import Link from "next/link"
import { Check, Loader2, MoreHorizontal, Plus, ShoppingCart, X } from "lucide-react"
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
import { Textarea } from "@/components/ui/textarea"
import { apiGet, apiPost, mensajeDeError } from "@/lib/api"
import type { EstadoSugerencia, Fondo, Pedido, Sugerencia } from "@/lib/types"
import { FondoSelect, Vacio } from "./comun"

const FILTROS: { valor: string; texto: string }[] = [
  { valor: "Pendiente", texto: "Por revisar" },
  { valor: "Aceptada", texto: "Aceptadas" },
  { valor: "Pedida", texto: "Pedidas" },
  { valor: "Rechazada", texto: "Rechazadas" },
  { valor: "", texto: "Todas" },
]

const VARIANTE: Record<EstadoSugerencia, "default" | "secondary" | "outline"> = {
  Pendiente: "outline",
  Aceptada: "secondary",
  Pedida: "default",
  Rechazada: "outline",
}

export function SugerenciasPanel() {
  const [filtro, setFiltro] = useState("Pendiente")
  const [sugerencias, setSugerencias] = useState<Sugerencia[] | null>(null)
  const [nueva, setNueva] = useState(false)
  const [rechazando, setRechazando] = useState<Sugerencia | null>(null)
  const [pidiendo, setPidiendo] = useState<Sugerencia | null>(null)

  const cargar = useCallback(async () => {
    try {
      setSugerencias(await apiGet<Sugerencia[]>(`/acquisitions/suggestions${filtro ? `?estado=${filtro}` : ""}`))
    } catch (e) {
      toast.error("No se pudieron cargar las sugerencias", { description: mensajeDeError(e) })
    }
  }, [filtro])

  useEffect(() => {
    cargar()
  }, [cargar])

  async function aceptar(s: Sugerencia) {
    try {
      await apiPost(`/acquisitions/suggestions/${s.id}/accept`, {})
      toast.success("Sugerencia aceptada", { description: s.titulo })
      cargar()
    } catch (error) {
      toast.error("No se pudo aceptar", { description: mensajeDeError(error) })
    }
  }

  return (
    <div className="space-y-4">
      <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
        <div className="flex flex-wrap gap-1.5" role="group" aria-label="Filtrar sugerencias">
          {FILTROS.map((f) => (
            <Button key={f.texto} size="sm" variant={filtro === f.valor ? "default" : "outline"}
                    aria-pressed={filtro === f.valor} onClick={() => setFiltro(f.valor)}>
              {f.texto}
            </Button>
          ))}
        </div>
        <Button onClick={() => setNueva(true)}>
          <Plus className="mr-2 h-4 w-4" />
          Nueva sugerencia
        </Button>
      </div>

      {sugerencias === null ? (
        <div className="py-12 text-center text-muted-foreground"><Loader2 className="mx-auto h-5 w-5 animate-spin" /></div>
      ) : sugerencias.length === 0 ? (
        <Vacio>No hay sugerencias con este filtro.</Vacio>
      ) : (
        <div className="divide-y divide-border rounded-lg border bg-card">
          {sugerencias.map((s) => (
            <div key={s.id} className="flex flex-col gap-2 px-4 py-3 sm:flex-row sm:items-start sm:justify-between">
              <div className="min-w-0">
                <p className="font-medium text-foreground">
                  {s.titulo} <Badge variant={VARIANTE[s.estado]} className="ml-1">{s.estado}</Badge>
                </p>
                <p className="text-xs text-muted-foreground">
                  {[s.autor, s.editorial, s.ano, s.isbn && `ISBN ${s.isbn}`].filter(Boolean).join(" · ") || "Sin datos de edición"}
                </p>
                <p className="text-xs text-muted-foreground">
                  Sugerida el {s.fecha}{s.lector ? ` por ${s.lector} (${s.carnet})` : ""}
                  {s.gestionada_por && ` · revisó ${s.gestionada_por}`}
                </p>
                {s.nota && <p className="mt-1 text-sm italic text-muted-foreground">“{s.nota}”</p>}
                {s.motivo && <p className="mt-1 text-sm text-foreground">Motivo: {s.motivo}</p>}
                {s.en_catalogo_id && (
                  <p className="mt-1 text-xs">
                    <Link href={`/catalogo/${s.en_catalogo_id}`} className="text-primary hover:underline">
                      Ya hay un registro con ese ISBN en el catálogo
                    </Link>
                  </p>
                )}
                {s.orden_id && (
                  <p className="mt-1 text-xs">
                    <Link href={`/adquisiciones/pedidos/${s.orden_id}`} className="text-primary hover:underline">
                      Ver el pedido
                    </Link>
                  </p>
                )}
              </div>
              {(s.estado === "Pendiente" || s.estado === "Aceptada") && (
                <div className="flex shrink-0 gap-2">
                  <Button size="sm" variant="outline" onClick={() => setPidiendo(s)}>
                    <ShoppingCart className="mr-2 h-4 w-4" />
                    Pedir
                  </Button>
                  <DropdownMenu>
                    <DropdownMenuTrigger asChild>
                      <Button size="sm" variant="ghost" aria-label={`Más acciones para ${s.titulo}`}>
                        <MoreHorizontal className="h-4 w-4" />
                      </Button>
                    </DropdownMenuTrigger>
                    <DropdownMenuContent align="end">
                      {s.estado === "Pendiente" && (
                        <DropdownMenuItem onClick={() => aceptar(s)}>
                          <Check className="mr-2 h-4 w-4" /> Aceptar
                        </DropdownMenuItem>
                      )}
                      <DropdownMenuItem onClick={() => setRechazando(s)}>
                        <X className="mr-2 h-4 w-4" /> Rechazar…
                      </DropdownMenuItem>
                    </DropdownMenuContent>
                  </DropdownMenu>
                </div>
              )}
            </div>
          ))}
        </div>
      )}

      <NuevaSugerenciaDialog open={nueva} onOpenChange={setNueva} onCreada={cargar} />
      <RechazarDialog sugerencia={rechazando} onOpenChange={(v) => !v && setRechazando(null)}
                      onHecho={() => { setRechazando(null); cargar() }} />
      <PedirDialog sugerencia={pidiendo} onOpenChange={(v) => !v && setPidiendo(null)}
                   onHecho={() => { setPidiendo(null); cargar() }} />
    </div>
  )
}

function NuevaSugerenciaDialog({ open, onOpenChange, onCreada }: {
  open: boolean
  onOpenChange: (v: boolean) => void
  onCreada: () => void
}) {
  const vacio = { titulo: "", autor: "", isbn: "", editorial: "", ano: "", nota: "", nro_carnet: "" }
  const [f, setF] = useState(vacio)
  const [enviando, setEnviando] = useState(false)
  const campo = (k: keyof typeof f) => (e: React.ChangeEvent<HTMLInputElement | HTMLTextAreaElement>) =>
    setF((x) => ({ ...x, [k]: e.target.value }))

  async function crear(e: React.FormEvent) {
    e.preventDefault()
    setEnviando(true)
    try {
      await apiPost("/acquisitions/suggestions", { ...f, ano: f.ano ? Number(f.ano) : null })
      toast.success("Sugerencia registrada", { description: f.titulo })
      setF(vacio)
      onOpenChange(false)
      onCreada()
    } catch (error) {
      toast.error("No se pudo registrar", { description: mensajeDeError(error) })
    } finally {
      setEnviando(false)
    }
  }

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-lg">
        <form onSubmit={crear}>
          <DialogHeader>
            <DialogTitle>Nueva sugerencia de compra</DialogTitle>
            <DialogDescription>A nombre de un lector (su carnet) o a tu nombre si lo dejas vacío.</DialogDescription>
          </DialogHeader>
          <div className="grid gap-4 py-4 sm:grid-cols-2">
            <div className="space-y-2 sm:col-span-2">
              <Label htmlFor="sug-titulo">Título</Label>
              <Input id="sug-titulo" required value={f.titulo} onChange={campo("titulo")} />
            </div>
            <div className="space-y-2">
              <Label htmlFor="sug-autor">Autor</Label>
              <Input id="sug-autor" value={f.autor} onChange={campo("autor")} />
            </div>
            <div className="space-y-2">
              <Label htmlFor="sug-isbn">ISBN</Label>
              <Input id="sug-isbn" value={f.isbn} onChange={campo("isbn")} />
            </div>
            <div className="space-y-2">
              <Label htmlFor="sug-editorial">Editorial</Label>
              <Input id="sug-editorial" value={f.editorial} onChange={campo("editorial")} />
            </div>
            <div className="space-y-2">
              <Label htmlFor="sug-ano">Año</Label>
              <Input id="sug-ano" type="number" value={f.ano} onChange={campo("ano")} />
            </div>
            <div className="space-y-2 sm:col-span-2">
              <Label htmlFor="sug-carnet">Carnet del lector</Label>
              <Input id="sug-carnet" value={f.nro_carnet} placeholder="Opcional" onChange={campo("nro_carnet")} />
            </div>
            <div className="space-y-2 sm:col-span-2">
              <Label htmlFor="sug-nota">Para qué lo necesita</Label>
              <Textarea id="sug-nota" rows={2} value={f.nota} onChange={campo("nota")} />
            </div>
          </div>
          <DialogFooter>
            <Button type="button" variant="outline" onClick={() => onOpenChange(false)}>Cancelar</Button>
            <Button type="submit" disabled={enviando || !f.titulo.trim()}>
              {enviando && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}
              Registrar
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  )
}

function RechazarDialog({ sugerencia, onOpenChange, onHecho }: {
  sugerencia: Sugerencia | null
  onOpenChange: (v: boolean) => void
  onHecho: () => void
}) {
  const [motivo, setMotivo] = useState("")
  const [enviando, setEnviando] = useState(false)

  async function rechazar(e: React.FormEvent) {
    e.preventDefault()
    if (!sugerencia) return
    setEnviando(true)
    try {
      await apiPost(`/acquisitions/suggestions/${sugerencia.id}/reject`, { motivo })
      toast.success("Sugerencia rechazada", { description: sugerencia.titulo })
      setMotivo("")
      onHecho()
    } catch (error) {
      toast.error("No se pudo rechazar", { description: mensajeDeError(error) })
    } finally {
      setEnviando(false)
    }
  }

  return (
    <Dialog open={sugerencia !== null} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-md">
        <form onSubmit={rechazar}>
          <DialogHeader>
            <DialogTitle>Rechazar sugerencia</DialogTitle>
            <DialogDescription>{sugerencia?.titulo}. El lector verá el motivo.</DialogDescription>
          </DialogHeader>
          <div className="space-y-2 py-4">
            <Label htmlFor="sug-motivo">Motivo</Label>
            <Textarea id="sug-motivo" required rows={3} value={motivo} onChange={(e) => setMotivo(e.target.value)}
                      placeholder="Fuera de la política de colección, agotado, ya hay ejemplares…" />
          </div>
          <DialogFooter>
            <Button type="button" variant="outline" onClick={() => onOpenChange(false)}>Cancelar</Button>
            <Button type="submit" variant="destructive" disabled={enviando || !motivo.trim()}>
              {enviando && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}
              Rechazar
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  )
}

function PedirDialog({ sugerencia, onOpenChange, onHecho }: {
  sugerencia: Sugerencia | null
  onOpenChange: (v: boolean) => void
  onHecho: () => void
}) {
  const [pedidos, setPedidos] = useState<Pedido[]>([])
  const [fondos, setFondos] = useState<Fondo[]>([])
  const [pedido, setPedido] = useState("")
  const [cantidad, setCantidad] = useState("1")
  const [precio, setPrecio] = useState("")
  const [fondo, setFondo] = useState<number | null>(null)
  const [enviando, setEnviando] = useState(false)

  useEffect(() => {
    if (!sugerencia) return
    Promise.all([
      apiGet<Pedido[]>("/acquisitions/orders?estado=Abierta"),
      apiGet<Fondo[]>("/acquisitions/funds"),
    ])
      .then(([p, f]) => {
        setPedidos(p)
        setFondos(f)
        setPedido(p.length ? String(p[0].id) : "")
      })
      .catch(() => setPedidos([]))
  }, [sugerencia])

  async function pedir(e: React.FormEvent) {
    e.preventDefault()
    if (!sugerencia) return
    setEnviando(true)
    try {
      await apiPost(`/acquisitions/suggestions/${sugerencia.id}/order`, {
        orden_id: Number(pedido), cantidad: Number(cantidad), precio_unitario: Number(precio), fondo_id: fondo,
      })
      toast.success("Agregada al pedido", { description: sugerencia.titulo })
      onHecho()
    } catch (error) {
      toast.error("No se pudo pedir", { description: mensajeDeError(error) })
    } finally {
      setEnviando(false)
    }
  }

  return (
    <Dialog open={sugerencia !== null} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-md">
        <form onSubmit={pedir}>
          <DialogHeader>
            <DialogTitle>Pedir sugerencia</DialogTitle>
            <DialogDescription>{sugerencia?.titulo} se agrega como título nuevo a un pedido abierto.</DialogDescription>
          </DialogHeader>
          <div className="grid gap-4 py-4 sm:grid-cols-2">
            <div className="space-y-2 sm:col-span-2">
              <Label htmlFor="pedir-pedido">Pedido</Label>
              <Select value={pedido} onValueChange={setPedido}>
                <SelectTrigger id="pedir-pedido" className="w-full">
                  <SelectValue placeholder="No hay pedidos abiertos" />
                </SelectTrigger>
                <SelectContent>
                  {pedidos.map((p) => (
                    <SelectItem key={p.id} value={String(p.id)}>{p.nombre} · {p.proveedor_nombre}</SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
            <div className="space-y-2">
              <Label htmlFor="pedir-cantidad">Cantidad</Label>
              <Input id="pedir-cantidad" type="number" min={1} required value={cantidad} onChange={(e) => setCantidad(e.target.value)} />
            </div>
            <div className="space-y-2">
              <Label htmlFor="pedir-precio">Precio de lista (Bs.)</Label>
              <Input id="pedir-precio" type="number" min={0} step="0.01" required value={precio} onChange={(e) => setPrecio(e.target.value)} />
            </div>
            <div className="space-y-2 sm:col-span-2">
              <Label htmlFor="pedir-fondo">Fondo</Label>
              <FondoSelect id="pedir-fondo" fondos={fondos} valor={fondo} onChange={setFondo} />
            </div>
          </div>
          <DialogFooter>
            <Button type="button" variant="outline" onClick={() => onOpenChange(false)}>Cancelar</Button>
            <Button type="submit" disabled={enviando || !pedido || precio === ""}>
              {enviando && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}
              Agregar al pedido
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  )
}
