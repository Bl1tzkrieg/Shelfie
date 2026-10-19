"use client"

import { useEffect, useRef, useState } from "react"
import { useRouter } from "next/navigation"
import { Check, Loader2, Search } from "lucide-react"
import { toast } from "sonner"

import type { Book } from "@/components/catalogo/book-card"
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
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select"
import { Switch } from "@/components/ui/switch"
import { Tabs, TabsList, TabsTrigger } from "@/components/ui/tabs"
import { apiGet, apiPost, mensajeDeError } from "@/lib/api"
import type { BusquedaCatalogo, FasciculoPredicho, OpcionesRegla, Suscripcion, UnidadFrecuencia } from "@/lib/types"
import { cn } from "@/lib/utils"

/** Frecuencias habituales; "otra" deja elegir unidad y cada cuánto. */
export const FRECUENCIAS: { clave: string; texto: string; unidad: UnidadFrecuencia; cada: number }[] = [
  { clave: "diaria", texto: "Diaria", unidad: "dia", cada: 1 },
  { clave: "semanal", texto: "Semanal", unidad: "semana", cada: 1 },
  { clave: "quincenal", texto: "Quincenal", unidad: "semana", cada: 2 },
  { clave: "mensual", texto: "Mensual", unidad: "mes", cada: 1 },
  { clave: "bimestral", texto: "Bimestral", unidad: "mes", cada: 2 },
  { clave: "trimestral", texto: "Trimestral", unidad: "mes", cada: 3 },
  { clave: "semestral", texto: "Semestral", unidad: "mes", cada: 6 },
  { clave: "anual", texto: "Anual", unidad: "anio", cada: 1 },
  { clave: "irregular", texto: "Irregular (se cargan a mano)", unidad: "irregular", cada: 1 },
]

const SIN_PROVEEDOR = "ninguno"

export function NuevaSuscripcionDialog({ open, onOpenChange }: { open: boolean; onOpenChange: (v: boolean) => void }) {
  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-h-[90vh] overflow-y-auto sm:max-w-3xl">
        {open && <Formulario onCancel={() => onOpenChange(false)} />}
      </DialogContent>
    </Dialog>
  )
}

function hoyIso() {
  return new Date().toLocaleDateString("en-CA")
}

function Formulario({ onCancel }: { onCancel: () => void }) {
  const router = useRouter()
  const { sedes, sedeId } = useSedes()
  const [origen, setOrigen] = useState<"nuevo" | "catalogo">("nuevo")
  const [titulo, setTitulo] = useState("")
  const [issn, setIssn] = useState("")
  const [q, setQ] = useState("")
  const [resultados, setResultados] = useState<Book[] | null>(null)
  const [elegido, setElegido] = useState<Book | null>(null)
  const [proveedores, setProveedores] = useState<{ id: number; nombre: string }[]>([])
  const [tipos, setTipos] = useState<OpcionesRegla["tipos_item"]>([])
  const [proveedor, setProveedor] = useState(SIN_PROVEEDOR)
  const [frecuencia, setFrecuencia] = useState("mensual")
  const [numeracion, setNumeracion] = useState("Vol. {X}, Núm. {Y}")
  const [porVolumen, setPorVolumen] = useState("12")
  const [volumen, setVolumen] = useState("1")
  const [numero, setNumero] = useState("1")
  const [primero, setPrimero] = useState(hoyIso())
  const [fin, setFin] = useState("")
  const [gracia, setGracia] = useState("15")
  const [sede, setSede] = useState(sedeId ? String(sedeId) : "")
  const [tipo, setTipo] = useState("REV")
  const [crearEjemplares, setCrearEjemplares] = useState(true)
  const [prevista, setPrevista] = useState<FasciculoPredicho[]>([])
  const [errorPatron, setErrorPatron] = useState<string | null>(null)
  const [enviando, setEnviando] = useState(false)
  const ultima = useRef(0)

  const f = FRECUENCIAS.find((x) => x.clave === frecuencia)!
  const irregular = f.unidad === "irregular"
  const usaVolumen = numeracion.includes("{X}")

  useEffect(() => {
    apiGet<{ id: number; nombre: string }[]>("/serials/suppliers").then(setProveedores).catch(() => setProveedores([]))
    apiGet<OpcionesRegla>("/circulation-rules/options").then((o) => setTipos(o.tipos_item)).catch(() => setTipos([]))
  }, [])

  // Búsqueda en el catálogo (registro existente).
  useEffect(() => {
    if (origen !== "catalogo" || q.trim().length < 2) return
    const id = ++ultima.current
    const t = setTimeout(() => {
      apiGet<BusquedaCatalogo<Book>>(`/catalog/search?q=${encodeURIComponent(q.trim())}&por_pagina=6`)
        .then((r) => id === ultima.current && setResultados(r.resultados))
        .catch(() => id === ultima.current && setResultados([]))
    }, 250)
    return () => clearTimeout(t)
  }, [q, origen])

  // Vista previa del patrón: los próximos números que se esperarán.
  useEffect(() => {
    if (irregular || !primero) return
    // Una respuesta vieja (de antes de seguir escribiendo) no pisa a la nueva.
    let vigente = true
    const t = setTimeout(() => {
      apiPost<FasciculoPredicho[]>("/serials/prediction", {
        frecuencia_unidad: f.unidad,
        frecuencia_cada: f.cada,
        numeracion,
        numeros_por_volumen: usaVolumen && porVolumen ? Number(porVolumen) : null,
        volumen_inicial: Number(volumen || 1),
        numero_inicial: Number(numero || 1),
        primer_fasciculo: primero,
        cantidad: 6,
      })
        .then((p) => {
          if (!vigente) return
          setPrevista(p)
          setErrorPatron(null)
        })
        .catch((e) => {
          if (!vigente) return
          setPrevista([])
          setErrorPatron(mensajeDeError(e))
        })
    }, 300)
    return () => {
      vigente = false
      clearTimeout(t)
    }
  }, [irregular, f.unidad, f.cada, numeracion, usaVolumen, porVolumen, volumen, numero, primero])

  const valido =
    (origen === "nuevo" ? titulo.trim() !== "" : elegido !== null) &&
    (irregular || (errorPatron === null && prevista.length > 0))

  async function crear(e: React.FormEvent) {
    e.preventDefault()
    setEnviando(true)
    try {
      const s = await apiPost<Suscripcion>("/serials/subscriptions", {
        ...(origen === "nuevo" ? { titulo: titulo.trim(), issn: issn.trim() || null } : { biblio_id: Number(elegido!.id) }),
        proveedor_id: proveedor === SIN_PROVEEDOR ? null : Number(proveedor),
        biblioteca_id: sede ? Number(sede) : null,
        tipo_item_codigo: tipos.some((t) => t.codigo === tipo) ? tipo : null,
        crear_ejemplares: crearEjemplares,
        frecuencia_unidad: f.unidad,
        frecuencia_cada: f.cada,
        numeracion: irregular ? "" : numeracion,
        numeros_por_volumen: usaVolumen && porVolumen ? Number(porVolumen) : null,
        volumen_inicial: Number(volumen || 1),
        numero_inicial: Number(numero || 1),
        primer_fasciculo: primero,
        fecha_inicio: primero,
        fecha_fin: fin || null,
        dias_gracia: Number(gracia || 0),
      })
      toast.success("Suscripción creada", { description: s.titulo })
      router.push(`/seriadas/${s.id}`)
    } catch (error) {
      toast.error("No se pudo crear la suscripción", { description: mensajeDeError(error) })
      setEnviando(false)
    }
  }

  return (
    <form onSubmit={crear}>
      <DialogHeader>
        <DialogTitle>Nueva suscripción</DialogTitle>
        <DialogDescription>
          Con el patrón, Shelfie espera cada número en su fecha y avisa cuando se atrasa.
        </DialogDescription>
      </DialogHeader>

      <div className="grid gap-6 py-4 lg:grid-cols-[1fr_16rem]">
        <div className="space-y-5">
          <fieldset className="space-y-3">
            <legend className="text-sm font-semibold text-foreground">Publicación</legend>
            <Tabs value={origen} onValueChange={(v) => setOrigen(v as "nuevo" | "catalogo")}>
              <TabsList>
                <TabsTrigger value="nuevo">Título nuevo</TabsTrigger>
                <TabsTrigger value="catalogo">Ya está en el catálogo</TabsTrigger>
              </TabsList>
            </Tabs>
            {origen === "nuevo" ? (
              <div className="grid gap-3 sm:grid-cols-[1fr_10rem]">
                <div className="space-y-2">
                  <Label htmlFor="sus-titulo">Título</Label>
                  <Input id="sus-titulo" autoFocus value={titulo} onChange={(e) => setTitulo(e.target.value)} />
                </div>
                <div className="space-y-2">
                  <Label htmlFor="sus-issn">ISSN</Label>
                  <Input id="sus-issn" value={issn} placeholder="1234-5678" onChange={(e) => setIssn(e.target.value)} />
                </div>
              </div>
            ) : (
              <div className="space-y-2">
                <Label htmlFor="sus-buscar">Buscar el registro</Label>
                <div className="relative">
                  <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
                  <Input id="sus-buscar" className="pl-9" value={q} onChange={(e) => setQ(e.target.value)} />
                </div>
                {resultados && (
                  <ul className="max-h-40 divide-y divide-border overflow-y-auto rounded-md border">
                    {resultados.length === 0 && <li className="px-3 py-2 text-sm text-muted-foreground">Sin resultados.</li>}
                    {resultados.map((b) => (
                      <li key={b.id}>
                        <button type="button" onClick={() => setElegido(b)}
                                className={cn("flex w-full items-center justify-between px-3 py-2 text-left text-sm hover:bg-muted",
                                              elegido?.id === b.id && "bg-primary/10")}>
                          <span className="truncate">{b.title}</span>
                          {elegido?.id === b.id && <Check className="h-4 w-4 text-primary" />}
                        </button>
                      </li>
                    ))}
                  </ul>
                )}
              </div>
            )}
          </fieldset>

          <fieldset className="space-y-3">
            <legend className="text-sm font-semibold text-foreground">Patrón</legend>
            <div className="grid gap-3 sm:grid-cols-2">
              <div className="space-y-2">
                <Label htmlFor="sus-frecuencia">Frecuencia</Label>
                <Select value={frecuencia} onValueChange={setFrecuencia}>
                  <SelectTrigger id="sus-frecuencia" className="w-full"><SelectValue /></SelectTrigger>
                  <SelectContent>
                    {FRECUENCIAS.map((x) => <SelectItem key={x.clave} value={x.clave}>{x.texto}</SelectItem>)}
                  </SelectContent>
                </Select>
              </div>
              {!irregular && (
                <div className="space-y-2">
                  <Label htmlFor="sus-primero">Primer número esperado</Label>
                  <Input id="sus-primero" type="date" required value={primero} onChange={(e) => setPrimero(e.target.value)} />
                </div>
              )}
            </div>
            {!irregular && (
              <>
                <div className="space-y-2">
                  <Label htmlFor="sus-numeracion">Numeración</Label>
                  <Input id="sus-numeracion" value={numeracion} onChange={(e) => setNumeracion(e.target.value)}
                         aria-describedby="sus-numeracion-ayuda" />
                  <p id="sus-numeracion-ayuda" className="text-xs text-muted-foreground">
                    {"{X}"} volumen · {"{Y}"} número · {"{ANO}"} año · {"{MES}"} mes. Ej.: Vol. {"{X}"}, Núm. {"{Y}"} ({"{MES}"} {"{ANO}"})
                  </p>
                </div>
                <div className="grid gap-3 sm:grid-cols-3">
                  {usaVolumen && (
                    <div className="space-y-2">
                      <Label htmlFor="sus-volumen">Volumen inicial</Label>
                      <Input id="sus-volumen" type="number" min={0} value={volumen} onChange={(e) => setVolumen(e.target.value)} />
                    </div>
                  )}
                  <div className="space-y-2">
                    <Label htmlFor="sus-numero">Número inicial</Label>
                    <Input id="sus-numero" type="number" min={0} value={numero} onChange={(e) => setNumero(e.target.value)} />
                  </div>
                  {usaVolumen && (
                    <div className="space-y-2">
                      <Label htmlFor="sus-por-volumen">Números por volumen</Label>
                      <Input id="sus-por-volumen" type="number" min={1} value={porVolumen} onChange={(e) => setPorVolumen(e.target.value)} />
                    </div>
                  )}
                </div>
              </>
            )}
          </fieldset>

          <fieldset className="space-y-3">
            <legend className="text-sm font-semibold text-foreground">Recepción</legend>
            <div className="grid gap-3 sm:grid-cols-2">
              <div className="space-y-2">
                <Label htmlFor="sus-proveedor">Proveedor</Label>
                <Select value={proveedor} onValueChange={setProveedor}>
                  <SelectTrigger id="sus-proveedor" className="w-full"><SelectValue /></SelectTrigger>
                  <SelectContent>
                    <SelectItem value={SIN_PROVEEDOR}>Sin proveedor (canje, donación)</SelectItem>
                    {proveedores.map((p) => <SelectItem key={p.id} value={String(p.id)}>{p.nombre}</SelectItem>)}
                  </SelectContent>
                </Select>
              </div>
              <div className="space-y-2">
                <Label htmlFor="sus-fin">Vence el</Label>
                <Input id="sus-fin" type="date" value={fin} onChange={(e) => setFin(e.target.value)} />
              </div>
              <div className="space-y-2">
                <Label htmlFor="sus-gracia">Días de gracia antes de reclamar</Label>
                <Input id="sus-gracia" type="number" min={0} value={gracia} onChange={(e) => setGracia(e.target.value)} />
              </div>
              {sedes.length > 1 && (
                <div className="space-y-2">
                  <Label htmlFor="sus-sede">La recibe</Label>
                  <Select value={sede} onValueChange={setSede}>
                    <SelectTrigger id="sus-sede" className="w-full"><SelectValue /></SelectTrigger>
                    <SelectContent>
                      {sedes.map((s) => <SelectItem key={s.id} value={String(s.id)}>{s.nombre}</SelectItem>)}
                    </SelectContent>
                  </Select>
                </div>
              )}
            </div>
            <div className="flex flex-wrap items-center gap-x-6 gap-y-3">
              <div className="flex items-center gap-3">
                <Switch id="sus-ejemplares" checked={crearEjemplares} onCheckedChange={setCrearEjemplares} />
                <Label htmlFor="sus-ejemplares">Dar de alta un ejemplar por número</Label>
              </div>
              {crearEjemplares && tipos.length > 0 && (
                <div className="flex items-center gap-2">
                  <Label htmlFor="sus-tipo" className="font-normal">Tipo</Label>
                  <Select value={tipo} onValueChange={setTipo}>
                    <SelectTrigger id="sus-tipo" className="w-44"><SelectValue /></SelectTrigger>
                    <SelectContent>
                      {tipos.map((t) => <SelectItem key={t.codigo} value={t.codigo}>{t.nombre}</SelectItem>)}
                    </SelectContent>
                  </Select>
                </div>
              )}
            </div>
          </fieldset>
        </div>

        <aside className="space-y-2 rounded-lg border bg-muted/30 p-4" aria-live="polite">
          <p className="text-sm font-semibold text-foreground">Próximos números</p>
          {irregular ? (
            <p className="text-sm text-muted-foreground">Irregular: cada número se registra a mano cuando se anuncia.</p>
          ) : errorPatron ? (
            <p className="text-sm text-destructive">{errorPatron}</p>
          ) : (
            <ol className="space-y-1.5 text-sm">
              {prevista.map((p) => (
                <li key={p.fecha_esperada + p.numero} className="flex justify-between gap-2">
                  <span className="font-medium text-foreground">{p.numero}</span>
                  <span className="shrink-0 tabular-nums text-muted-foreground">{p.fecha_esperada}</span>
                </li>
              ))}
            </ol>
          )}
        </aside>
      </div>

      <DialogFooter>
        <Button type="button" variant="outline" onClick={onCancel}>Cancelar</Button>
        <Button type="submit" disabled={enviando || !valido}>
          {enviando && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}
          Crear suscripción
        </Button>
      </DialogFooter>
    </form>
  )
}
