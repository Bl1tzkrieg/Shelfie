"use client"

import { useEffect, useState } from "react"
import Link from "next/link"
import { ArrowRight, Building2, Clock, Bell, Database, Save, Loader2, MapPin } from "lucide-react"
import { toast } from "sonner"

import { AppLayout } from "@/components/layout/app-layout"
import { Header } from "@/components/layout/header"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { olvidarInstitucion } from "@/components/layout/sidebar"
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

  async function guardar() {
    if (!config) return
    setGuardando(true)
    try {
      // Solo lo que se edita aquí: las políticas viven en /configuracion/circulacion y
      // los avisos en /configuracion/avisos.
      const actualizada = await apiPut<Configuracion>("/settings", {
        institucion: config.institucion,
      })
      setConfig(actualizada)
      olvidarInstitucion()
      toast.success("Configuración guardada")
      apiGet<SystemInfo>("/settings/system-info").then(setInfo).catch(() => {})
    } catch (error) {
      toast.error("No se pudo guardar", { description: mensajeDeError(error) })
    } finally {
      setGuardando(false)
    }
  }

  if (cargando || !config) {
    return (
      <AppLayout permiso="configuracion">
        <Header title="Configuración" description="Ajustes del sistema de biblioteca" />
        <div className="p-6">
          <div className="rounded-lg border bg-card py-16 text-center text-muted-foreground">
            {cargando ? "Cargando configuración..." : "No se pudo cargar la configuración."}
          </div>
        </div>
      </AppLayout>
    )
  }

  const { institucion, politicas_prestamo: politicas } = config

  return (
    <AppLayout permiso="configuracion">
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
            titulo="Circulación"
            descripcion="Plazos, topes, renovaciones, multas, calendario y deudas"
          >
            <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
              <p className="max-w-xl text-sm text-muted-foreground">
                {politicas.dias_estudiante} días para estudiantes, {politicas.dias_docente} para
                docentes y {politicas.dias_personal} para el personal;{" "}
                {politicas.renovaciones_permitidas} renovación(es) y Bs.{" "}
                {politicas.multa_por_dia.toFixed(2)} de multa por día en la regla general. Las
                excepciones por tipo de ítem o sede, los feriados y el tope de deuda se ajustan
                en su pantalla.
              </p>
              <Button asChild variant="outline" className="shrink-0">
                <Link href="/configuracion/circulacion">
                  Reglas y calendario
                  <ArrowRight className="ml-2 h-4 w-4" />
                </Link>
              </Button>
            </div>
          </Seccion>

          <Seccion
            icono={MapPin}
            titulo="Sedes"
            descripcion="Bibliotecas de la institución y dónde se retiran reservas"
          >
            <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
              <p className="max-w-xl text-sm text-muted-foreground">
                Cada ejemplar pertenece a una sede y cada reserva se retira en una. Entre sedes,
                los ejemplares viajan con traslados.
              </p>
              <Button asChild variant="outline" className="shrink-0">
                <Link href="/configuracion/sedes">
                  Gestionar sedes
                  <ArrowRight className="ml-2 h-4 w-4" />
                </Link>
              </Button>
            </div>
          </Seccion>

          <Seccion
            icono={Bell}
            titulo="Avisos"
            descripcion="Correos a los lectores y tareas programadas"
          >
            <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
              <p className="max-w-xl text-sm text-muted-foreground">
                Recordatorios de vencimiento, préstamos vencidos, reservas listas y recuperación de
                contraseña. Aquí se editan las plantillas, cuándo se avisa y se ve la cola de correos.
              </p>
              <Button asChild variant="outline" className="shrink-0">
                <Link href="/configuracion/avisos">
                  Avisos y tareas
                  <ArrowRight className="ml-2 h-4 w-4" />
                </Link>
              </Button>
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
