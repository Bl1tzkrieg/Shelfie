"use client"

import { useCallback, useEffect, useState } from "react"
import { AlertTriangle, CheckCircle2, DatabaseBackup, Loader2, Save, Search, XCircle } from "lucide-react"
import { toast } from "sonner"

import { useSesion } from "@/components/auth/sesion-provider"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { apiGet, apiPost, apiPut, mensajeDeError } from "@/lib/api"
import { olvidarNombreBiblioteca } from "@/lib/biblioteca"
import { fechaDeBiblioteca, ZONA_BIBLIOTECA } from "@/lib/fechas"
import type { Configuracion, EstadoRespaldo } from "@/lib/types"
import { tamanoLegible } from "@/lib/utils"

type ResultadoRespaldo = {
  ok: boolean
  carpeta_creada: string | null
  mensaje: string
  tamano: number | null
  aviso?: string | null
}

const FECHA_HORA: Intl.DateTimeFormatOptions = { dateStyle: "long", timeStyle: "short" }

function fechaHora(iso: string) {
  return new Date(iso).toLocaleString("es-VE", { timeZone: ZONA_BIBLIOTECA, ...FECHA_HORA })
}

export function Ajustes() {
  const [config, setConfig] = useState<Configuracion | null>(null)

  useEffect(() => {
    apiGet<Configuracion>("/settings")
      .then(setConfig)
      .catch((e) => toast.error("No se pudo cargar la configuración", { description: mensajeDeError(e) }))
  }, [])

  if (!config) return <Loader2 className="mx-auto mt-8 h-5 w-5 animate-spin text-muted-foreground" />
  return (
    <div className="grid max-w-5xl gap-6 lg:grid-cols-2 lg:items-start">
      <TarjetaBiblioteca inicial={config.biblioteca} />
      <TarjetaRespaldo inicial={config.respaldo} />
    </div>
  )
}

function Tarjeta({ titulo, descripcion, children }: {
  titulo: string
  descripcion: string
  children: React.ReactNode
}) {
  return (
    <section className="space-y-4 rounded-xl border border-border/80 bg-card shadow-papel p-4 sm:p-6">
      <div>
        <h2 className="text-base font-semibold text-foreground">{titulo}</h2>
        <p className="text-sm text-muted-foreground">{descripcion}</p>
      </div>
      {children}
    </section>
  )
}

function TarjetaBiblioteca({ inicial }: { inicial: Configuracion["biblioteca"] }) {
  const original = {
    nombre: inicial.nombre ?? "", codigoSede: inicial.codigo_sede ?? "", tipoItem: inicial.tipo_item ?? "",
    codigoOrganizacion: inicial.codigo_organizacion ?? "",
  }
  const [guardado, setGuardado] = useState(original)
  const [f, setF] = useState(original)
  const [guardando, setGuardando] = useState(false)
  const completo = f.nombre.trim() !== "" && f.codigoSede.trim() !== "" && f.tipoItem.trim() !== ""
  const cambio = JSON.stringify(f) !== JSON.stringify(guardado)

  async function guardar(e: React.FormEvent) {
    e.preventDefault()
    setGuardando(true)
    try {
      const r = await apiPut<Configuracion>("/settings", {
        biblioteca: {
          nombre: f.nombre.trim(), codigo_sede: f.codigoSede.trim(), tipo_item: f.tipoItem.trim(),
          codigo_organizacion: f.codigoOrganizacion.trim(),
        },
      })
      const nuevo = {
        nombre: r.biblioteca.nombre ?? f.nombre, codigoSede: r.biblioteca.codigo_sede ?? f.codigoSede,
        tipoItem: r.biblioteca.tipo_item ?? f.tipoItem,
        codigoOrganizacion: r.biblioteca.codigo_organizacion ?? f.codigoOrganizacion,
      }
      setGuardado(nuevo)
      setF(nuevo)
      olvidarNombreBiblioteca()
      toast.success("Datos de la biblioteca guardados")
    } catch (error) {
      toast.error("No se pudieron guardar", { description: mensajeDeError(error) })
    } finally {
      setGuardando(false)
    }
  }

  const set = (k: keyof typeof f) => (e: React.ChangeEvent<HTMLInputElement>) =>
    setF((a) => ({ ...a, [k]: e.target.value }))

  return (
    <Tarjeta titulo="Biblioteca" descripcion="El nombre sale en el encabezado; los códigos, en cada registro MARC exportado.">
      <form onSubmit={guardar} className="space-y-4">
        <div className="space-y-1.5">
          <Label htmlFor="b-nombre">Nombre de la biblioteca</Label>
          <Input id="b-nombre" value={f.nombre} onChange={set("nombre")} maxLength={200} />
        </div>
        <div className="grid gap-4 sm:grid-cols-2">
          <div className="space-y-1.5">
            <Label htmlFor="b-codigo-sede">Código de sede (952 $a y $b)</Label>
            <Input id="b-codigo-sede" value={f.codigoSede} onChange={set("codigoSede")} maxLength={10}
                   aria-describedby="b-codigo-sede-ayuda" />
            <p id="b-codigo-sede-ayuda" className="text-xs text-muted-foreground">
              Identifica a esta biblioteca en cada ejemplar exportado (biblioteca propietaria y
              biblioteca donde está). Debe coincidir con el código que tenga esta biblioteca en el
              sistema que importe el archivo. Obligatorio, hasta 10 caracteres.
            </p>
          </div>
          <div className="space-y-1.5">
            <Label htmlFor="b-tipo-item">Tipo de ítem (952 $y)</Label>
            <Input id="b-tipo-item" value={f.tipoItem} onChange={set("tipoItem")} maxLength={10}
                   aria-describedby="b-tipo-item-ayuda" />
            <p id="b-tipo-item-ayuda" className="text-xs text-muted-foreground">
              Código del tipo de material que llevan los ejemplares exportados (p. ej. LIB). Debe
              existir en el sistema que importe el archivo. Obligatorio, hasta 10 caracteres; se
              exporta en mayúsculas.
            </p>
          </div>
        </div>
        <div className="space-y-1.5">
          <Label htmlFor="b-codigo-organizacion">Código de organización MARC (003)</Label>
          <Input id="b-codigo-organizacion" value={f.codigoOrganizacion}
                 onChange={set("codigoOrganizacion")} maxLength={16}
                 aria-describedby="b-codigo-organizacion-ayuda" />
          <p id="b-codigo-organizacion-ayuda" className="text-xs text-muted-foreground">
            Código MARC de la institución (lista de códigos de organizaciones MARC de la Biblioteca
            del Congreso). Si se deja vacío, los registros se exportan sin 003. Opcional, hasta 16
            caracteres; se respetan mayúsculas y minúsculas (p. ej. «VeMaLUZ»).
          </p>
        </div>
        <Button type="submit" disabled={!cambio || !completo || guardando}>
          {guardando ? <Loader2 className="mr-2 h-4 w-4 animate-spin" /> : <Save className="mr-2 h-4 w-4" />}
          Guardar
        </Button>
      </form>
    </Tarjeta>
  )
}

function TarjetaRespaldo({ inicial }: { inicial: Configuracion["respaldo"] }) {
  const { recargarSesion } = useSesion()
  const original = { carpeta: inicial?.carpeta ?? "", pg_dump: inicial?.pg_dump ?? "" }
  const [guardado, setGuardado] = useState(original)
  const [f, setF] = useState(original)
  const [estado, setEstado] = useState<EstadoRespaldo | null>(null)
  const [guardando, setGuardando] = useState(false)
  const [detectando, setDetectando] = useState(false)
  const [corriendo, setCorriendo] = useState(false)
  const [resultado, setResultado] = useState<ResultadoRespaldo | null>(null)
  const cambio = JSON.stringify(f) !== JSON.stringify(guardado)

  const cargarEstado = useCallback(async () => {
    try {
      setEstado(await apiGet<EstadoRespaldo>("/settings/backup"))
    } catch (e) {
      toast.error("No se pudo leer el estado del respaldo", { description: mensajeDeError(e) })
    }
  }, [])

  useEffect(() => {
    apiGet<EstadoRespaldo>("/settings/backup")
      .then(setEstado)
      .catch((e) => toast.error("No se pudo leer el estado del respaldo", { description: mensajeDeError(e) }))
  }, [])

  async function guardarRuta() {
    await apiPut("/settings", { respaldo: { carpeta: f.carpeta.trim(), pg_dump: f.pg_dump.trim() } })
    const limpio = { carpeta: f.carpeta.trim(), pg_dump: f.pg_dump.trim() }
    setGuardado(limpio)
    setF(limpio)
  }

  async function guardar(e: React.FormEvent) {
    e.preventDefault()
    setGuardando(true)
    try {
      await guardarRuta()
      toast.success("Ajustes del respaldo guardados")
    } catch (error) {
      toast.error("No se pudieron guardar", { description: mensajeDeError(error) })
    } finally {
      setGuardando(false)
    }
  }

  async function detectar() {
    setDetectando(true)
    try {
      const r = await apiGet<{ ruta: string | null }>("/settings/backup/pg_dump")
      if (r.ruta) {
        setF((a) => ({ ...a, pg_dump: r.ruta ?? "" }))
        toast.success("Se encontró pg_dump", { description: "Recuerda guardar para conservarlo." })
      } else {
        toast.error("No se encontró pg_dump en este equipo", {
          description: "Instala PostgreSQL o escribe la ruta a mano.",
        })
      }
    } catch (error) {
      toast.error("No se pudo buscar pg_dump", { description: mensajeDeError(error) })
    } finally {
      setDetectando(false)
    }
  }

  async function respaldar() {
    setCorriendo(true)
    setResultado(null)
    try {
      if (cambio) await guardarRuta()  // el respaldo usa lo guardado: que no sea lo viejo
      setResultado(await apiPost<ResultadoRespaldo>("/settings/backup"))
    } catch (error) {
      setResultado({ ok: false, carpeta_creada: null, mensaje: mensajeDeError(error), tamano: null })
    } finally {
      setCorriendo(false)
      await Promise.all([cargarEstado(), recargarSesion()])
    }
  }

  const ultimo = estado?.ultimo ?? null
  const set = (k: keyof typeof f) => (e: React.ChangeEvent<HTMLInputElement>) =>
    setF((a) => ({ ...a, [k]: e.target.value }))

  return (
    <Tarjeta titulo="Respaldo" descripcion="Una copia de la base y del catálogo en MARC y CSV, por si algo se pierde.">
      <form onSubmit={guardar} className="space-y-4">
        <div className="space-y-1.5">
          <Label htmlFor="r-carpeta">Carpeta del respaldo</Label>
          <Input id="r-carpeta" value={f.carpeta} onChange={set("carpeta")}
                 placeholder="D:\Respaldos\Shelfie" aria-describedby="r-reco r-permisos" />
          <p id="r-reco" className="text-xs text-muted-foreground">
            Conviene que sea otro disco o una carpeta de Drive u OneDrive: si el equipo se daña,
            el respaldo no se pierde con él. Se guardan los 30 últimos.
          </p>
          <p id="r-permisos" className="flex items-start gap-1.5 text-xs text-amber-700 dark:text-amber-400">
            <AlertTriangle className="mt-0.5 h-3.5 w-3.5 shrink-0" aria-hidden />
            <span>
              Si cambias la carpeta, vuelve a ejecutar instalar.ps1 para protegerla: los respaldos
              contienen las claves cifradas del personal.
            </span>
          </p>
        </div>
        <div className="space-y-1.5">
          <Label htmlFor="r-pgdump">Ruta de pg_dump</Label>
          <div className="flex gap-2">
            <Input id="r-pgdump" value={f.pg_dump} onChange={set("pg_dump")} className="font-mono text-sm"
                   placeholder="Se busca sola si la dejas vacía" />
            <Button type="button" variant="outline" onClick={detectar} disabled={detectando}>
              {detectando ? <Loader2 className="mr-1.5 h-4 w-4 animate-spin" /> : <Search className="mr-1.5 h-4 w-4" />}
              Detectar
            </Button>
          </div>
        </div>
        <Button type="submit" disabled={!cambio || guardando}>
          {guardando ? <Loader2 className="mr-2 h-4 w-4 animate-spin" /> : <Save className="mr-2 h-4 w-4" />}
          Guardar
        </Button>
      </form>

      <div className="space-y-3 border-t border-border pt-4">
        <h3 className="text-sm font-medium text-foreground">Último respaldo</h3>
        {estado === null ? (
          <Loader2 className="h-4 w-4 animate-spin text-muted-foreground" />
        ) : ultimo ? (
          <p className={`flex items-start gap-2 text-sm ${ultimo.ok ? "text-foreground" : "text-destructive"}`}>
            {ultimo.ok
              ? <CheckCircle2 className="mt-0.5 h-4 w-4 shrink-0 text-green-600 dark:text-green-500" aria-hidden />
              : <XCircle className="mt-0.5 h-4 w-4 shrink-0" aria-hidden />}
            <span>
              {ultimo.ok ? "Correcto" : "Falló"} · {fechaHora(ultimo.fecha)}
              {ultimo.ok && ultimo.tamano != null && ` · ${tamanoLegible(ultimo.tamano)}`}
              {!ultimo.ok && ultimo.mensaje && <><br /><span className="text-muted-foreground">{ultimo.mensaje}</span></>}
              {ultimo.ok && ultimo.aviso && (
                <><br /><span className="text-amber-700 dark:text-amber-400">{ultimo.aviso}</span></>
              )}
            </span>
          </p>
        ) : (
          <p className="text-sm text-muted-foreground">Todavía no se ha hecho ningún respaldo.</p>
        )}
        {estado?.ultimo_ok && !ultimo?.ok && (
          <p className="text-xs text-muted-foreground">
            El último correcto fue el {fechaDeBiblioteca(estado.ultimo_ok, { dateStyle: "long" })}.
          </p>
        )}

        <Button onClick={respaldar} disabled={corriendo}>
          {corriendo ? <Loader2 className="mr-2 h-4 w-4 animate-spin" /> : <DatabaseBackup className="mr-2 h-4 w-4" />}
          {corriendo ? "Respaldando…" : "Respaldar ahora"}
        </Button>

        <div aria-live="polite">
          {resultado && (resultado.ok ? (
            <p className="rounded-md border border-green-600/30 bg-green-600/10 p-3 text-sm text-green-700 dark:text-green-400">
              Respaldo creado en {resultado.carpeta_creada}
              {resultado.tamano != null && ` (${tamanoLegible(resultado.tamano)})`}
              {resultado.aviso && (
                <span className="mt-1 block text-amber-700 dark:text-amber-400">{resultado.aviso}</span>
              )}
            </p>
          ) : (
            <p className="rounded-md border border-destructive/30 bg-destructive/10 p-3 text-sm text-destructive">
              {resultado.mensaje}
            </p>
          ))}
        </div>
      </div>
    </Tarjeta>
  )
}
