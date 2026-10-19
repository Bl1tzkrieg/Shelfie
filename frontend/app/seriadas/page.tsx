"use client"

import { Suspense, useCallback, useEffect, useMemo, useState } from "react"
import Link from "next/link"
import { usePathname, useRouter, useSearchParams } from "next/navigation"
import { Loader2, Mail, PackageCheck, Plus } from "lucide-react"
import { toast } from "sonner"

import { AppLayout } from "@/components/layout/app-layout"
import { Header } from "@/components/layout/header"
import { EstadoFasciculoBadge, fechaIso } from "@/components/seriadas/comun"
import { RecibirFasciculoDialog } from "@/components/seriadas/recibir-fasciculo-dialog"
import { NuevaSuscripcionDialog } from "@/components/seriadas/suscripcion-dialog"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs"
import { apiGet, apiPost, mensajeDeError } from "@/lib/api"
import type { Fasciculo, Suscripcion } from "@/lib/types"

type Vista = "suscripciones" | "recepcion" | "reclamos"
const VISTAS: Vista[] = ["suscripciones", "recepcion", "reclamos"]

export default function SeriadasPage() {
  return (
    <AppLayout permiso="seriadas">
      <Header title="Publicaciones seriadas" description="Suscripciones, recepción de fascículos y reclamos" />
      <Suspense fallback={null}>
        <Contenido />
      </Suspense>
    </AppLayout>
  )
}

function Vacio({ children }: { children: React.ReactNode }) {
  return <div className="rounded-lg border border-dashed bg-card py-12 text-center text-sm text-muted-foreground">{children}</div>
}

function Contenido() {
  const router = useRouter()
  const pathname = usePathname()
  const params = useSearchParams()
  const pedida = params.get("vista") as Vista | null
  const vista: Vista = pedida && VISTAS.includes(pedida) ? pedida : "suscripciones"

  const [suscripciones, setSuscripciones] = useState<Suscripcion[] | null>(null)
  const [esperados, setEsperados] = useState<Fasciculo[]>([])
  const [atrasados, setAtrasados] = useState<Fasciculo[]>([])
  const [soloActivas, setSoloActivas] = useState(true)
  const [nueva, setNueva] = useState(false)
  const [recibiendo, setRecibiendo] = useState<Fasciculo | null>(null)

  const cargar = useCallback(async () => {
    try {
      const [s, e, a] = await Promise.all([
        apiGet<Suscripcion[]>(`/serials/subscriptions${soloActivas ? "?estado=Activa" : ""}`),
        apiGet<Fasciculo[]>("/serials/issues/expected"),
        apiGet<Fasciculo[]>("/serials/issues/late"),
      ])
      setSuscripciones(s)
      setEsperados(e)
      setAtrasados(a)
    } catch (error) {
      toast.error("No se pudieron cargar las seriadas", { description: mensajeDeError(error) })
    }
  }, [soloActivas])

  useEffect(() => {
    cargar()
  }, [cargar])

  const crearEjemplares = useMemo(
    () => new Map((suscripciones ?? []).map((s) => [s.id, s.crear_ejemplares])),
    [suscripciones],
  )

  async function accion(ruta: string, aviso: string) {
    try {
      await apiPost(ruta, {})
      toast.success(aviso)
      cargar()
    } catch (error) {
      toast.error("No se pudo completar", { description: mensajeDeError(error) })
    }
  }

  // Reclamos agrupados por proveedor: un correo por proveedor y título.
  const porProveedor = useMemo(() => {
    const grupos = new Map<string, Fasciculo[]>()
    for (const f of atrasados) {
      const clave = f.proveedor_nombre ?? "Sin proveedor"
      grupos.set(clave, [...(grupos.get(clave) ?? []), f])
    }
    return [...grupos.entries()]
  }, [atrasados])

  return (
    <div className="p-6">
      <Tabs value={vista} onValueChange={(v) => router.replace(`${pathname}?vista=${v}`, { scroll: false })}>
        <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
          <TabsList>
            <TabsTrigger value="suscripciones">Suscripciones</TabsTrigger>
            <TabsTrigger value="recepcion">
              Por recibir {esperados.length > 0 && <span className="ml-1.5 rounded-full bg-muted-foreground/15 px-1.5 text-xs">{esperados.length}</span>}
            </TabsTrigger>
            <TabsTrigger value="reclamos">
              Atrasados {atrasados.length > 0 && <span className="ml-1.5 rounded-full bg-destructive px-1.5 text-xs text-destructive-foreground">{atrasados.length}</span>}
            </TabsTrigger>
          </TabsList>
          <Button onClick={() => setNueva(true)}>
            <Plus className="mr-2 h-4 w-4" />
            Nueva suscripción
          </Button>
        </div>

        <TabsContent value="suscripciones" className="mt-6 space-y-4">
          <div className="flex gap-1.5" role="group" aria-label="Filtrar suscripciones">
            <Button size="sm" variant={soloActivas ? "default" : "outline"} aria-pressed={soloActivas} onClick={() => setSoloActivas(true)}>Activas</Button>
            <Button size="sm" variant={!soloActivas ? "default" : "outline"} aria-pressed={!soloActivas} onClick={() => setSoloActivas(false)}>Todas</Button>
          </div>
          {suscripciones === null ? (
            <div className="py-12 text-center text-muted-foreground"><Loader2 className="mx-auto h-5 w-5 animate-spin" /></div>
          ) : suscripciones.length === 0 ? (
            <Vacio>No hay suscripciones {soloActivas ? "activas" : ""}.</Vacio>
          ) : (
            <div className="overflow-x-auto rounded-lg border bg-card">
              <table className="w-full text-sm">
                <thead className="bg-muted/50 text-left text-muted-foreground">
                  <tr>
                    <th className="px-4 py-3 font-medium">Publicación</th>
                    <th className="px-4 py-3 font-medium">Periodicidad</th>
                    <th className="px-4 py-3 font-medium">Próximo número</th>
                    <th className="px-4 py-3 text-right font-medium">Recibidos</th>
                    <th className="px-4 py-3 font-medium">Estado</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-border">
                  {suscripciones.map((s) => (
                    <tr key={s.id} className="hover:bg-muted/30">
                      <td className="px-4 py-3">
                        <Link href={`/seriadas/${s.id}`} className="font-medium text-foreground hover:underline">{s.titulo}</Link>
                        <p className="text-xs text-muted-foreground">
                          {[s.issn && `ISSN ${s.issn}`, s.proveedor_nombre].filter(Boolean).join(" · ") || "—"}
                        </p>
                      </td>
                      <td className="px-4 py-3">{s.periodicidad}</td>
                      <td className="px-4 py-3">
                        {s.proximo ? (
                          <>
                            <p>{s.proximo.numero}</p>
                            <p className="text-xs text-muted-foreground">{fechaIso(s.proximo.fecha_esperada)}</p>
                          </>
                        ) : "—"}
                      </td>
                      <td className="px-4 py-3 text-right tabular-nums">{s.fasciculos_recibidos}</td>
                      <td className="px-4 py-3">
                        <div className="flex flex-wrap gap-1">
                          <Badge variant={s.estado === "Activa" ? "secondary" : "outline"}>{s.estado}</Badge>
                          {s.fasciculos_atrasados > 0 && <Badge variant="destructive">{s.fasciculos_atrasados} atrasado(s)</Badge>}
                          {s.por_vencer && <Badge variant="outline">Por renovar</Badge>}
                        </div>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </TabsContent>

        <TabsContent value="recepcion" className="mt-6">
          {esperados.length === 0 ? (
            <Vacio>No se espera ningún número.</Vacio>
          ) : (
            <div className="divide-y divide-border rounded-lg border bg-card">
              {esperados.map((f) => (
                <div key={f.id} className="flex flex-col gap-2 px-4 py-3 sm:flex-row sm:items-center sm:justify-between">
                  <div>
                    <Link href={`/seriadas/${f.suscripcion_id}`} className="font-medium text-foreground hover:underline">{f.titulo}</Link>
                    <p className="text-sm">
                      {f.numero} <span className="text-muted-foreground">· esperado el {fechaIso(f.fecha_esperada)}</span>
                    </p>
                  </div>
                  <div className="flex items-center gap-2">
                    <EstadoFasciculoBadge estado={f.estado} atraso={f.dias_atraso} />
                    <Button size="sm" onClick={() => setRecibiendo(f)} aria-label={`Recibir ${f.titulo} ${f.numero}`}>
                      <PackageCheck className="mr-2 h-4 w-4" />
                      Recibir
                    </Button>
                  </div>
                </div>
              ))}
            </div>
          )}
        </TabsContent>

        <TabsContent value="reclamos" className="mt-6 space-y-4">
          {porProveedor.length === 0 ? (
            <Vacio>Nada atrasado: todo llegó dentro de los días de gracia.</Vacio>
          ) : (
            porProveedor.map(([proveedor, lista]) => (
              <section key={proveedor} className="rounded-lg border bg-card">
                <div className="flex items-center justify-between border-b px-4 py-3">
                  <h3 className="font-semibold text-foreground">{proveedor}</h3>
                  {lista[0].proveedor_email && lista[0].proveedor_id && (
                    <Button size="sm" variant="outline"
                            onClick={() => accion(`/serials/suppliers/${lista[0].proveedor_id}/claim`,
                                                  `Reclamo enviado a ${lista[0].proveedor_email}`)}>
                      <Mail className="mr-2 h-4 w-4" />
                      Reclamar todo por correo
                    </Button>
                  )}
                </div>
                <ul className="divide-y divide-border">
                  {lista.map((f) => (
                    <li key={f.id} className="flex flex-col gap-2 px-4 py-3 sm:flex-row sm:items-center sm:justify-between">
                      <div>
                        <p className="font-medium text-foreground">{f.titulo} · {f.numero}</p>
                        <p className="text-xs text-muted-foreground">
                          Esperado el {fechaIso(f.fecha_esperada)}
                          {f.reclamos > 0 && ` · reclamado ${f.reclamos} vez/veces, la última el ${f.fecha_reclamo}`}
                        </p>
                      </div>
                      <div className="flex items-center gap-2">
                        <EstadoFasciculoBadge estado={f.estado} atraso={f.dias_atraso} />
                        <Button size="sm" variant="outline" onClick={() => accion(`/serials/issues/${f.id}/claim`, "Reclamo registrado")}>
                          Marcar reclamado
                        </Button>
                        <Button size="sm" variant="ghost" onClick={() => accion(`/serials/issues/${f.id}/missing`, "Marcado como faltante")}>
                          Faltante
                        </Button>
                      </div>
                    </li>
                  ))}
                </ul>
              </section>
            ))
          )}
        </TabsContent>
      </Tabs>

      <NuevaSuscripcionDialog open={nueva} onOpenChange={setNueva} />
      <RecibirFasciculoDialog
        fasciculo={recibiendo}
        titulo={recibiendo?.titulo ?? ""}
        crearEjemplar={recibiendo ? crearEjemplares.get(recibiendo.suscripcion_id) ?? true : true}
        onOpenChange={(v) => !v && setRecibiendo(null)}
        onRecibido={() => {
          setRecibiendo(null)
          cargar()
        }}
      />
    </div>
  )
}
