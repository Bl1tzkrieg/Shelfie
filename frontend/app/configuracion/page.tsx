"use client"

import { useEffect, useState } from "react"
import { Building2, Clock, Bell, Database, Save, Loader2 } from "lucide-react"
import { toast } from "sonner"

import { AppLayout } from "@/components/layout/app-layout"
import { Header } from "@/components/layout/header"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select"
import { apiGet, apiPut, mensajeDeError } from "@/lib/api"
import type { Configuracion, SystemInfo } from "@/lib/types"

export default function ConfiguracionPage() {
  const [config, setConfig] = useState<Configuracion | null>(null)
  const [info, setInfo] = useState<SystemInfo | null>(null)
  const [cargando, setCargando] = useState(true)
  const [guardando, setGuardando] = useState(false)

  useEffect(() => {
    Promise.all([
      apiGet<Configuracion>("/settings"),
      apiGet<SystemInfo>("/settings/system-info").catch(() => null),
    ])
      .then(([c, i]) => {
        setConfig(c)
        setInfo(i)
      })
      .catch((e) =>
        toast.error("No se pudo cargar la configuración", { description: mensajeDeError(e) })
      )
      .finally(() => setCargando(false))
  }, [])

  function setInstitucion(campo: keyof Configuracion["institucion"], valor: string) {
    setConfig((c) => (c ? { ...c, institucion: { ...c.institucion, [campo]: valor } } : c))
  }

  function setPolitica(campo: keyof Configuracion["politicas_prestamo"], valor: string) {
    const numero = valor === "" ? 0 : Number(valor)
    setConfig((c) =>
      c ? { ...c, politicas_prestamo: { ...c.politicas_prestamo, [campo]: numero } } : c
    )
  }

  function setNotificacion(campo: keyof Configuracion["notificaciones"], valor: string) {
    setConfig((c) =>
      c
        ? {
            ...c,
            notificaciones: {
              ...c.notificaciones,
              [campo]: campo === "recordatorio_dias_antes" ? Number(valor) : valor,
            },
          }
        : c
    )
  }

  async function guardar() {
    if (!config) return
    setGuardando(true)
    try {
      const actualizada = await apiPut<Configuracion>("/settings", config)
      setConfig(actualizada)
      toast.success("Configuración guardada", {
        description: "Las políticas de préstamo se aplicaron a las categorías de usuario.",
      })
      apiGet<SystemInfo>("/settings/system-info").then(setInfo).catch(() => {})
    } catch (error) {
      toast.error("No se pudo guardar", { description: mensajeDeError(error) })
    } finally {
      setGuardando(false)
    }
  }

  if (cargando || !config) {
    return (
      <AppLayout>
        <Header title="Configuración" description="Ajustes del sistema de biblioteca" />
        <div className="p-6">
          <div className="rounded-lg border bg-card py-16 text-center text-muted-foreground">
            {cargando ? "Cargando configuración..." : "No se pudo cargar la configuración."}
          </div>
        </div>
      </AppLayout>
    )
  }

  const { institucion, politicas_prestamo: politicas, notificaciones } = config

  return (
    <AppLayout>
      <Header title="Configuración" description="Ajustes del sistema de biblioteca" />

      <div className="p-6">
        <div className="mx-auto max-w-4xl space-y-8">
          <Seccion
            icono={Building2}
            titulo="Información de la Institución"
            descripcion="Datos generales de la biblioteca"
          >
            <div className="grid gap-4 sm:grid-cols-2">
              <Campo label="Nombre de la Biblioteca">
                <Input
                  value={institucion.nombre}
                  onChange={(e) => setInstitucion("nombre", e.target.value)}
                />
              </Campo>
              <Campo label="Código">
                <Input
                  value={institucion.codigo}
                  onChange={(e) => setInstitucion("codigo", e.target.value)}
                />
              </Campo>
            </div>
            <Campo label="Dirección">
              <Input
                value={institucion.direccion}
                onChange={(e) => setInstitucion("direccion", e.target.value)}
              />
            </Campo>
            <div className="grid gap-4 sm:grid-cols-2">
              <Campo label="Teléfono">
                <Input
                  value={institucion.telefono}
                  onChange={(e) => setInstitucion("telefono", e.target.value)}
                />
              </Campo>
              <Campo label="Email">
                <Input
                  type="email"
                  value={institucion.email}
                  onChange={(e) => setInstitucion("email", e.target.value)}
                />
              </Campo>
            </div>
          </Seccion>

          <Seccion
            icono={Clock}
            titulo="Políticas de Préstamo"
            descripcion="Estos valores se aplican a las categorías de usuario y los usa el checkout"
          >
            <div className="grid gap-4 sm:grid-cols-3">
              <Campo label="Días préstamo (Estudiantes)">
                <Input
                  type="number"
                  min={1}
                  value={politicas.dias_estudiante}
                  onChange={(e) => setPolitica("dias_estudiante", e.target.value)}
                />
              </Campo>
              <Campo label="Días préstamo (Docentes)">
                <Input
                  type="number"
                  min={1}
                  value={politicas.dias_docente}
                  onChange={(e) => setPolitica("dias_docente", e.target.value)}
                />
              </Campo>
              <Campo label="Días préstamo (Personal)">
                <Input
                  type="number"
                  min={1}
                  value={politicas.dias_personal}
                  onChange={(e) => setPolitica("dias_personal", e.target.value)}
                />
              </Campo>
            </div>
            <div className="grid gap-4 sm:grid-cols-3">
              <Campo label="Máx. libros (Estudiantes)">
                <Input
                  type="number"
                  min={1}
                  value={politicas.max_estudiante}
                  onChange={(e) => setPolitica("max_estudiante", e.target.value)}
                />
              </Campo>
              <Campo label="Máx. libros (Docentes)">
                <Input
                  type="number"
                  min={1}
                  value={politicas.max_docente}
                  onChange={(e) => setPolitica("max_docente", e.target.value)}
                />
              </Campo>
              <Campo label="Renovaciones permitidas">
                <Input
                  type="number"
                  min={0}
                  value={politicas.renovaciones_permitidas}
                  onChange={(e) => setPolitica("renovaciones_permitidas", e.target.value)}
                />
              </Campo>
            </div>
            <Campo label="Multa por día de retraso">
              <div className="flex items-center gap-2">
                <span className="text-sm text-muted-foreground">Bs.</span>
                <Input
                  type="number"
                  min={0}
                  step="0.01"
                  className="w-32"
                  value={politicas.multa_por_dia}
                  onChange={(e) => setPolitica("multa_por_dia", e.target.value)}
                />
              </div>
            </Campo>
          </Seccion>

          <Seccion
            icono={Bell}
            titulo="Notificaciones"
            descripcion="Configuración de alertas automáticas"
          >
            <div className="grid gap-4 sm:grid-cols-2">
              <Campo label="Recordatorio antes de vencimiento">
                <Select
                  value={String(notificaciones.recordatorio_dias_antes)}
                  onValueChange={(v) => setNotificacion("recordatorio_dias_antes", v)}
                >
                  <SelectTrigger>
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="1">1 día antes</SelectItem>
                    <SelectItem value="2">2 días antes</SelectItem>
                    <SelectItem value="3">3 días antes</SelectItem>
                    <SelectItem value="5">5 días antes</SelectItem>
                  </SelectContent>
                </Select>
              </Campo>
              <Campo label="Canal de notificación">
                <Select
                  value={notificaciones.canal}
                  onValueChange={(v) => setNotificacion("canal", v)}
                >
                  <SelectTrigger>
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="email">Email</SelectItem>
                    <SelectItem value="sms">SMS</SelectItem>
                    <SelectItem value="both">Email + SMS</SelectItem>
                  </SelectContent>
                </Select>
              </Campo>
            </div>
          </Seccion>

          <Seccion icono={Database} titulo="Sistema" descripcion="Información técnica del sistema">
            <div className="grid gap-4 sm:grid-cols-2">
              <Dato label="Versión del Sistema" valor={info?.version || "—"} />
              <Dato
                label="Última actualización de ajustes"
                valor={info?.ultima_actualizacion || "Sin cambios registrados"}
              />
              <Dato label="Títulos catalogados" valor={String(info?.total_registros ?? "—")} />
              <Dato label="Ejemplares" valor={String(info?.total_ejemplares ?? "—")} />
              <Dato label="Usuarios" valor={String(info?.total_usuarios ?? "—")} />
              <Dato label="Préstamos históricos" valor={String(info?.total_prestamos ?? "—")} />
            </div>
          </Seccion>

          <div className="flex justify-end">
            <Button size="lg" onClick={guardar} disabled={guardando}>
              {guardando ? (
                <Loader2 className="mr-2 h-4 w-4 animate-spin" />
              ) : (
                <Save className="mr-2 h-4 w-4" />
              )}
              Guardar Cambios
            </Button>
          </div>
        </div>
      </div>
    </AppLayout>
  )
}

function Seccion({
  icono: Icono,
  titulo,
  descripcion,
  children,
}: {
  icono: typeof Building2
  titulo: string
  descripcion: string
  children: React.ReactNode
}) {
  return (
    <div className="rounded-lg border border-border bg-card">
      <div className="border-b border-border px-6 py-4">
        <div className="flex items-center gap-3">
          <Icono className="h-5 w-5 text-primary" />
          <div>
            <h3 className="font-semibold text-foreground">{titulo}</h3>
            <p className="text-sm text-muted-foreground">{descripcion}</p>
          </div>
        </div>
      </div>
      <div className="space-y-4 p-6">{children}</div>
    </div>
  )
}

function Campo({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div className="space-y-2">
      <label className="text-sm font-medium text-foreground">{label}</label>
      {children}
    </div>
  )
}

function Dato({ label, valor }: { label: string; valor: string }) {
  return (
    <div className="rounded-lg bg-muted/50 p-4">
      <p className="text-sm text-muted-foreground">{label}</p>
      <p className="mt-1 font-medium text-foreground">{valor}</p>
    </div>
  )
}
