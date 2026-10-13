"use client"

import { useRef, useState } from "react"
import { Download, FileUp, Loader2, Upload } from "lucide-react"
import { toast } from "sonner"

import { Button } from "@/components/ui/button"
import { Checkbox } from "@/components/ui/checkbox"
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog"
import { Label } from "@/components/ui/label"
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select"
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs"
import { apiDownload, apiUpload, mensajeDeError } from "@/lib/api"
import type { ResultadoImportacion } from "@/lib/types"
import { cn } from "@/lib/utils"

type Duplicados = "omitir" | "reemplazar" | "agregar"

const DUPLICADOS: Record<Duplicados, string> = {
  omitir: "Omitir el registro del archivo",
  reemplazar: "Reemplazar el MARC del que ya existe",
  agregar: "Agregarlo como registro aparte",
}

const ACCION: Record<ResultadoImportacion["registros"][number]["accion"], [string, string]> = {
  nuevo: ["Nuevo", "bg-primary/10 text-primary"],
  reemplazar: ["Reemplaza", "bg-accent/30 text-accent-foreground"],
  omitir: ["Se omite", "bg-muted text-muted-foreground"],
  error: ["Error", "bg-destructive/10 text-destructive"],
}

interface IntercambioMarcDialogProps {
  open: boolean
  onOpenChange: (open: boolean) => void
  /** Parámetros de la búsqueda actual, para exportar solo lo que se está viendo. */
  filtrosBusqueda: string
  totalBusqueda: number | null
  puedeImportar: boolean
  onImportado: () => void
}

export function IntercambioMarcDialog({
  open,
  onOpenChange,
  filtrosBusqueda,
  totalBusqueda,
  puedeImportar,
  onImportado,
}: IntercambioMarcDialogProps) {
  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-3xl">
        <DialogHeader>
          <DialogTitle>Importar y exportar MARC</DialogTitle>
          <DialogDescription>
            MARC21 en ISO 2709 (.mrc) o MARCXML. Los ejemplares viajan en el campo 952, como en
            Koha.
          </DialogDescription>
        </DialogHeader>
        <Tabs defaultValue={puedeImportar ? "importar" : "exportar"}>
          <TabsList>
            {puedeImportar && <TabsTrigger value="importar">Importar</TabsTrigger>}
            <TabsTrigger value="exportar">Exportar</TabsTrigger>
          </TabsList>
          {puedeImportar && (
            <TabsContent value="importar">
              <Importar onImportado={onImportado} />
            </TabsContent>
          )}
          <TabsContent value="exportar">
            <Exportar filtrosBusqueda={filtrosBusqueda} totalBusqueda={totalBusqueda} />
          </TabsContent>
        </Tabs>
      </DialogContent>
    </Dialog>
  )
}

function Importar({ onImportado }: { onImportado: () => void }) {
  const entrada = useRef<HTMLInputElement>(null)
  const [archivo, setArchivo] = useState<File | null>(null)
  const [duplicados, setDuplicados] = useState<Duplicados>("omitir")
  const [vista, setVista] = useState<ResultadoImportacion | null>(null)
  const [trabajando, setTrabajando] = useState<"vista" | "aplicar" | null>(null)

  async function enviar(modo: "vista" | "aplicar") {
    if (!archivo) return
    setTrabajando(modo)
    try {
      const r = await apiUpload<ResultadoImportacion>(
        `/catalog/import?modo=${modo}&duplicados=${duplicados}`,
        archivo
      )
      setVista(r)
      if (modo === "aplicar") {
        toast.success("Importación terminada", {
          description: `${r.nuevos} nuevo(s), ${r.reemplazados} reemplazado(s), ${r.ejemplares} ejemplar(es).`,
        })
        onImportado()
      }
    } catch (error) {
      toast.error("No se pudo leer el archivo", { description: mensajeDeError(error) })
    } finally {
      setTrabajando(null)
    }
  }

  return (
    <div className="space-y-4 pt-2">
      <div className="flex flex-wrap items-end gap-3">
        <div className="space-y-1.5">
          <Label htmlFor="importar-archivo">Archivo</Label>
          <input
            ref={entrada}
            id="importar-archivo"
            type="file"
            accept=".mrc,.marc,.xml,.marcxml,application/marc,application/xml,text/xml"
            className="block text-sm file:mr-3 file:rounded-md file:border file:border-border file:bg-card file:px-3 file:py-1.5 file:text-sm"
            onChange={(e) => {
              setArchivo(e.target.files?.[0] ?? null)
              setVista(null)
            }}
          />
        </div>
        <div className="space-y-1.5">
          <Label htmlFor="importar-duplicados">Si el ISBN ya existe</Label>
          <Select value={duplicados} onValueChange={(v) => { setDuplicados(v as Duplicados); setVista(null) }}>
            <SelectTrigger id="importar-duplicados" className="w-72">
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              {(Object.keys(DUPLICADOS) as Duplicados[]).map((d) => (
                <SelectItem key={d} value={d}>
                  {DUPLICADOS[d]}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        </div>
        <Button variant="outline" disabled={!archivo || trabajando !== null} onClick={() => enviar("vista")}>
          {trabajando === "vista" ? <Loader2 className="mr-2 h-4 w-4 animate-spin" /> : <FileUp className="mr-2 h-4 w-4" />}
          Revisar
        </Button>
      </div>

      {vista && (
        <div className="space-y-3">
          <p className="text-sm" aria-live="polite">
            {vista.aplicado ? "Se importaron" : "Se importarían"}{" "}
            <strong>{vista.nuevos}</strong> nuevo(s)
            {vista.reemplazados > 0 && <>, <strong>{vista.reemplazados}</strong> reemplazado(s)</>}
            {" "}y <strong>{vista.ejemplares}</strong> ejemplar(es) de {vista.total} registro(s)
            {vista.formato === "marcxml" ? " MARCXML" : " MARC"}.
            {vista.omitidos > 0 && <> {vista.omitidos} se omite(n).</>}
            {vista.con_errores > 0 && <span className="text-destructive"> {vista.con_errores} con errores.</span>}
          </p>
          <div className="max-h-72 overflow-y-auto rounded-lg border border-border">
            <table className="w-full text-sm">
              <thead className="sticky top-0 bg-muted/90 text-left text-muted-foreground">
                <tr>
                  <th className="px-3 py-2 font-medium">#</th>
                  <th className="px-3 py-2 font-medium">Título</th>
                  <th className="px-3 py-2 font-medium">ISBN</th>
                  <th className="px-3 py-2 font-medium">Ej.</th>
                  <th className="px-3 py-2 font-medium">Qué pasa</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-border">
                {vista.registros.map((r) => (
                  <tr key={r.n} className="align-top">
                    <td className="px-3 py-2 tabular-nums text-muted-foreground">{r.n}</td>
                    <td className="px-3 py-2">
                      <p className="font-medium text-foreground">{r.titulo || "—"}</p>
                      {r.autor && <p className="text-xs text-muted-foreground">{r.autor}</p>}
                      {r.mensajes.length > 0 && (
                        <ul className="mt-1 space-y-0.5 text-xs text-muted-foreground">
                          {r.mensajes.slice(0, 3).map((m, i) => <li key={i}>{m}</li>)}
                          {r.mensajes.length > 3 && <li>… y {r.mensajes.length - 3} más</li>}
                        </ul>
                      )}
                    </td>
                    <td className="px-3 py-2 font-mono text-xs">{r.isbn ?? "—"}</td>
                    <td className="px-3 py-2 tabular-nums">{r.ejemplares}</td>
                    <td className="px-3 py-2">
                      <span className={cn("rounded-full px-2 py-0.5 text-xs font-medium", ACCION[r.accion][1])}>
                        {ACCION[r.accion][0]}
                      </span>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          {!vista.aplicado && (
            <div className="flex justify-end">
              <Button disabled={trabajando !== null || vista.nuevos + vista.reemplazados === 0}
                      onClick={() => enviar("aplicar")}>
                {trabajando === "aplicar" ? <Loader2 className="mr-2 h-4 w-4 animate-spin" /> : <Upload className="mr-2 h-4 w-4" />}
                Importar {vista.nuevos + vista.reemplazados} registro(s)
              </Button>
            </div>
          )}
        </div>
      )}
    </div>
  )
}

function Exportar({ filtrosBusqueda, totalBusqueda }: { filtrosBusqueda: string; totalBusqueda: number | null }) {
  const [formato, setFormato] = useState<"marc" | "marcxml">("marc")
  const [ejemplares, setEjemplares] = useState(true)
  const [alcance, setAlcance] = useState<"busqueda" | "todo">(filtrosBusqueda ? "busqueda" : "todo")
  const [descargando, setDescargando] = useState(false)

  async function descargar() {
    setDescargando(true)
    try {
      const p = new URLSearchParams(alcance === "busqueda" ? filtrosBusqueda : "")
      p.set("formato", formato)
      p.set("ejemplares", String(ejemplares))
      await apiDownload(`/catalog/export?${p}`, formato === "marc" ? "catalogo.mrc" : "catalogo.xml")
    } catch (error) {
      toast.error("No se pudo exportar", { description: mensajeDeError(error) })
    } finally {
      setDescargando(false)
    }
  }

  return (
    <div className="space-y-4 pt-2">
      <div className="grid gap-4 sm:grid-cols-2">
        <div className="space-y-1.5">
          <Label htmlFor="exportar-formato">Formato</Label>
          <Select value={formato} onValueChange={(v) => setFormato(v as "marc" | "marcxml")}>
            <SelectTrigger id="exportar-formato">
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="marc">MARC21 ISO 2709 (.mrc)</SelectItem>
              <SelectItem value="marcxml">MARCXML (.xml)</SelectItem>
            </SelectContent>
          </Select>
        </div>
        <div className="space-y-1.5">
          <Label htmlFor="exportar-alcance">Qué registros</Label>
          <Select value={alcance} onValueChange={(v) => setAlcance(v as "busqueda" | "todo")}>
            <SelectTrigger id="exportar-alcance">
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              {filtrosBusqueda && (
                <SelectItem value="busqueda">
                  Los de la búsqueda actual{totalBusqueda !== null ? ` (${totalBusqueda})` : ""}
                </SelectItem>
              )}
              <SelectItem value="todo">Todo el catálogo</SelectItem>
            </SelectContent>
          </Select>
        </div>
      </div>
      <div className="flex items-center gap-2">
        <Checkbox id="exportar-ejemplares" checked={ejemplares}
                  onCheckedChange={(v) => setEjemplares(v === true)} />
        <Label htmlFor="exportar-ejemplares" className="font-normal">
          Incluir los ejemplares (952: código de barras, signatura, tipo, sede)
        </Label>
      </div>
      <div className="flex justify-end">
        <Button onClick={descargar} disabled={descargando}>
          {descargando ? <Loader2 className="mr-2 h-4 w-4 animate-spin" /> : <Download className="mr-2 h-4 w-4" />}
          Descargar
        </Button>
      </div>
    </div>
  )
}
