"use client"

import { Suspense, useCallback, useEffect, useRef, useState } from "react"
import { usePathname, useRouter, useSearchParams } from "next/navigation"
import { ChevronLeft, ChevronRight, Download, Loader2, RotateCcw, Save, Search } from "lucide-react"
import { toast } from "sonner"

import { AppLayout } from "@/components/layout/app-layout"
import { Header } from "@/components/layout/header"
import { ListaAcciones, NOMBRE_MODULO } from "@/components/registro/lista-acciones"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select"
import { Switch } from "@/components/ui/switch"
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs"
import { apiDownload, apiGet, apiPut, mensajeDeError } from "@/lib/api"
import type { AjustesRegistro, PaginaRegistro } from "@/lib/types"

const FILTROS = ["modulo", "accion", "actor", "usuario", "codigo", "biblio_id", "desde", "hasta", "q"] as const
type Filtro = (typeof FILTROS)[number]
const TODOS = "todos"

export default function RegistroPage() {
  return (
    <Suspense fallback={null}>
      <Registro />
    </Suspense>
  )
}

function Registro() {
  const router = useRouter()
  const pathname = usePathname()
  const params = useSearchParams()
  const vista = params.get("vista") === "ajustes" ? "ajustes" : "acciones"
  const [ajustes, setAjustes] = useState<AjustesRegistro | null>(null)

  useEffect(() => {
    apiGet<AjustesRegistro>("/logs/settings").then(setAjustes).catch(() => setAjustes(null))
  }, [])

  function irA(v: string) {
    const p = new URLSearchParams(params.toString())
    if (v === "acciones") p.delete("vista")
    else p.set("vista", v)
    router.replace(`${pathname}?${p}`, { scroll: false })
  }

  return (
    <AppLayout permiso="superbibliotecario">
      <Header title="Registro de acciones" description="Quién hizo qué y cuándo" />
      <div className="p-4 sm:p-6">
        <Tabs value={vista} onValueChange={irA}>
          <TabsList>
            <TabsTrigger value="acciones">Acciones</TabsTrigger>
            <TabsTrigger value="ajustes">Qué se registra</TabsTrigger>
          </TabsList>
          <TabsContent value="acciones" className="mt-4">
            <Acciones ajustes={ajustes} />
          </TabsContent>
          <TabsContent value="ajustes" className="mt-4">
            {ajustes ? <Ajustes ajustes={ajustes} onGuardado={setAjustes} />
              : <Loader2 className="mx-auto mt-8 h-5 w-5 animate-spin text-muted-foreground" />}
          </TabsContent>
        </Tabs>
      </div>
    </AppLayout>
  )
}

function Acciones({ ajustes }: { ajustes: AjustesRegistro | null }) {
  const router = useRouter()
  const pathname = usePathname()
  const params = useSearchParams()
  const clave = params.toString()
  const pagina = Math.max(1, Number(params.get("pagina")) || 1)
  const [pagina_, setPagina] = useState<PaginaRegistro | null>(null)
  // Qué consulta respondió la última vez: si no es la actual, se está cargando.
  const [respondida, setRespondida] = useState<string | null>(null)
  const pedida = `${clave}#${pagina}`
  const cargando = respondida !== pedida
  const [exportando, setExportando] = useState(false)
  // Lo que se escribe en los campos de texto va a la URL al buscar, no con cada tecla.
  const [borrador, setBorrador] = useState<Record<Filtro, string>>(() => leerFiltros(params))
  const ultima = useRef(0)

  const consulta = useCallback(() => {
    const p = new URLSearchParams()
    for (const f of FILTROS) {
      const v = params.get(f)
      if (v) p.set(f, v)
    }
    return p
  }, [params])

  useEffect(() => {
    const id = ++ultima.current
    const p = consulta()
    p.set("pagina", String(pagina))
    apiGet<PaginaRegistro>(`/logs?${p}`)
      .then((r) => id === ultima.current && setPagina(r))
      .catch((e) => id === ultima.current && toast.error("No se pudo cargar el registro", { description: mensajeDeError(e) }))
      .finally(() => id === ultima.current && setRespondida(pedida))
  }, [pedida, pagina, consulta])

  function navegar(cambios: Partial<Record<Filtro | "pagina", string | null>>) {
    const p = new URLSearchParams(window.location.search)
    for (const [k, v] of Object.entries(cambios)) {
      if (!v || v === TODOS) p.delete(k)
      else p.set(k, v)
    }
    if (!("pagina" in cambios)) p.delete("pagina")
    router.replace(`${pathname}?${p}`, { scroll: false })
  }

  function buscar(e: React.FormEvent) {
    e.preventDefault()
    navegar({ ...borrador })
  }

  function limpiar() {
    const vacio = Object.fromEntries(FILTROS.map((f) => [f, ""])) as Record<Filtro, string>
    setBorrador(vacio)
    navegar(vacio)
  }

  async function exportar() {
    setExportando(true)
    try {
      await apiDownload(`/logs/export?${consulta()}`, "registro.csv")
    } catch (e) {
      toast.error("No se pudo exportar", { description: mensajeDeError(e) })
    } finally {
      setExportando(false)
    }
  }

  const modulo = params.get("modulo") || TODOS
  // Los módulos salen del backend: son los que realmente registra.
  const modulos = ajustes ? Object.keys(ajustes.descripciones) : Object.keys(NOMBRE_MODULO)
  const accionesDelModulo = ajustes ? Object.entries(ajustes.acciones) : []
  const set = (f: Filtro) => (e: React.ChangeEvent<HTMLInputElement>) =>
    setBorrador((b) => ({ ...b, [f]: e.target.value }))

  return (
    <div className="space-y-4">
      <form onSubmit={buscar} className="grid gap-3 rounded-lg border border-border bg-card p-4 sm:grid-cols-2 lg:grid-cols-4">
        <div className="space-y-1.5">
          <Label htmlFor="f-modulo">Módulo</Label>
          <Select value={modulo} onValueChange={(v) => navegar({ modulo: v, accion: null })}>
            <SelectTrigger id="f-modulo" className="w-full"><SelectValue /></SelectTrigger>
            <SelectContent>
              <SelectItem value={TODOS}>Todos</SelectItem>
              {modulos.map((k) => <SelectItem key={k} value={k}>{NOMBRE_MODULO[k] ?? k}</SelectItem>)}
            </SelectContent>
          </Select>
        </div>
        <div className="space-y-1.5">
          <Label htmlFor="f-accion">Acción</Label>
          <Select value={params.get("accion") || TODOS} onValueChange={(v) => navegar({ accion: v })}>
            <SelectTrigger id="f-accion" className="w-full"><SelectValue /></SelectTrigger>
            <SelectContent>
              <SelectItem value={TODOS}>Todas</SelectItem>
              {accionesDelModulo.map(([k, v]) => <SelectItem key={k} value={k}>{v}</SelectItem>)}
            </SelectContent>
          </Select>
        </div>
        <div className="space-y-1.5">
          <Label htmlFor="f-actor">Quién (usuario)</Label>
          <Input id="f-actor" value={borrador.actor} onChange={set("actor")} placeholder="maria.perez o «sistema»" />
        </div>
        <div className="space-y-1.5">
          <Label htmlFor="f-usuario">Usuario afectado</Label>
          <Input id="f-usuario" value={borrador.usuario} onChange={set("usuario")} />
        </div>
        <div className="space-y-1.5">
          <Label htmlFor="f-codigo">Código de barras</Label>
          <Input id="f-codigo" value={borrador.codigo} onChange={set("codigo")} />
        </div>
        <div className="space-y-1.5">
          <Label htmlFor="f-desde">Desde</Label>
          <Input id="f-desde" type="date" value={borrador.desde} onChange={set("desde")} />
        </div>
        <div className="space-y-1.5">
          <Label htmlFor="f-hasta">Hasta</Label>
          <Input id="f-hasta" type="date" value={borrador.hasta} onChange={set("hasta")} />
        </div>
        <div className="space-y-1.5">
          <Label htmlFor="f-q">Texto</Label>
          <Input id="f-q" value={borrador.q} onChange={set("q")} placeholder="Busca en la descripción" />
        </div>
        <div className="flex flex-wrap gap-2 sm:col-span-2 lg:col-span-4">
          <Button type="submit"><Search className="mr-2 h-4 w-4" />Buscar</Button>
          <Button type="button" variant="outline" onClick={limpiar}><RotateCcw className="mr-2 h-4 w-4" />Limpiar</Button>
          <Button type="button" variant="outline" className="sm:ml-auto" onClick={exportar} disabled={exportando}>
            {exportando ? <Loader2 className="mr-2 h-4 w-4 animate-spin" /> : <Download className="mr-2 h-4 w-4" />}
            Exportar CSV
          </Button>
        </div>
      </form>

      <section aria-live="polite" className="rounded-lg border border-border bg-card">
        <div className="flex items-center justify-between border-b border-border px-4 py-3">
          <p className="text-sm text-muted-foreground tabular-nums">
            {pagina_ ? `${pagina_.total} ${pagina_.total === 1 ? "acción" : "acciones"}` : "…"}
            {params.get("biblio_id") && " · de un registro del catálogo"}
          </p>
          {cargando && <Loader2 className="h-4 w-4 animate-spin text-muted-foreground" />}
        </div>
        {pagina_ && <ListaAcciones filas={pagina_.filas} />}
        {pagina_ && pagina_.paginas > 1 && (
          <nav aria-label="Páginas" className="flex items-center justify-between border-t border-border px-4 py-3">
            <Button variant="outline" size="sm" disabled={pagina <= 1}
                    onClick={() => navegar({ pagina: String(pagina - 1) })}>
              <ChevronLeft className="mr-1 h-4 w-4" />Anterior
            </Button>
            <span className="text-sm tabular-nums text-muted-foreground">Página {pagina} de {pagina_.paginas}</span>
            <Button variant="outline" size="sm" disabled={pagina >= pagina_.paginas}
                    onClick={() => navegar({ pagina: String(pagina + 1) })}>
              Siguiente<ChevronRight className="ml-1 h-4 w-4" />
            </Button>
          </nav>
        )}
      </section>
    </div>
  )
}

function leerFiltros(params: URLSearchParams) {
  return Object.fromEntries(FILTROS.map((f) => [f, params.get(f) ?? ""])) as Record<Filtro, string>
}

function Ajustes({ ajustes, onGuardado }: { ajustes: AjustesRegistro; onGuardado: (a: AjustesRegistro) => void }) {
  const [modulos, setModulos] = useState(ajustes.modulos)
  const [dias, setDias] = useState(String(ajustes.dias_retencion))
  const [guardando, setGuardando] = useState(false)
  const cambio = JSON.stringify(modulos) !== JSON.stringify(ajustes.modulos)
    || Number(dias) !== ajustes.dias_retencion
  const valido = dias.trim() !== "" && Number.isInteger(Number(dias)) && Number(dias) >= 0

  async function guardar(e: React.FormEvent) {
    e.preventDefault()
    setGuardando(true)
    try {
      const r = await apiPut<AjustesRegistro>("/logs/settings", { modulos, dias_retencion: Number(dias) })
      onGuardado(r)
      toast.success("Ajustes del registro guardados")
    } catch (error) {
      toast.error("No se pudieron guardar", { description: mensajeDeError(error) })
    } finally {
      setGuardando(false)
    }
  }

  return (
    <form onSubmit={guardar} className="max-w-2xl space-y-4">
      <div className="divide-y divide-border rounded-lg border border-border bg-card">
        {Object.entries(ajustes.descripciones).map(([modulo, descripcion]) => (
          <div key={modulo} className="flex items-start gap-3 p-4">
            <Switch id={`m-${modulo}`} checked={modulos[modulo] ?? true}
                    onCheckedChange={(v) => setModulos((m) => ({ ...m, [modulo]: v }))}
                    aria-describedby={`m-${modulo}-ayuda`} />
            <div className="space-y-0.5">
              <Label htmlFor={`m-${modulo}`}>{NOMBRE_MODULO[modulo] ?? modulo}</Label>
              <p id={`m-${modulo}-ayuda`} className="text-xs text-muted-foreground">{descripcion}</p>
            </div>
          </div>
        ))}
      </div>
      <div className="space-y-1.5">
        <Label htmlFor="dias-retencion">Días que se guarda el registro</Label>
        <Input id="dias-retencion" type="number" min={0} className="w-40" value={dias}
               onChange={(e) => setDias(e.target.value)} aria-describedby="dias-ayuda" />
        <p id="dias-ayuda" className="text-xs text-muted-foreground">
          La tarea de limpieza borra lo más viejo. 0 = guardar todo. Apagar un módulo o cambiar esto
          también queda registrado.
        </p>
      </div>
      <Button type="submit" disabled={!cambio || !valido || guardando}>
        {guardando ? <Loader2 className="mr-2 h-4 w-4 animate-spin" /> : <Save className="mr-2 h-4 w-4" />}
        Guardar
      </Button>
    </form>
  )
}
