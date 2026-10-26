"use client"

import { useEffect, useRef, useState } from "react"
import { Loader2, RotateCcw, Save } from "lucide-react"
import { toast } from "sonner"

import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { Switch } from "@/components/ui/switch"
import { Textarea } from "@/components/ui/textarea"
import { apiGet, apiPost, apiPut, mensajeDeError } from "@/lib/api"
import type { PlantillaAviso } from "@/lib/types"
import { cn } from "@/lib/utils"

const ESPERA_VISTA_PREVIA_MS = 400

/** Editor de las plantillas: asunto, cuerpo, marcadores y vista previa con datos de ejemplo. */
export function PlantillasAvisos({ puedeEditar }: { puedeEditar: boolean }) {
  const [plantillas, setPlantillas] = useState<PlantillaAviso[] | null>(null)
  const [elegida, setElegida] = useState<string | null>(null)

  useEffect(() => {
    apiGet<PlantillaAviso[]>("/notices/templates")
      .then((p) => {
        setPlantillas(p)
        setElegida((e) => e ?? p[0]?.codigo ?? null)
      })
      .catch((e) => toast.error("No se pudieron cargar las plantillas", { description: mensajeDeError(e) }))
  }, [])

  if (!plantillas) return <Loader2 className="mx-auto my-8 h-5 w-5 animate-spin text-muted-foreground" />
  const actual = plantillas.find((p) => p.codigo === elegida)

  return (
    <div className="grid gap-6 lg:grid-cols-[16rem_1fr]">
      <ul className="space-y-1" aria-label="Plantillas">
        {plantillas.map((p) => (
          <li key={p.codigo}>
            <button type="button" onClick={() => setElegida(p.codigo)} aria-pressed={p.codigo === elegida}
                    className={cn("flex w-full items-center justify-between gap-2 rounded-md px-3 py-2 text-left text-sm transition-colors",
                                  p.codigo === elegida ? "bg-primary/10 font-medium text-primary" : "hover:bg-muted")}>
              <span>{p.nombre}</span>
              {!p.activo ? <Badge variant="outline">Apagada</Badge> : p.modificada ? <Badge variant="secondary">Editada</Badge> : null}
            </button>
          </li>
        ))}
      </ul>
      {actual && (
        <Editor key={actual.codigo} plantilla={actual} puedeEditar={puedeEditar}
                onGuardada={(p) => setPlantillas((todas) => todas?.map((x) => (x.codigo === p.codigo ? p : x)) ?? null)} />
      )}
    </div>
  )
}

function Editor({ plantilla, puedeEditar, onGuardada }:
  { plantilla: PlantillaAviso; puedeEditar: boolean; onGuardada: (p: PlantillaAviso) => void }) {
  const [asunto, setAsunto] = useState(plantilla.asunto)
  const [cuerpo, setCuerpo] = useState(plantilla.cuerpo)
  const [previa, setPrevia] = useState<{ asunto: string; cuerpo: string } | null>(null)
  const [errorPrevia, setErrorPrevia] = useState<string | null>(null)
  const [guardando, setGuardando] = useState(false)
  const cuerpoRef = useRef<HTMLTextAreaElement>(null)
  const cambiada = asunto !== plantilla.asunto || cuerpo !== plantilla.cuerpo

  useEffect(() => {
    const t = setTimeout(() => {
      apiPost<{ asunto: string; cuerpo: string }>(`/notices/templates/${plantilla.codigo}/preview`, { asunto, cuerpo })
        .then((p) => {
          setPrevia(p)
          setErrorPrevia(null)
        })
        .catch((e) => setErrorPrevia(mensajeDeError(e)))
    }, ESPERA_VISTA_PREVIA_MS)
    return () => clearTimeout(t)
  }, [plantilla.codigo, asunto, cuerpo])

  async function guardar(datos: Record<string, unknown>, aviso: string) {
    setGuardando(true)
    try {
      const p = await apiPut<PlantillaAviso>(`/notices/templates/${plantilla.codigo}`, datos)
      onGuardada(p)
      setAsunto(p.asunto)
      setCuerpo(p.cuerpo)
      toast.success(aviso)
    } catch (e) {
      toast.error("No se pudo guardar", { description: mensajeDeError(e) })
    } finally {
      setGuardando(false)
    }
  }

  function insertar(marcador: string) {
    const area = cuerpoRef.current
    const texto = `{${marcador}}`
    if (!area) return setCuerpo((c) => c + texto)
    const { selectionStart: inicio, selectionEnd: fin } = area
    setCuerpo((c) => c.slice(0, inicio) + texto + c.slice(fin))
    requestAnimationFrame(() => {
      area.focus()
      area.setSelectionRange(inicio + texto.length, inicio + texto.length)
    })
  }

  return (
    <div className="grid gap-6 xl:grid-cols-2">
      <div className="space-y-4">
        <div className="flex items-start justify-between gap-4">
          <div>
            <h3 className="font-semibold text-foreground">{plantilla.nombre}</h3>
            <p className="text-sm text-muted-foreground">{plantilla.cuando}</p>
          </div>
          <label className="flex shrink-0 items-center gap-2 text-sm">
            <Switch checked={plantilla.activo} disabled={!puedeEditar || guardando}
                    onCheckedChange={(v) => guardar({ activo: v }, v ? "Plantilla encendida" : "Plantilla apagada: no se mandará")} />
            Se envía
          </label>
        </div>
        <div className="space-y-2">
          <Label htmlFor="plantilla-asunto">Asunto</Label>
          <Input id="plantilla-asunto" value={asunto} maxLength={300} disabled={!puedeEditar}
                 onChange={(e) => setAsunto(e.target.value)} />
        </div>
        <div className="space-y-2">
          <Label htmlFor="plantilla-cuerpo">Mensaje</Label>
          <Textarea id="plantilla-cuerpo" ref={cuerpoRef} rows={12} value={cuerpo} maxLength={5000}
                    disabled={!puedeEditar} className="font-mono text-sm" onChange={(e) => setCuerpo(e.target.value)} />
        </div>
        <div>
          <p className="mb-1.5 text-xs text-muted-foreground">Marcadores (clic para insertar en el mensaje):</p>
          <div className="flex flex-wrap gap-1.5">
            {plantilla.marcadores.map((m) => (
              <button key={m} type="button" disabled={!puedeEditar} onClick={() => insertar(m)}
                      className="rounded border bg-muted px-1.5 py-0.5 font-mono text-xs hover:border-primary hover:text-primary disabled:opacity-60">
                {`{${m}}`}
              </button>
            ))}
          </div>
        </div>
        {puedeEditar && (
          <div className="flex flex-wrap justify-end gap-2">
            {plantilla.modificada && (
              <Button variant="ghost" disabled={guardando}
                      onClick={() => guardar({ restablecer: true }, "Volvió el texto original")}>
                <RotateCcw className="mr-2 h-4 w-4" /> Texto original
              </Button>
            )}
            <Button disabled={!cambiada || guardando || !!errorPrevia}
                    onClick={() => guardar({ asunto, cuerpo }, "Plantilla guardada")}>
              {guardando ? <Loader2 className="mr-2 h-4 w-4 animate-spin" /> : <Save className="mr-2 h-4 w-4" />}
              Guardar
            </Button>
          </div>
        )}
      </div>

      <div className="space-y-2">
        <p className="text-sm font-medium text-foreground">Así le llega al lector (datos de ejemplo)</p>
        {errorPrevia ? (
          <p role="alert" className="rounded-md bg-destructive/10 px-3 py-2 text-sm text-destructive">{errorPrevia}</p>
        ) : previa ? (
          <div className="rounded-lg border bg-card shadow-papel">
            <p className="border-b px-4 py-2.5 text-sm font-medium text-foreground">{previa.asunto}</p>
            <pre className="whitespace-pre-wrap px-4 py-3 font-sans text-sm text-foreground">{previa.cuerpo}</pre>
          </div>
        ) : (
          <Loader2 className="my-6 h-5 w-5 animate-spin text-muted-foreground" />
        )}
      </div>
    </div>
  )
}
