"use client"

import { Suspense, useCallback, useEffect, useMemo, useState } from "react"
import Link from "next/link"
import { usePathname, useRouter, useSearchParams } from "next/navigation"
import {
  ArrowDown,
  ArrowRight,
  ArrowUp,
  BookmarkCheck,
  Loader2,
  MoreHorizontal,
  Pause,
  Pencil,
  Play,
  RefreshCw,
  Search,
  Truck,
  X,
} from "lucide-react"
import { toast } from "sonner"

import { avisarDevolucion } from "@/components/circulacion/aviso-devolucion"
import { EditarReservaDialog } from "@/components/circulacion/editar-reserva-dialog"
import { AppLayout } from "@/components/layout/app-layout"
import { Header } from "@/components/layout/header"
import { useSedes } from "@/components/layout/sede-provider"
import { useSesion } from "@/components/auth/sesion-provider"
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
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { Switch } from "@/components/ui/switch"
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs"
import { apiDelete, apiGet, apiPatch, apiPost, mensajeDeError } from "@/lib/api"
import type { ReservaGestion, ResultadoDevolucion, TituloPorSacar } from "@/lib/types"
import { cn } from "@/lib/utils"

type Vista = "retirar" | "sacar" | "transito" | "cola"
const VISTAS: Vista[] = ["retirar", "sacar", "transito", "cola"]

export default function ReservasPage() {
  return (
    <AppLayout>
      <Header title="Reservas" description="Cola, estante de reservas y ejemplares por apartar" />
      <Suspense fallback={null}>
        <GestionDeReservas />
      </Suspense>
    </AppLayout>
  )
}

function coincide(q: string, ...campos: (string | null | undefined)[]) {
  return !q || campos.some((c) => c?.toLowerCase().includes(q))
}

function GestionDeReservas() {
  const router = useRouter()
  const pathname = usePathname()
  const params = useSearchParams()
  const { tienePermiso } = useSesion()
  const { sedes, sedeId, sede } = useSedes()
  const puedeOperar = tienePermiso("circulacion")
  const variasSedes = sedes.length > 1

  const vistaUrl = params.get("vista") as Vista | null
  const vista: Vista = vistaUrl && VISTAS.includes(vistaUrl) ? vistaUrl : "retirar"
  const [reservas, setReservas] = useState<ReservaGestion[] | null>(null)
  const [porSacar, setPorSacar] = useState<TituloPorSacar[] | null>(null)
  const [todasLasSedes, setTodasLasSedes] = useState(false)
  const [busqueda, setBusqueda] = useState("")
  const [editando, setEditando] = useState<ReservaGestion | null>(null)
  const [aCancelar, setACancelar] = useState<ReservaGestion | null>(null)
  const [cargando, setCargando] = useState(false)

  const cargar = useCallback(async () => {
    setCargando(true)
    try {
      const [r, p] = await Promise.all([
        apiGet<ReservaGestion[]>("/circulation/holds"),
        apiGet<TituloPorSacar[]>(`/circulation/holds/to-pull?todas_las_sedes=${todasLasSedes}`),
      ])
      setReservas(r)
      setPorSacar(p)
    } catch (error) {
      toast.error("No se pudieron cargar las reservas", { description: mensajeDeError(error) })
    } finally {
      setCargando(false)
    }
  }, [todasLasSedes])

  // Recarga al cambiar de sede: "para sacar" depende de dónde está quien opera.
  useEffect(() => {
    cargar()
  }, [cargar, sedeId])

  function irA(v: string) {
    const p = new URLSearchParams(params.toString())
    p.set("vista", v)
    router.replace(`${pathname}?${p}`, { scroll: false })
  }

  const q = busqueda.trim().toLowerCase()
  const deEstaSede = (r: ReservaGestion) =>
    !variasSedes || todasLasSedes || r.pickupBranchId === sedeId || r.pickupBranchId === null
  const filtrar = (r: ReservaGestion) =>
    coincide(q, r.title, r.author, r.userName, r.userId, r.itemBarcode)

  const listas = useMemo(() => {
    const todas = reservas ?? []
    return {
      retirar: todas.filter((r) => r.status === "EnEspera" && deEstaSede(r) && filtrar(r)),
      // En tránsito importa a quien lo envía y a quien lo recibe.
      transito: todas.filter(
        (r) => r.status === "EnTransito" && (deEstaSede(r) || r.transitFromId === sedeId) && filtrar(r),
      ),
      cola: todas.filter((r) => r.status === "Pendiente" && filtrar(r)),
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [reservas, q, todasLasSedes, sedeId, variasSedes])

  const sacar = useMemo(
    () => (porSacar ?? []).filter((t) => coincide(q, t.title, t.author, t.firstPatron,
                                                    ...t.items.map((i) => i.barcode))),
    [porSacar, q],
  )

  async function cancelar() {
    if (!aCancelar) return
    try {
      await apiDelete(`/circulation/holds/${aCancelar.id}`)
      toast.success("Reserva cancelada", { description: `${aCancelar.userName} · ${aCancelar.title}` })
      await cargar()
    } catch (error) {
      toast.error("No se pudo cancelar", { description: mensajeDeError(error) })
    } finally {
      setACancelar(null)
    }
  }

  async function cambiar(r: ReservaGestion, cambios: Record<string, unknown>,
                         aviso: string | ((nueva: ReservaGestion) => string)) {
    try {
      const nueva = await apiPatch<ReservaGestion>(`/circulation/holds/${r.id}`, cambios)
      toast.success(typeof aviso === "function" ? aviso(nueva) : aviso,
                    { description: `${r.userName} · ${r.title}` })
      await cargar()
    } catch (error) {
      toast.error("No se pudo actualizar la reserva", { description: mensajeDeError(error) })
    }
  }

  async function apartar(codigo: string) {
    try {
      const res = await apiPost<ResultadoDevolucion>("/circulation/checkin", { codigo_barras: codigo })
      avisarDevolucion(res)
      await cargar()
    } catch (error) {
      toast.error("No se pudo apartar", { description: mensajeDeError(error) })
    }
  }

  const acciones: AccionesReserva = {
    puedeOperar,
    editar: setEditando,
    cancelar: setACancelar,
    // El turno que quedó de verdad (al mandar al final se envía 9999 y el backend lo acota).
    mover: (r, prioridad) => cambiar(r, { prioridad }, (nueva) => `Turno ${nueva.priority ?? prioridad}`),
    suspender: (r, s) => cambiar(r, { suspendida: s }, s ? "Reserva suspendida" : "Reserva reanudada"),
  }

  return (
    <div className="space-y-6 p-6">
      <div className="flex flex-col gap-4 lg:flex-row lg:items-center lg:justify-between">
        <div className="relative w-full lg:max-w-sm">
          <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
          <Input
            type="search"
            placeholder="Título, lector, carnet o código…"
            className="pl-9"
            value={busqueda}
            onChange={(e) => setBusqueda(e.target.value)}
            aria-label="Filtrar reservas"
          />
        </div>
        <div className="flex flex-wrap items-center gap-4">
          {variasSedes && (
            <div className="flex items-center gap-2">
              <Switch id="todas-las-sedes" checked={todasLasSedes} onCheckedChange={setTodasLasSedes} />
              <Label htmlFor="todas-las-sedes" className="font-normal">
                Todas las sedes{!todasLasSedes && sede ? ` (ahora: ${sede.nombre})` : ""}
              </Label>
            </div>
          )}
          <Button variant="outline" onClick={cargar} disabled={cargando}>
            <RefreshCw className={cn("mr-2 h-4 w-4", cargando && "animate-spin")} />
            Actualizar
          </Button>
          <Button variant="outline" asChild>
            <Link href="/circulacion/traslados">
              <Truck className="mr-2 h-4 w-4" />
              Traslados
            </Link>
          </Button>
        </div>
      </div>

      {reservas === null ? (
        <div className="rounded-lg border bg-card shadow-papel py-16 text-center text-muted-foreground">
          <Loader2 className="mx-auto mb-2 h-5 w-5 animate-spin" />
          Cargando reservas…
        </div>
      ) : (
        <Tabs value={vista} onValueChange={irA}>
          <TabsList>
            <TabsTrigger value="retirar">
              Por retirar <Contador n={listas.retirar.length} alerta={listas.retirar.some((r) => r.expiresToday)} />
            </TabsTrigger>
            <TabsTrigger value="sacar">
              Para sacar del estante <Contador n={sacar.length} />
            </TabsTrigger>
            <TabsTrigger value="transito">
              En tránsito <Contador n={listas.transito.length} />
            </TabsTrigger>
            <TabsTrigger value="cola">
              Cola <Contador n={listas.cola.length} />
            </TabsTrigger>
          </TabsList>

          <TabsContent value="retirar" className="mt-4">
            <PorRetirar filas={listas.retirar} acciones={acciones} />
          </TabsContent>
          <TabsContent value="sacar" className="mt-4">
            <ParaSacar titulos={sacar} puedeOperar={puedeOperar} onApartar={apartar} />
          </TabsContent>
          <TabsContent value="transito" className="mt-4">
            <EnTransito filas={listas.transito} acciones={acciones} />
          </TabsContent>
          <TabsContent value="cola" className="mt-4">
            <Cola filas={listas.cola} acciones={acciones} variasSedes={variasSedes} />
          </TabsContent>
        </Tabs>
      )}

      <EditarReservaDialog
        reserva={editando}
        onOpenChange={(v) => !v && setEditando(null)}
        onSaved={() => {
          setEditando(null)
          cargar()
        }}
      />

      <AlertDialog open={aCancelar !== null} onOpenChange={(v) => !v && setACancelar(null)}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>¿Cancelar la reserva?</AlertDialogTitle>
            <AlertDialogDescription>
              {aCancelar?.userName} ({aCancelar?.userId}) · <strong>{aCancelar?.title}</strong>.
              {aCancelar?.status === "EnEspera" &&
                " El ejemplar apartado pasa al siguiente de la cola o vuelve al estante."}
              {aCancelar?.status === "EnTransito" &&
                " Si el ejemplar ya salió, sigue viaje; al llegar se ubica como cualquier otro."}
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel>Volver</AlertDialogCancel>
            <AlertDialogAction
              onClick={cancelar}
              className="bg-destructive text-destructive-foreground hover:bg-destructive/90"
            >
              Cancelar reserva
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </div>
  )
}

type AccionesReserva = {
  puedeOperar: boolean
  editar: (r: ReservaGestion) => void
  cancelar: (r: ReservaGestion) => void
  mover: (r: ReservaGestion, prioridad: number) => void
  suspender: (r: ReservaGestion, suspendida: boolean) => void
}

function Contador({ n, alerta = false }: { n: number; alerta?: boolean }) {
  if (n === 0) return null
  return (
    <span
      className={cn(
        "ml-1.5 rounded-full px-1.5 text-xs tabular-nums",
        alerta ? "bg-destructive text-destructive-foreground" : "bg-muted-foreground/15",
      )}
    >
      {n}
    </span>
  )
}

function Vacio({ children }: { children: React.ReactNode }) {
  return (
    <div className="rounded-lg border border-dashed bg-card py-12 text-center text-sm text-muted-foreground">
      {children}
    </div>
  )
}

function Lector({ r }: { r: ReservaGestion }) {
  return (
    <>
      <Link href={`/usuarios/${encodeURIComponent(r.userId)}`} className="font-medium text-foreground hover:underline">
        {r.userName}
      </Link>
      <p className="font-mono text-xs text-muted-foreground">{r.userId}</p>
    </>
  )
}

function Titulo({ r }: { r: { biblioId: string; title: string; author: string | null } }) {
  return (
    <>
      <Link href={`/catalogo/${r.biblioId}`} className="font-medium text-foreground hover:underline">
        {r.title}
      </Link>
      {r.author && <p className="text-xs text-muted-foreground">{r.author}</p>}
    </>
  )
}

function Tabla({ cabeceras, children }: { cabeceras: string[]; children: React.ReactNode }) {
  return (
    <div className="overflow-x-auto rounded-lg border border-border bg-card shadow-papel">
      <table className="w-full text-sm">
        <thead className="bg-muted/50 text-left text-muted-foreground">
          <tr>
            {cabeceras.map((c, i) => (
              <th key={i} className="px-4 py-3 font-medium">
                {c}
              </th>
            ))}
          </tr>
        </thead>
        <tbody className="divide-y divide-border">{children}</tbody>
      </table>
    </div>
  )
}

function PorRetirar({ filas, acciones }: { filas: ReservaGestion[]; acciones: AccionesReserva }) {
  if (filas.length === 0) return <Vacio>No hay ejemplares esperando en el estante de reservas.</Vacio>
  return (
    <Tabla cabeceras={["Lector", "Título", "Ejemplar", "En el estante", "Retirar hasta", ""]}>
      {filas.map((r) => (
        <tr key={r.id} className="align-top">
          <td className="px-4 py-3"><Lector r={r} /></td>
          <td className="px-4 py-3"><Titulo r={r} /></td>
          <td className="px-4 py-3">
            <p className="font-mono text-xs">{r.itemBarcode}</p>
            {r.callNumber && <p className="text-xs text-muted-foreground">{r.callNumber}</p>}
          </td>
          <td className="px-4 py-3 text-muted-foreground">
            {r.waitingSince}
            {r.daysWaiting ? <span className="block text-xs">hace {r.daysWaiting} día(s)</span> : null}
          </td>
          <td className="px-4 py-3">
            <span className={cn(r.expiresToday && "font-medium text-destructive")}>{r.pickupBy}</span>
            {r.expiresToday && <Badge variant="destructive" className="ml-2">Vence hoy</Badge>}
            {r.pickupBranch && <p className="text-xs text-muted-foreground">{r.pickupBranch}</p>}
          </td>
          <td className="px-4 py-3 text-right">
            <MenuReserva r={r} acciones={acciones} />
          </td>
        </tr>
      ))}
    </Tabla>
  )
}

function ParaSacar({
  titulos,
  puedeOperar,
  onApartar,
}: {
  titulos: TituloPorSacar[]
  puedeOperar: boolean
  onApartar: (codigo: string) => Promise<void>
}) {
  const [apartando, setApartando] = useState<string | null>(null)
  if (titulos.length === 0) {
    return <Vacio>Ninguna reserva espera un ejemplar que esté libre en el estante.</Vacio>
  }
  return (
    <div className="space-y-3">
      <p className="text-sm text-muted-foreground">
        Busca estos ejemplares en el estante y apártalos. Escanearlos en la devolución hace lo mismo.
      </p>
      {titulos.map((t) => (
        <div key={t.biblioId} className="rounded-lg border border-border bg-card shadow-papel p-4">
          <div className="flex flex-col gap-1 sm:flex-row sm:items-start sm:justify-between">
            <div>
              <Titulo r={t} />
            </div>
            <p className="text-sm text-muted-foreground">
              {t.holds} reserva(s) · primero: <span className="text-foreground">{t.firstPatron}</span>
              {t.pickupBranch && <> · retira en {t.pickupBranch}</>}
            </p>
          </div>
          <ul className="mt-3 divide-y divide-border rounded-md border border-border">
            {t.items.map((i) => (
              <li key={i.barcode} className="flex items-center justify-between gap-3 px-3 py-2 text-sm">
                <div className="flex flex-wrap items-baseline gap-x-3">
                  <span className="font-mono">{i.barcode}</span>
                  <span className="text-muted-foreground">{i.callNumber ?? "sin signatura"}</span>
                  {i.branch && <span className="text-xs text-muted-foreground">{i.branch}</span>}
                </div>
                {puedeOperar && (
                  <Button
                    size="sm"
                    variant="outline"
                    disabled={apartando !== null}
                    onClick={async () => {
                      setApartando(i.barcode)
                      await onApartar(i.barcode)
                      setApartando(null)
                    }}
                    aria-label={`Apartar ${i.barcode}`}
                  >
                    {apartando === i.barcode ? (
                      <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                    ) : (
                      <BookmarkCheck className="mr-2 h-4 w-4" />
                    )}
                    Apartar
                  </Button>
                )}
              </li>
            ))}
          </ul>
          {t.toPull < t.items.length && (
            <p className="mt-2 text-xs text-muted-foreground">
              Basta con {t.toPull} de {t.items.length}: hay {t.holds} reserva(s) esperando.
            </p>
          )}
        </div>
      ))}
    </div>
  )
}

function EnTransito({ filas, acciones }: { filas: ReservaGestion[]; acciones: AccionesReserva }) {
  if (filas.length === 0) return <Vacio>No hay reservas con ejemplares en camino.</Vacio>
  return (
    <Tabla cabeceras={["Lector", "Título", "Ejemplar", "Recorrido", ""]}>
      {filas.map((r) => (
        <tr key={r.id} className="align-top">
          <td className="px-4 py-3"><Lector r={r} /></td>
          <td className="px-4 py-3"><Titulo r={r} /></td>
          <td className="px-4 py-3 font-mono text-xs">{r.itemBarcode}</td>
          <td className="px-4 py-3">
            <span className="inline-flex items-center gap-1.5">
              {r.transitFrom ?? "—"} <ArrowRight className="h-3.5 w-3.5" /> {r.pickupBranch ?? "—"}
            </span>
            <p className="text-xs text-muted-foreground">
              {r.transitSent ? "En camino" : "Por enviar desde la sede de origen"}
            </p>
          </td>
          <td className="px-4 py-3 text-right">
            <MenuReserva r={r} acciones={acciones} />
          </td>
        </tr>
      ))}
    </Tabla>
  )
}

function Cola({
  filas,
  acciones,
  variasSedes,
}: {
  filas: ReservaGestion[]
  acciones: AccionesReserva
  variasSedes: boolean
}) {
  const porTitulo = useMemo(() => {
    const grupos = new Map<string, ReservaGestion[]>()
    for (const r of filas) grupos.set(r.biblioId, [...(grupos.get(r.biblioId) ?? []), r])
    return [...grupos.values()]
  }, [filas])

  if (filas.length === 0) return <Vacio>No hay reservas pendientes.</Vacio>
  return (
    <div className="space-y-4">
      {porTitulo.map((grupo) => (
        <div key={grupo[0].biblioId} className="overflow-hidden rounded-lg border border-border bg-card shadow-papel">
          <div className="flex items-baseline justify-between gap-3 border-b border-border bg-muted/40 px-4 py-2.5">
            <div>
              <Titulo r={grupo[0]} />
            </div>
            <span className="shrink-0 text-xs text-muted-foreground">{grupo.length} en cola</span>
          </div>
          <ul className="divide-y divide-border">
            {grupo.map((r, i) => (
              <li key={r.id} className={cn("flex items-start gap-4 px-4 py-3 text-sm", r.suspended && "bg-muted/30")}>
                <span className="mt-0.5 w-6 shrink-0 text-center font-semibold tabular-nums text-muted-foreground">
                  {r.priority}
                </span>
                <div className="min-w-0 flex-1">
                  <Lector r={r} />
                  <div className="mt-1 flex flex-wrap gap-x-3 gap-y-1 text-xs text-muted-foreground">
                    <span>Desde el {r.reservedOn}</span>
                    {variasSedes && r.pickupBranch && <span>Retira en {r.pickupBranch}</span>}
                    {r.notNeededAfter && <span>No la necesita después del {formatoIso(r.notNeededAfter)}</span>}
                  </div>
                  {r.notes && <p className="mt-1 text-xs italic text-muted-foreground">“{r.notes}”</p>}
                </div>
                {r.suspended && (
                  <Badge variant="outline" className="shrink-0">
                    <Pause className="mr-1 h-3 w-3" />
                    {r.suspendedUntil ? `Hasta el ${formatoIso(r.suspendedUntil)}` : "Suspendida"}
                  </Badge>
                )}
                {acciones.puedeOperar && (
                  <div className="flex shrink-0 items-center gap-1">
                    <Button variant="ghost" size="icon" className="h-8 w-8" disabled={i === 0}
                            onClick={() => acciones.mover(r, r.priority - 1)}
                            aria-label={`Subir el turno de ${r.userName}`}>
                      <ArrowUp className="h-4 w-4" />
                    </Button>
                    <Button variant="ghost" size="icon" className="h-8 w-8" disabled={i === grupo.length - 1}
                            onClick={() => acciones.mover(r, r.priority + 1)}
                            aria-label={`Bajar el turno de ${r.userName}`}>
                      <ArrowDown className="h-4 w-4" />
                    </Button>
                    <MenuReserva r={r} acciones={acciones} primero={i === 0} ultimo={i === grupo.length - 1} />
                  </div>
                )}
              </li>
            ))}
          </ul>
        </div>
      ))}
    </div>
  )
}

function formatoIso(iso: string) {
  const [a, m, d] = iso.split("-")
  return `${d}/${m}/${a}`
}

function MenuReserva({
  r,
  acciones,
  primero = true,
  ultimo = true,
}: {
  r: ReservaGestion
  acciones: AccionesReserva
  primero?: boolean
  ultimo?: boolean
}) {
  if (!acciones.puedeOperar) return null
  const pendiente = r.status === "Pendiente"
  return (
    <DropdownMenu>
      <DropdownMenuTrigger asChild>
        <Button variant="ghost" size="icon" className="h-8 w-8" aria-label={`Acciones de la reserva de ${r.userName}`}>
          <MoreHorizontal className="h-4 w-4" />
        </Button>
      </DropdownMenuTrigger>
      <DropdownMenuContent align="end">
        {pendiente && (
          <>
            <DropdownMenuItem disabled={primero} onClick={() => acciones.mover(r, 1)}>
              <ArrowUp className="mr-2 h-4 w-4" /> Primer turno
            </DropdownMenuItem>
            <DropdownMenuItem disabled={ultimo} onClick={() => acciones.mover(r, 9999)}>
              <ArrowDown className="mr-2 h-4 w-4" /> Último turno
            </DropdownMenuItem>
            <DropdownMenuItem onClick={() => acciones.suspender(r, !r.suspended)}>
              {r.suspended ? <Play className="mr-2 h-4 w-4" /> : <Pause className="mr-2 h-4 w-4" />}
              {r.suspended ? "Reanudar" : "Suspender"}
            </DropdownMenuItem>
          </>
        )}
        <DropdownMenuItem onClick={() => acciones.editar(r)}>
          <Pencil className="mr-2 h-4 w-4" /> Editar…
        </DropdownMenuItem>
        <DropdownMenuSeparator />
        <DropdownMenuItem className="text-destructive focus:text-destructive" onClick={() => acciones.cancelar(r)}>
          <X className="mr-2 h-4 w-4" /> Cancelar reserva
        </DropdownMenuItem>
      </DropdownMenuContent>
    </DropdownMenu>
  )
}
