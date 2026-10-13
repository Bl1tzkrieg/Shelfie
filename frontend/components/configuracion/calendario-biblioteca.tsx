"use client"

import { useState } from "react"
import { Loader2, Plus, Trash2 } from "lucide-react"
import { toast } from "sonner"

import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { apiDelete, apiPost, apiPut, mensajeDeError } from "@/lib/api"
import type { CalendarioBiblioteca, Feriado } from "@/lib/types"
import { cn } from "@/lib/utils"

/** 0 = lunes … 6 = domingo, como en el backend (date.weekday()). */
const DIAS = ["Lunes", "Martes", "Miércoles", "Jueves", "Viernes", "Sábado", "Domingo"]
const MESES = ["ene", "feb", "mar", "abr", "may", "jun", "jul", "ago", "sep", "oct", "nov", "dic"]

function hoyIso() {
  const d = new Date()
  const dos = (n: number) => String(n).padStart(2, "0")
  return `${d.getFullYear()}-${dos(d.getMonth() + 1)}-${dos(d.getDate())}`
}

/** "2026-12-25" → "vie 25 dic 2026", sin pasar por zonas horarias. */
function formatearFeriado(iso: string) {
  const [a, m, d] = iso.split("-").map(Number)
  const dia = DIAS[(new Date(Date.UTC(a, m - 1, d)).getUTCDay() + 6) % 7]
  return `${dia.slice(0, 3).toLowerCase()} ${String(d).padStart(2, "0")} ${MESES[m - 1]} ${a}`
}

interface CalendarioProps {
  calendario: CalendarioBiblioteca
  onChange: (calendario: CalendarioBiblioteca) => void
}

export function CalendarioBibliotecaPanel({ calendario, onChange }: CalendarioProps) {
  return (
    <div className="grid gap-8 lg:grid-cols-[minmax(0,1fr)_minmax(0,1.4fr)]">
      <DiasCerrados
        key={calendario.dias_cerrados.join(",")}
        actuales={calendario.dias_cerrados}
        onChange={onChange}
      />
      <Feriados feriados={calendario.feriados} onChange={onChange} />
    </div>
  )
}

function DiasCerrados({
  actuales,
  onChange,
}: {
  actuales: number[]
  onChange: (c: CalendarioBiblioteca) => void
}) {
  const [seleccion, setSeleccion] = useState<number[]>(actuales)
  const [guardando, setGuardando] = useState(false)
  const cambio = seleccion.join(",") !== actuales.join(",")

  function alternar(dia: number) {
    setSeleccion((s) => (s.includes(dia) ? s.filter((d) => d !== dia) : [...s, dia].sort()))
  }

  async function guardar() {
    setGuardando(true)
    try {
      const c = await apiPut<CalendarioBiblioteca>("/calendar/closed-days", { dias: seleccion })
      toast.success("Días cerrados actualizados")
      onChange(c)
    } catch (error) {
      toast.error("No se pudieron guardar los días cerrados", { description: mensajeDeError(error) })
    } finally {
      setGuardando(false)
    }
  }

  return (
    <div className="space-y-3">
      <div>
        <h4 className="text-sm font-medium text-foreground">Cierra todas las semanas</h4>
        <p className="text-sm text-muted-foreground">
          Un vencimiento que cae en día cerrado pasa al siguiente día hábil, y esos días no
          cuentan para multas ni para el plazo de retiro de reservas.
        </p>
      </div>
      <div className="flex flex-wrap gap-2" role="group" aria-label="Días cerrados">
        {DIAS.map((nombre, i) => {
          const cerrado = seleccion.includes(i)
          return (
            <button
              key={nombre}
              type="button"
              aria-pressed={cerrado}
              onClick={() => alternar(i)}
              className={cn(
                "rounded-md border px-3 py-1.5 text-sm transition-colors",
                cerrado
                  ? "border-destructive/30 bg-destructive/10 text-destructive"
                  : "border-border bg-card text-foreground hover:bg-muted"
              )}
            >
              {nombre}
            </button>
          )
        })}
      </div>
      <p className="text-xs text-muted-foreground">
        {seleccion.length === 0
          ? "Abre todos los días."
          : `Cerrado: ${seleccion.map((d) => DIAS[d].toLowerCase()).join(", ")}.`}
      </p>
      <Button size="sm" onClick={guardar} disabled={!cambio || guardando}>
        {guardando && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}
        Guardar días cerrados
      </Button>
    </div>
  )
}

function Feriados({
  feriados,
  onChange,
}: {
  feriados: Feriado[]
  onChange: (c: CalendarioBiblioteca) => void
}) {
  const [fecha, setFecha] = useState("")
  const [descripcion, setDescripcion] = useState("")
  const [enviando, setEnviando] = useState(false)
  const [borrando, setBorrando] = useState<number | null>(null)
  const [verPasados, setVerPasados] = useState(false)

  const hoy = hoyIso()
  const proximos = feriados.filter((f) => f.fecha >= hoy)
  const pasados = feriados.filter((f) => f.fecha < hoy)

  async function agregar(e: React.FormEvent) {
    e.preventDefault()
    setEnviando(true)
    try {
      const c = await apiPost<CalendarioBiblioteca>("/calendar/holidays", {
        fecha,
        descripcion: descripcion.trim(),
      })
      toast.success("Feriado agregado", { description: `${formatearFeriado(fecha)} · ${descripcion.trim()}` })
      setFecha("")
      setDescripcion("")
      onChange(c)
    } catch (error) {
      toast.error("No se pudo agregar el feriado", { description: mensajeDeError(error) })
    } finally {
      setEnviando(false)
    }
  }

  async function quitar(f: Feriado) {
    setBorrando(f.id)
    try {
      onChange(await apiDelete<CalendarioBiblioteca>(`/calendar/holidays/${f.id}`))
      toast.success("Feriado eliminado", { description: f.descripcion })
    } catch (error) {
      toast.error("No se pudo eliminar el feriado", { description: mensajeDeError(error) })
    } finally {
      setBorrando(null)
    }
  }

  const lista = verPasados ? [...pasados, ...proximos] : proximos

  return (
    <div className="space-y-3">
      <div>
        <h4 className="text-sm font-medium text-foreground">Feriados y cierres puntuales</h4>
        <p className="text-sm text-muted-foreground">
          Días concretos en que la biblioteca no abre: feriados nacionales, vacaciones colectivas,
          inventario.
        </p>
      </div>

      <form onSubmit={agregar} className="grid gap-3 sm:grid-cols-[10rem_minmax(0,1fr)_auto] sm:items-end">
        <div className="space-y-1.5">
          <Label htmlFor="feriado-fecha">Fecha</Label>
          <Input
            id="feriado-fecha"
            type="date"
            value={fecha}
            onChange={(e) => setFecha(e.target.value)}
            required
          />
        </div>
        <div className="space-y-1.5">
          <Label htmlFor="feriado-descripcion">Motivo</Label>
          <Input
            id="feriado-descripcion"
            value={descripcion}
            maxLength={150}
            placeholder="Batalla de Carabobo"
            onChange={(e) => setDescripcion(e.target.value)}
            required
          />
        </div>
        <Button type="submit" disabled={enviando || !fecha || !descripcion.trim()}>
          {enviando ? <Loader2 className="mr-2 h-4 w-4 animate-spin" /> : <Plus className="mr-2 h-4 w-4" />}
          Agregar
        </Button>
      </form>

      {lista.length === 0 ? (
        <p className="rounded-lg border border-dashed border-border py-6 text-center text-sm text-muted-foreground">
          No hay feriados próximos registrados.
        </p>
      ) : (
        <ul className="divide-y divide-border rounded-lg border border-border">
          {lista.map((f) => {
            const pasado = f.fecha < hoy
            return (
              <li key={f.id} className="flex items-center gap-3 px-4 py-2.5">
                <span
                  className={cn(
                    "w-32 shrink-0 text-sm tabular-nums",
                    pasado ? "text-muted-foreground" : "font-medium text-foreground"
                  )}
                >
                  {formatearFeriado(f.fecha)}
                </span>
                <span className={cn("min-w-0 flex-1 truncate text-sm", pasado && "text-muted-foreground")}>
                  {f.descripcion}
                </span>
                <Button
                  variant="ghost"
                  size="icon"
                  aria-label={`Eliminar el feriado ${f.descripcion}`}
                  disabled={borrando === f.id}
                  onClick={() => quitar(f)}
                >
                  {borrando === f.id ? (
                    <Loader2 className="h-4 w-4 animate-spin" />
                  ) : (
                    <Trash2 className="h-4 w-4 text-destructive" />
                  )}
                </Button>
              </li>
            )
          })}
        </ul>
      )}
      {pasados.length > 0 && (
        <button
          type="button"
          className="text-sm text-primary hover:underline"
          onClick={() => setVerPasados((v) => !v)}
        >
          {verPasados ? "Ocultar los pasados" : `Ver también los ${pasados.length} pasados`}
        </button>
      )}
    </div>
  )
}
