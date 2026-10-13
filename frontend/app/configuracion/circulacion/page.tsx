"use client"

import { useCallback, useEffect, useState } from "react"
import Link from "next/link"
import { ArrowLeft, CalendarDays, Loader2, Save, Scale, Wallet } from "lucide-react"
import { toast } from "sonner"

import { AppLayout } from "@/components/layout/app-layout"
import { Header } from "@/components/layout/header"
import { CalendarioBibliotecaPanel } from "@/components/configuracion/calendario-biblioteca"
import { ReglasCirculacion } from "@/components/configuracion/reglas-circulacion"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { Switch } from "@/components/ui/switch"
import { apiGet, apiPut, mensajeDeError } from "@/lib/api"
import type {
  CalendarioBiblioteca,
  Configuracion,
  OpcionesRegla,
  ReglaCirculacion,
} from "@/lib/types"

type AjustesCirculacion = Configuracion["circulacion"]

export default function ReglasYCalendarioPage() {
  const [reglas, setReglas] = useState<ReglaCirculacion[] | null>(null)
  const [opciones, setOpciones] = useState<OpcionesRegla | null>(null)
  const [calendario, setCalendario] = useState<CalendarioBiblioteca | null>(null)
  const [ajustes, setAjustes] = useState<AjustesCirculacion | null>(null)
  const [error, setError] = useState<string | null>(null)

  const cargarReglas = useCallback(async () => {
    try {
      setReglas(await apiGet<ReglaCirculacion[]>("/circulation-rules"))
    } catch (e) {
      toast.error("No se pudieron cargar las reglas", { description: mensajeDeError(e) })
    }
  }, [])

  useEffect(() => {
    Promise.all([
      apiGet<ReglaCirculacion[]>("/circulation-rules"),
      apiGet<OpcionesRegla>("/circulation-rules/options"),
      apiGet<CalendarioBiblioteca>("/calendar"),
      apiGet<Configuracion>("/settings"),
    ])
      .then(([r, o, c, s]) => {
        setReglas(r)
        setOpciones(o)
        setCalendario(c)
        setAjustes(s.circulacion)
      })
      .catch((e) => setError(mensajeDeError(e)))
  }, [])

  const listo = reglas && opciones && calendario && ajustes

  return (
    <AppLayout permiso="configuracion">
      <Header
        title="Reglas y calendario"
        description="Cómo se presta, cuándo vence y cuánto se cobra"
      />

      <div className="p-6">
        <div className="mx-auto max-w-6xl space-y-8">
          <Link
            href="/configuracion"
            className="inline-flex items-center gap-1 text-sm text-muted-foreground hover:text-foreground"
          >
            <ArrowLeft className="h-4 w-4" />
            Configuración
          </Link>

          {!listo ? (
            <div className="rounded-lg border bg-card py-16 text-center text-muted-foreground">
              {error ? `No se pudo cargar: ${error}` : "Cargando reglas y calendario…"}
            </div>
          ) : (
            <>
              <Seccion
                icono={Scale}
                titulo="Reglas de circulación"
                descripcion="Plazos, topes, renovaciones y multas por categoría de lector, tipo de ítem y sede"
              >
                <ReglasCirculacion reglas={reglas} opciones={opciones} onChange={cargarReglas} />
              </Seccion>

              <Seccion
                icono={CalendarDays}
                titulo="Calendario"
                descripcion="Días en que la biblioteca no abre"
              >
                <CalendarioBibliotecaPanel calendario={calendario} onChange={setCalendario} />
              </Seccion>

              <Seccion
                icono={Wallet}
                titulo="Deudas y reservas"
                descripcion="Valores que aplican a todas las reglas"
              >
                <AjustesGenerales
                  key={JSON.stringify(ajustes)}
                  ajustes={ajustes}
                  onSaved={setAjustes}
                />
              </Seccion>
            </>
          )}
        </div>
      </div>
    </AppLayout>
  )
}

function AjustesGenerales({
  ajustes,
  onSaved,
}: {
  ajustes: AjustesCirculacion
  onSaved: (a: AjustesCirculacion) => void
}) {
  const [textos, setTextos] = useState({
    umbral_bloqueo: String(ajustes.umbral_bloqueo),
    dias_retiro_reserva: String(ajustes.dias_retiro_reserva),
    precio_reposicion: String(ajustes.precio_reposicion),
  })
  const [retorno, setRetorno] = useState(ajustes.retorno_a_sede_propia)
  const [guardando, setGuardando] = useState(false)

  const valores = {
    umbral_bloqueo: Number(textos.umbral_bloqueo),
    dias_retiro_reserva: Math.trunc(Number(textos.dias_retiro_reserva)),
    precio_reposicion: Number(textos.precio_reposicion),
  }
  const validos =
    Object.values(textos).every((t) => t.trim() !== "") &&
    Object.values(valores).every((n) => Number.isFinite(n) && n >= 0) &&
    valores.dias_retiro_reserva >= 1
  const cambio =
    valores.umbral_bloqueo !== ajustes.umbral_bloqueo ||
    valores.dias_retiro_reserva !== ajustes.dias_retiro_reserva ||
    valores.precio_reposicion !== ajustes.precio_reposicion ||
    retorno !== ajustes.retorno_a_sede_propia

  async function guardar(e: React.FormEvent) {
    e.preventDefault()
    setGuardando(true)
    try {
      const c = await apiPut<Configuracion>("/settings", { circulacion: { ...valores, retorno_a_sede_propia: retorno } })
      toast.success("Ajustes guardados")
      onSaved(c.circulacion)
    } catch (error) {
      toast.error("No se pudieron guardar los ajustes", { description: mensajeDeError(error) })
    } finally {
      setGuardando(false)
    }
  }

  return (
    <form onSubmit={guardar} className="space-y-4">
      <div className="grid gap-4 sm:grid-cols-3">
        <Campo
          id="ajuste-umbral"
          label="Deuda máxima permitida (Bs.)"
          ayuda="Por encima de este monto el lector no puede retirar, renovar ni reservar."
          valor={textos.umbral_bloqueo}
          decimales
          onChange={(v) => setTextos((t) => ({ ...t, umbral_bloqueo: v }))}
        />
        <Campo
          id="ajuste-retiro"
          label="Días hábiles para retirar una reserva"
          ayuda="Pasado el plazo, el ejemplar apartado pasa al siguiente de la cola."
          valor={textos.dias_retiro_reserva}
          onChange={(v) => setTextos((t) => ({ ...t, dias_retiro_reserva: v }))}
        />
        <Campo
          id="ajuste-reposicion"
          label="Reposición por defecto (Bs.)"
          ayuda="Se cobra al declarar perdido un ejemplar que no tiene precio propio."
          valor={textos.precio_reposicion}
          decimales
          onChange={(v) => setTextos((t) => ({ ...t, precio_reposicion: v }))}
        />
      </div>
      <div className="flex items-start gap-3 rounded-lg border border-border p-4">
        <Switch id="ajuste-retorno" checked={retorno} onCheckedChange={setRetorno}
                aria-describedby="ajuste-retorno-ayuda" />
        <div className="space-y-1">
          <Label htmlFor="ajuste-retorno">Devolver cada ejemplar a su sede propia</Label>
          <p id="ajuste-retorno-ayuda" className="text-xs text-muted-foreground">
            Si se devuelve en otra sede y nadie lo reservó, se genera un traslado de vuelta.
            Apagado, el ejemplar se queda donde lo devolvieron (colección flotante).
          </p>
        </div>
      </div>
      <div className="flex justify-end">
        <Button type="submit" disabled={!validos || !cambio || guardando}>
          {guardando ? (
            <Loader2 className="mr-2 h-4 w-4 animate-spin" />
          ) : (
            <Save className="mr-2 h-4 w-4" />
          )}
          Guardar ajustes
        </Button>
      </div>
    </form>
  )
}

function Seccion({
  icono: Icono,
  titulo,
  descripcion,
  children,
}: {
  icono: typeof Scale
  titulo: string
  descripcion: string
  children: React.ReactNode
}) {
  return (
    <section className="rounded-lg border border-border bg-card">
      <div className="border-b border-border px-6 py-4">
        <div className="flex items-center gap-3">
          <Icono className="h-5 w-5 text-primary" />
          <div>
            <h3 className="font-semibold text-foreground">{titulo}</h3>
            <p className="text-sm text-muted-foreground">{descripcion}</p>
          </div>
        </div>
      </div>
      <div className="p-6">{children}</div>
    </section>
  )
}

function Campo({
  id,
  label,
  ayuda,
  valor,
  decimales = false,
  onChange,
}: {
  id: string
  label: string
  ayuda: string
  valor: string
  decimales?: boolean
  onChange: (v: string) => void
}) {
  return (
    <div className="space-y-2">
      <Label htmlFor={id}>{label}</Label>
      <Input
        id={id}
        type="number"
        min={decimales ? 0 : 1}
        step={decimales ? "0.01" : "1"}
        value={valor}
        onChange={(e) => onChange(e.target.value)}
        aria-describedby={`${id}-ayuda`}
      />
      <p id={`${id}-ayuda`} className="text-xs text-muted-foreground">
        {ayuda}
      </p>
    </div>
  )
}
