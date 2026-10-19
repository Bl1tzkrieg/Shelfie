"use client"

import { useCallback, useEffect, useState } from "react"
import { CheckCircle2, Loader2, Mail, Play, Save, XCircle } from "lucide-react"
import { toast } from "sonner"

import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { Switch } from "@/components/ui/switch"
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table"
import { apiGet, apiPost, apiPut, mensajeDeError } from "@/lib/api"
import type { AjustesAvisos, CorridaTarea, ResumenAvisos, TareaProgramada } from "@/lib/types"

const MODOS = {
  archivo: "Se guardan como archivos .eml (modo de prueba, no salen de este equipo)",
  smtp: "Se envían por el servidor SMTP",
  desactivado: "Desactivado: los avisos esperan en la cola",
}

function resumirResultado(r: CorridaTarea["resultado"]): string {
  if (!r) return ""
  return Object.entries(r)
    .filter(([, v]) => typeof v === "number" || typeof v === "string")
    .map(([k, v]) => `${k.replace(/_/g, " ")}: ${v}`)
    .join(" · ")
}

export function TareasAvisos({ resumen, puedeEditar, onCambio }:
  { resumen: ResumenAvisos; puedeEditar: boolean; onCambio: () => void }) {
  return (
    <div className="space-y-8">
      <Correo resumen={resumen} puedeEditar={puedeEditar} />
      <Ajustes inicial={resumen.ajustes} puedeEditar={puedeEditar} onCambio={onCambio} />
      <Tareas resumen={resumen} puedeEditar={puedeEditar} onCambio={onCambio} />
    </div>
  )
}

function Correo({ resumen, puedeEditar }: { resumen: ResumenAvisos; puedeEditar: boolean }) {
  const [destino, setDestino] = useState("")
  const [enviando, setEnviando] = useState(false)
  const { correo } = resumen

  async function probar(e: React.FormEvent) {
    e.preventDefault()
    setEnviando(true)
    try {
      const r = await apiPost<{ mensaje: string }>("/notices/test", { destinatario: destino.trim() })
      toast.success(r.mensaje, {
        description: correo.modo === "archivo" ? `Revisa la carpeta ${correo.carpeta}` : undefined,
      })
    } catch (err) {
      toast.error("No salió el correo de prueba", { description: mensajeDeError(err) })
    } finally {
      setEnviando(false)
    }
  }

  return (
    <section className="space-y-3">
      <h3 className="font-semibold text-foreground">Correo</h3>
      <div className="grid gap-4 rounded-lg border bg-card p-4 md:grid-cols-2">
        <dl className="space-y-1.5 text-sm">
          <div className="flex gap-2">
            <dt className="w-24 shrink-0 text-muted-foreground">Envío</dt>
            <dd className="text-foreground">{MODOS[correo.modo]}</dd>
          </div>
          <div className="flex gap-2">
            <dt className="w-24 shrink-0 text-muted-foreground">Remitente</dt>
            <dd className="break-all text-foreground">{correo.remitente}</dd>
          </div>
          {correo.servidor && (
            <div className="flex gap-2">
              <dt className="w-24 shrink-0 text-muted-foreground">Servidor</dt>
              <dd className="font-mono text-foreground">{correo.servidor}</dd>
            </div>
          )}
          {correo.carpeta && (
            <div className="flex gap-2">
              <dt className="w-24 shrink-0 text-muted-foreground">Carpeta</dt>
              <dd className="break-all font-mono text-xs text-foreground">{correo.carpeta}</dd>
            </div>
          )}
          <p className="pt-1 text-xs text-muted-foreground">
            Se cambia en el <code>.env</code> del backend (CORREO_MODO, SMTP_HOST…) y se reinicia.
          </p>
        </dl>
        {puedeEditar && (
          <form onSubmit={probar} className="space-y-2">
            <Label htmlFor="correo-prueba">Mandar un correo de prueba a</Label>
            <div className="flex gap-2">
              <Input id="correo-prueba" type="email" required placeholder="tu@correo.com"
                     value={destino} onChange={(e) => setDestino(e.target.value)} />
              <Button type="submit" variant="outline" disabled={enviando || !destino.trim()}>
                {enviando ? <Loader2 className="h-4 w-4 animate-spin" /> : <Mail className="h-4 w-4" />}
                <span className="sr-only sm:not-sr-only sm:ml-2">Probar</span>
              </Button>
            </div>
          </form>
        )}
      </div>
    </section>
  )
}

function Ajustes({ inicial, puedeEditar, onCambio }:
  { inicial: AjustesAvisos; puedeEditar: boolean; onCambio: () => void }) {
  const [antes, setAntes] = useState(String(inicial.recordatorio_dias_antes))
  const [vencido, setVencido] = useState(inicial.dias_vencido.join(", "))
  const [automaticos, setAutomaticos] = useState(inicial.reclamos_automaticos)
  const [entre, setEntre] = useState(String(inicial.dias_entre_reclamos))
  const [guardando, setGuardando] = useState(false)

  const dias = vencido.split(/[,\s]+/).filter(Boolean).map(Number)
  const diasValidos = dias.length > 0 && dias.every((d) => Number.isInteger(d) && d >= 1 && d <= 365)

  async function guardar(e: React.FormEvent) {
    e.preventDefault()
    setGuardando(true)
    try {
      const r = await apiPut<AjustesAvisos>("/notices/settings", {
        recordatorio_dias_antes: Number(antes), dias_vencido: dias,
        reclamos_automaticos: automaticos, dias_entre_reclamos: Number(entre),
      })
      setVencido(r.dias_vencido.join(", "))
      toast.success("Ajustes de avisos guardados")
      onCambio()
    } catch (err) {
      toast.error("No se pudo guardar", { description: mensajeDeError(err) })
    } finally {
      setGuardando(false)
    }
  }

  return (
    <section className="space-y-3">
      <h3 className="font-semibold text-foreground">Cuándo se avisa</h3>
      <form onSubmit={guardar} className="grid gap-4 rounded-lg border bg-card p-4 md:grid-cols-2">
        <div className="space-y-2">
          <Label htmlFor="aviso-antes">Recordatorio antes del vencimiento (días)</Label>
          <Input id="aviso-antes" type="number" min={0} max={30} value={antes} disabled={!puedeEditar}
                 onChange={(e) => setAntes(e.target.value)} />
          <p className="text-xs text-muted-foreground">0 apaga el recordatorio.</p>
        </div>
        <div className="space-y-2">
          <Label htmlFor="aviso-vencido">Aviso de vencido a los días de atraso</Label>
          <Input id="aviso-vencido" value={vencido} disabled={!puedeEditar} aria-invalid={!diasValidos}
                 onChange={(e) => setVencido(e.target.value)} placeholder="1, 7, 14" />
          <p className="text-xs text-muted-foreground">Separados por coma. Cada correo lista todos sus vencidos.</p>
        </div>
        <div className="space-y-2">
          <label className="flex items-center gap-2 text-sm font-medium">
            <Switch checked={automaticos} disabled={!puedeEditar} onCheckedChange={setAutomaticos} />
            Reclamar solos los números atrasados de seriadas
          </label>
          <p className="text-xs text-muted-foreground">Un correo por proveedor, con la tarea diaria.</p>
        </div>
        <div className="space-y-2">
          <Label htmlFor="aviso-entre">Insistir con un reclamo cada (días)</Label>
          <Input id="aviso-entre" type="number" min={1} max={120} value={entre}
                 disabled={!puedeEditar || !automaticos} onChange={(e) => setEntre(e.target.value)} />
        </div>
        {puedeEditar && (
          <div className="flex justify-end md:col-span-2">
            <Button type="submit" disabled={guardando || !diasValidos}>
              {guardando ? <Loader2 className="mr-2 h-4 w-4 animate-spin" /> : <Save className="mr-2 h-4 w-4" />}
              Guardar
            </Button>
          </div>
        )}
      </form>
    </section>
  )
}

function Tareas({ resumen, puedeEditar, onCambio }:
  { resumen: ResumenAvisos; puedeEditar: boolean; onCambio: () => void }) {
  const [tareas, setTareas] = useState<TareaProgramada[] | null>(null)
  const [historial, setHistorial] = useState<CorridaTarea[]>([])
  const [corriendo, setCorriendo] = useState<string | null>(null)

  const cargar = useCallback(async () => {
    try {
      const [t, h] = await Promise.all([
        apiGet<{ tareas: TareaProgramada[] }>("/notices/tasks"),
        apiGet<CorridaTarea[]>("/notices/tasks/history"),
      ])
      setTareas(t.tareas)
      setHistorial(h)
    } catch (e) {
      toast.error("No se pudieron cargar las tareas", { description: mensajeDeError(e) })
    }
  }, [])

  useEffect(() => {
    cargar()
  }, [cargar])

  async function ejecutar(t: TareaProgramada) {
    setCorriendo(t.clave)
    try {
      const r = await apiPost<CorridaTarea>(`/notices/tasks/${t.clave}/run`)
      if (r.ok) toast.success(`${t.nombre}: listo`, { description: resumirResultado(r.resultado) || undefined })
      else toast.error(`${t.nombre} falló`, { description: r.error ?? undefined })
      await cargar()
      onCambio()
    } catch (e) {
      toast.error("No se pudo ejecutar", { description: mensajeDeError(e) })
    } finally {
      setCorriendo(null)
    }
  }

  const { tareas: auto } = resumen
  return (
    <section className="space-y-3">
      <div>
        <h3 className="font-semibold text-foreground">Tareas programadas</h3>
        <p className="text-sm text-muted-foreground">
          {auto.activas
            ? `Corren solas: la cola cada ${auto.cada_minutos_cola} minutos y las diarias desde las ${auto.hora_diarias}.`
            : "Las tareas automáticas están apagadas (TAREAS_AUTOMATICAS=false): prográmalas con python -m scripts.tareas."}
        </p>
      </div>
      {!tareas ? (
        <Loader2 className="mx-auto my-6 h-5 w-5 animate-spin text-muted-foreground" />
      ) : (
        <ul className="divide-y rounded-lg border bg-card">
          {tareas.map((t) => (
            <li key={t.clave} className="flex flex-col gap-2 px-4 py-3 sm:flex-row sm:items-center">
              <div className="min-w-0 flex-1">
                <p className="font-medium text-foreground">{t.nombre}</p>
                <p className="text-sm text-muted-foreground">{t.descripcion}</p>
                {t.ultima && (
                  <p className="mt-0.5 flex items-center gap-1 text-xs text-muted-foreground">
                    {t.ultima.ok ? <CheckCircle2 className="h-3.5 w-3.5 text-primary" /> : <XCircle className="h-3.5 w-3.5 text-destructive" />}
                    Última: {t.ultima.inicio} ({t.ultima.origen})
                    {t.ultima.error && <span className="text-destructive"> · {t.ultima.error}</span>}
                  </p>
                )}
              </div>
              {puedeEditar && (
                <Button size="sm" variant="outline" disabled={corriendo !== null} onClick={() => ejecutar(t)}
                        aria-label={`Ejecutar ${t.nombre}`}>
                  {corriendo === t.clave ? <Loader2 className="mr-2 h-4 w-4 animate-spin" /> : <Play className="mr-2 h-4 w-4" />}
                  Ejecutar ahora
                </Button>
              )}
            </li>
          ))}
        </ul>
      )}

      {historial.length > 0 && (
        <details className="rounded-lg border bg-card">
          <summary className="cursor-pointer px-4 py-3 text-sm font-medium">Últimas corridas</summary>
          <div className="overflow-x-auto border-t">
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Inicio</TableHead>
                  <TableHead>Tarea</TableHead>
                  <TableHead>Origen</TableHead>
                  <TableHead>Resultado</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {historial.map((c) => (
                  <TableRow key={c.id}>
                    <TableCell className="whitespace-nowrap tabular-nums">{c.inicio}</TableCell>
                    <TableCell>{c.tarea}</TableCell>
                    <TableCell><Badge variant="outline">{c.origen}</Badge></TableCell>
                    <TableCell className={c.ok ? "text-sm text-muted-foreground" : "text-sm text-destructive"}>
                      {c.ok ? resumirResultado(c.resultado) || "Listo" : c.error}
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </div>
        </details>
      )}
    </section>
  )
}
