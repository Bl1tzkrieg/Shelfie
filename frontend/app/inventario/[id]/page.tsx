"use client"

import { useCallback, useEffect, useRef, useState } from "react"
import Link from "next/link"
import { useParams } from "next/navigation"
import { ArrowLeft, CheckCircle2, Download, FileUp, Loader2, Lock, ScanBarcode, XCircle } from "lucide-react"
import { toast } from "sonner"

import { useSesion } from "@/components/auth/sesion-provider"
import { alcance, TONO_RESULTADO } from "@/components/inventario/alcance"
import { AppLayout } from "@/components/layout/app-layout"
import { Header } from "@/components/layout/header"
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
import { Label } from "@/components/ui/label"
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs"
import { Textarea } from "@/components/ui/textarea"
import { apiDownload, apiGet, apiPost, mensajeDeError } from "@/lib/api"
import type { InventarioDetalle, LecturaInventario, ResultadoLectura } from "@/lib/types"
import { cn } from "@/lib/utils"

const CLASES_TONO = {
  bien: "border-primary/30 bg-primary/5 text-primary",
  revisar: "border-accent/40 bg-accent/10 text-accent-foreground",
  problema: "border-destructive/30 bg-destructive/5 text-destructive",
}

const PROBLEMAS: ResultadoLectura[] = ["fuera_de_lugar", "prestado", "perdido", "retirado", "reservado",
                                       "en_transito", "desconocido"]

/** Separa los códigos de un texto pegado o de un archivo (uno por línea, o con comas/punto y coma). */
function codigosDe(texto: string) {
  return texto.split(/[\s,;]+/).map((c) => c.trim()).filter(Boolean)
}

export default function InventarioPage() {
  const { id } = useParams<{ id: string }>()
  const { tienePermiso } = useSesion()
  const [inv, setInv] = useState<InventarioDetalle | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [recientes, setRecientes] = useState<LecturaInventario[]>([])
  const [cerrando, setCerrando] = useState(false)

  const cargar = useCallback(async () => {
    try {
      setInv(await apiGet<InventarioDetalle>(`/inventories/${id}`))
    } catch (e) {
      setError(mensajeDeError(e))
    }
  }, [id])

  useEffect(() => {
    cargar()
  }, [cargar])

  const leer = useCallback(async (codigos: string[]) => {
    const r = await apiPost<{ lecturas: LecturaInventario[] }>(`/inventories/${id}/scan`, { codigos })
    setRecientes((anteriores) => [...[...r.lecturas].reverse(), ...anteriores].slice(0, 50))
    await cargar()
    return r.lecturas
  }, [id, cargar])

  async function cerrar() {
    try {
      setInv(await apiPost<InventarioDetalle>(`/inventories/${id}/close`))
      toast.success("Inventario cerrado")
    } catch (e) {
      toast.error("No se pudo cerrar", { description: mensajeDeError(e) })
    } finally {
      setCerrando(false)
    }
  }

  if (error) {
    return <AppLayout><Header title="Inventario" /><p role="alert" className="p-6 text-destructive">{error}</p></AppLayout>
  }
  if (!inv) {
    return <AppLayout><Header title="Inventario" /><Loader2 className="mx-auto mt-12 h-6 w-6 animate-spin text-muted-foreground" /></AppLayout>
  }

  const abierto = inv.estado === "Abierto"
  const puedeLeer = abierto && tienePermiso("catalogo")
  const problemas = PROBLEMAS.reduce((n, r) => n + (inv.conteos[r] ?? 0), 0)

  return (
    <AppLayout>
      <Header title={inv.nombre} description={alcance(inv)} />
      <div className="space-y-6 p-4 sm:p-6">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <Link href="/inventario" className="inline-flex items-center gap-1 text-sm text-muted-foreground hover:text-foreground">
            <ArrowLeft className="h-4 w-4" />Inventarios
          </Link>
          <div className="flex items-center gap-2">
            <span className={cn("rounded-full px-2.5 py-0.5 text-xs font-medium",
                                abierto ? "bg-primary/10 text-primary" : "bg-muted text-muted-foreground")}>
              {abierto ? "Abierto" : `Cerrado el ${inv.fecha_cierre}`}
            </span>
            {puedeLeer && (
              <Button variant="outline" size="sm" onClick={() => setCerrando(true)}>
                <Lock className="mr-2 h-4 w-4" />Cerrar inventario
              </Button>
            )}
          </div>
        </div>

        <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
          <Tarjeta titulo="Esperados" valor={inv.esperados} />
          <Tarjeta titulo="Leídos de lo esperado" valor={inv.esperados_leidos} pie={`${inv.avance} %`} />
          <Tarjeta titulo="Faltantes" valor={inv.faltantes_total} alerta={inv.faltantes_total > 0} />
          <Tarjeta titulo="A revisar" valor={problemas} alerta={problemas > 0} pie="fuera de lugar, estados raros, códigos desconocidos" />
        </div>
        <div className="h-2 overflow-hidden rounded-full bg-muted" role="progressbar" aria-label="Avance"
             aria-valuenow={inv.avance} aria-valuemin={0} aria-valuemax={100}>
          <div className="h-full bg-primary transition-[width]" style={{ width: `${inv.avance}%` }} />
        </div>

        {puedeLeer && <Lector onLeer={leer} recientes={recientes} />}

        <Tabs defaultValue="faltantes">
          <TabsList>
            <TabsTrigger value="faltantes">Faltantes ({inv.faltantes_total})</TabsTrigger>
            <TabsTrigger value="problemas">A revisar ({problemas})</TabsTrigger>
            <TabsTrigger value="lecturas">Lecturas ({inv.lecturas})</TabsTrigger>
          </TabsList>
          <TabsContent value="faltantes" className="mt-4">
            <Faltantes inv={inv} />
          </TabsContent>
          <TabsContent value="problemas" className="mt-4">
            <Lecturas filas={inv.ultimas_lecturas.filter((l) => PROBLEMAS.includes(l.resultado))}
                      vacio="Nada para revisar." />
          </TabsContent>
          <TabsContent value="lecturas" className="mt-4">
            <Lecturas filas={inv.ultimas_lecturas} vacio="Todavía no se leyó nada."
                      nota={inv.lecturas > inv.ultimas_lecturas.length ? `Las últimas ${inv.ultimas_lecturas.length}.` : undefined} />
          </TabsContent>
        </Tabs>
      </div>

      <AlertDialog open={cerrando} onOpenChange={setCerrando}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>¿Cerrar el inventario?</AlertDialogTitle>
            <AlertDialogDescription>
              Se guarda el resultado como está ({inv.esperados_leidos} de {inv.esperados} leídos,
              {" "}{inv.faltantes_total} faltantes) y ya no se pueden leer más códigos. Los faltantes no
              se marcan como perdidos: eso lo decides tú, ejemplar por ejemplar.
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel>Seguir leyendo</AlertDialogCancel>
            <AlertDialogAction onClick={cerrar}>Cerrar inventario</AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </AppLayout>
  )
}

function Tarjeta({ titulo, valor, pie, alerta = false }: { titulo: string; valor: number; pie?: string; alerta?: boolean }) {
  return (
    <div className={cn("rounded-lg border bg-card p-4", alerta ? "border-destructive/30" : "border-border")}>
      <p className="text-sm text-muted-foreground">{titulo}</p>
      <p className={cn("mt-1 text-2xl font-semibold tabular-nums", alerta ? "text-destructive" : "text-foreground")}>{valor}</p>
      {pie && <p className="text-xs text-muted-foreground">{pie}</p>}
    </div>
  )
}

/** El escáner: un campo que recibe un código y Enter, y la carga de muchos a la vez. */
function Lector({ onLeer, recientes }: { onLeer: (codigos: string[]) => Promise<LecturaInventario[]>; recientes: LecturaInventario[] }) {
  const [codigo, setCodigo] = useState("")
  const [lote, setLote] = useState("")
  const [enviando, setEnviando] = useState(false)
  const campo = useRef<HTMLInputElement>(null)
  const archivo = useRef<HTMLInputElement>(null)

  async function enviar(codigos: string[]) {
    if (codigos.length === 0) return
    setEnviando(true)
    try {
      const lecturas = await onLeer(codigos)
      if (codigos.length > 1) {
        const malos = lecturas.filter((l) => TONO_RESULTADO[l.resultado] === "problema").length
        toast.success(`${lecturas.length} códigos leídos`, { description: malos ? `${malos} para revisar` : "Todo en su lugar" })
      }
      return true
    } catch (e) {
      toast.error("No se pudo registrar la lectura", { description: mensajeDeError(e) })
      return false
    } finally {
      setEnviando(false)
      campo.current?.focus()
    }
  }

  async function porArchivo(e: React.ChangeEvent<HTMLInputElement>) {
    const f = e.target.files?.[0]
    if (!f) return
    await enviar(codigosDe(await f.text()))
    e.target.value = ""
  }

  return (
    <section aria-labelledby="leer" className="grid gap-4 lg:grid-cols-2">
      <div className="space-y-3 rounded-lg border border-border bg-card p-4">
        <h2 id="leer" className="flex items-center gap-2 font-semibold text-foreground"><ScanBarcode className="h-4 w-4" />Leer</h2>
        <form onSubmit={async (e) => {
          e.preventDefault()
          const c = codigo.trim()
          if (!c || enviando) return
          setCodigo("")
          if (!await enviar([c])) setCodigo(c)
        }} className="flex gap-2">
          <Label htmlFor="codigo-inventario" className="sr-only">Código de barras</Label>
          {/* Sin `disabled` mientras envía: deshabilitado pierde el foco y el escáner escribiría en otro lado. */}
          <Input id="codigo-inventario" ref={campo} autoFocus autoComplete="off" value={codigo}
                 placeholder="Escanea o escribe el código y Enter" onChange={(e) => setCodigo(e.target.value)} />
          <Button type="submit" disabled={enviando || !codigo.trim()}>Leer</Button>
        </form>
        <details>
          <summary className="cursor-pointer text-sm text-muted-foreground">Cargar muchos a la vez</summary>
          <div className="mt-3 space-y-2">
            <Label htmlFor="lote-inventario">Pega los códigos (uno por línea)</Label>
            <Textarea id="lote-inventario" rows={4} value={lote} onChange={(e) => setLote(e.target.value)} />
            <div className="flex flex-wrap gap-2">
              <Button type="button" variant="outline" disabled={enviando || !lote.trim()}
                      onClick={async () => { if (await enviar(codigosDe(lote))) setLote("") }}>
                Leer {codigosDe(lote).length || ""} códigos
              </Button>
              <Button type="button" variant="outline" disabled={enviando} onClick={() => archivo.current?.click()}>
                <FileUp className="mr-2 h-4 w-4" />Desde un archivo
              </Button>
              <input ref={archivo} type="file" accept=".txt,.csv,text/plain,text/csv" className="hidden" onChange={porArchivo} />
            </div>
            <p className="text-xs text-muted-foreground">Sirve el archivo de un lector portátil: un código por línea, o separados por comas.</p>
          </div>
        </details>
      </div>
      <div className="rounded-lg border border-border bg-card p-4" aria-live="polite">
        <h3 className="mb-2 text-sm font-medium text-muted-foreground">Recién leídos</h3>
        {recientes.length === 0 ? (
          <p className="py-6 text-center text-sm text-muted-foreground">Lo que leas aparece aquí.</p>
        ) : (
          <ul className="max-h-64 space-y-1.5 overflow-y-auto">
            {recientes.map((l, n) => (
              <li key={`${l.codigo_barras}-${n}`}
                  className={cn("flex items-start gap-2 rounded-md border px-3 py-2 text-sm", CLASES_TONO[TONO_RESULTADO[l.resultado]])}>
                {TONO_RESULTADO[l.resultado] === "problema" ? <XCircle className="mt-0.5 h-4 w-4 shrink-0" />
                  : <CheckCircle2 className="mt-0.5 h-4 w-4 shrink-0" />}
                <div className="min-w-0">
                  <p><span className="font-mono">{l.codigo_barras}</span> · {l.resultado_nombre}</p>
                  {(l.titulo || l.detalle) && (
                    <p className="truncate text-xs text-foreground/70">{[l.titulo, l.detalle].filter(Boolean).join(" — ")}</p>
                  )}
                </div>
              </li>
            ))}
          </ul>
        )}
      </div>
    </section>
  )
}

function Faltantes({ inv }: { inv: InventarioDetalle }) {
  const [exportando, setExportando] = useState(false)
  if (inv.faltantes.length === 0) {
    return <p className="py-8 text-center text-sm text-muted-foreground">
      {inv.esperados === 0 ? "No hay ejemplares esperados en este alcance." : "No falta nada."}</p>
  }
  return (
    <div className="rounded-lg border border-border bg-card">
      <div className="flex items-center justify-between border-b border-border px-4 py-3">
        <p className="text-sm text-muted-foreground">En orden de estante. Están Disponibles en el sistema pero no se leyeron.</p>
        <Button variant="outline" size="sm" disabled={exportando} onClick={async () => {
          setExportando(true)
          try {
            await apiDownload(`/inventories/${inv.id}/missing.csv`, "faltantes.csv")
          } catch (e) {
            toast.error("No se pudo exportar", { description: mensajeDeError(e) })
          } finally {
            setExportando(false)
          }
        }}>
          {exportando ? <Loader2 className="mr-2 h-4 w-4 animate-spin" /> : <Download className="mr-2 h-4 w-4" />}CSV
        </Button>
      </div>
      <div className="overflow-x-auto">
        <table className="w-full min-w-[560px] text-sm">
          <thead>
            <tr className="bg-muted/50 text-left text-muted-foreground">
              <th className="px-4 py-2 font-medium">Signatura</th>
              <th className="px-4 py-2 font-medium">Código</th>
              <th className="px-4 py-2 font-medium">Título</th>
              <th className="px-4 py-2 font-medium">Visto por última vez</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-border">
            {inv.faltantes.map((f) => (
              <tr key={f.codigo_barras}>
                <td className="px-4 py-2 font-mono text-xs">{f.signatura ?? "—"}</td>
                <td className="px-4 py-2 font-mono text-xs">{f.codigo_barras}</td>
                <td className="px-4 py-2">
                  {f.biblio_id ? <Link href={`/catalogo/${f.biblio_id}`} className="text-primary hover:underline">{f.titulo}</Link> : f.titulo}
                </td>
                <td className="px-4 py-2 text-muted-foreground">{f.ultimo_inventario ?? "Nunca"}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  )
}

function Lecturas({ filas, vacio, nota }: { filas: LecturaInventario[]; vacio: string; nota?: string }) {
  if (filas.length === 0) return <p className="py-8 text-center text-sm text-muted-foreground">{vacio}</p>
  return (
    <div className="rounded-lg border border-border bg-card">
      {nota && <p className="border-b border-border px-4 py-2 text-xs text-muted-foreground">{nota}</p>}
      <ul className="divide-y divide-border">
        {filas.map((l, n) => (
          <li key={`${l.codigo_barras}-${n}`} className="flex flex-col gap-1 px-4 py-3 text-sm sm:flex-row sm:items-start sm:justify-between">
            <div className="min-w-0">
              <p className="text-foreground"><span className="font-mono">{l.codigo_barras}</span>
                {l.titulo && <> · {l.biblio_id ? <Link href={`/catalogo/${l.biblio_id}`} className="text-primary hover:underline">{l.titulo}</Link> : l.titulo}</>}
              </p>
              {l.detalle && <p className="text-xs text-muted-foreground">{l.detalle}</p>}
            </div>
            <div className="flex shrink-0 items-center gap-3">
              <span className={cn("rounded-full border px-2 py-0.5 text-xs", CLASES_TONO[TONO_RESULTADO[l.resultado]])}>{l.resultado_nombre}</span>
              {l.fecha && <span className="text-xs tabular-nums text-muted-foreground">{l.fecha}</span>}
            </div>
          </li>
        ))}
      </ul>
    </div>
  )
}
