"use client"

import { Suspense, useCallback, useEffect, useState } from "react"
import Link from "next/link"
import { useParams, usePathname, useRouter, useSearchParams } from "next/navigation"
import { ArrowLeft, BookOpen, User, Calendar, MapPin, Tag, Hash, Pencil, Plus, Trash2 } from "lucide-react"
import { toast } from "sonner"

import { AppLayout } from "@/components/layout/app-layout"
import { Header } from "@/components/layout/header"
import { Button } from "@/components/ui/button"
import {
  AccionEjemplarDialog,
  AccionEjemplar,
} from "@/components/catalogo/accion-ejemplar-dialog"
import { AgregarEjemplarDialog } from "@/components/catalogo/agregar-ejemplar-dialog"
import { EditarEjemplarDialog } from "@/components/catalogo/editar-ejemplar-dialog"
import { EditorMarc } from "@/components/catalogo/editor-marc"
import { useSesion } from "@/components/auth/sesion-provider"
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
} from "@/components/ui/alert-dialog"
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs"
import { apiDelete, apiGet, apiPut, ApiError, mensajeDeError } from "@/lib/api"
import { cn } from "@/lib/utils"
import type { Book } from "@/components/catalogo/book-card"
import { useSedes } from "@/components/layout/sede-provider"
import type { Ejemplar, RegistroMarc, RegistroMarcGuardado, ReservaGestion } from "@/lib/types"

const estadoClases: Record<string, string> = {
  Disponible: "bg-primary/10 text-primary",
  Prestado: "bg-destructive/10 text-destructive",
  Reservado: "bg-accent/20 text-accent-foreground",
  EnTransito: "bg-secondary text-secondary-foreground",
  Perdido: "bg-destructive/10 text-destructive",
}

const ESTADO_EJEMPLAR: Record<string, string> = { EnTransito: "En tránsito" }

const ESTADO_RESERVA: Record<string, string> = {
  Pendiente: "En cola",
  EnTransito: "En tránsito",
  EnEspera: "Por retirar",
}

export default function FichaCatalogoPage() {
  // useSearchParams exige un límite de Suspense en el App Router.
  return (
    <Suspense fallback={null}>
      <FichaCatalogo />
    </Suspense>
  )
}

function FichaCatalogo() {
  const params = useParams<{ id: string }>()
  const router = useRouter()
  const pathname = usePathname()
  const searchParams = useSearchParams()
  const biblioId = params.id
  const { tienePermiso } = useSesion()
  const puedeCatalogar = tienePermiso("catalogo")
  const circula = tienePermiso("circulacion")
  const vista = searchParams.get("vista") === "marc" ? "marc" : "ficha"

  const [registroMarc, setRegistroMarc] = useState<RegistroMarcGuardado | null>(null)
  const [agregandoEjemplar, setAgregandoEjemplar] = useState(
    () => searchParams.get("ejemplar") === "nuevo"
  )
  const [aEliminar, setAEliminar] = useState(false)

  const [book, setBook] = useState<Book | null>(null)
  const [ejemplares, setEjemplares] = useState<Ejemplar[]>([])
  const [reservas, setReservas] = useState<ReservaGestion[]>([])
  const { sedes } = useSedes()
  const variasSedes = sedes.length > 1
  const [isLoading, setIsLoading] = useState(true)
  const [noEncontrado, setNoEncontrado] = useState(false)
  const [accion, setAccion] = useState<AccionEjemplar | null>(null)
  const [editando, setEditando] = useState<Ejemplar | null>(null)

  const cargar = useCallback(async () => {
    try {
      const [b, e, r] = await Promise.all([
        apiGet<Book>(`/catalog/items/${biblioId}`),
        apiGet<Ejemplar[]>(`/catalog/items/${biblioId}/ejemplares`),
        apiGet<ReservaGestion[]>(`/circulation/holds?biblio_id=${biblioId}`).catch(() => []),
      ])
      setBook(b)
      setEjemplares(e)
      setReservas(r)
    } catch (error) {
      if (error instanceof ApiError && error.status === 404) {
        setNoEncontrado(true)
      } else {
        toast.error("No se pudo cargar la ficha", { description: mensajeDeError(error) })
      }
    } finally {
      setIsLoading(false)
    }
  }, [biblioId])

  useEffect(() => {
    cargar()
  }, [cargar])

  useEffect(() => {
    if (vista !== "marc") return
    apiGet<RegistroMarcGuardado>(`/catalog/items/${biblioId}/marc`)
      .then(setRegistroMarc)
      .catch((e) => toast.error("No se pudo cargar el registro MARC", { description: mensajeDeError(e) }))
  }, [biblioId, vista])

  function cambiarVista(v: string) {
    router.replace(v === "marc" ? `${pathname}?vista=marc` : pathname, { scroll: false })
  }

  async function guardarMarc(plantilla: string, marc: RegistroMarc, permitirDuplicado: boolean) {
    const r = await apiPut<RegistroMarcGuardado>(`/catalog/items/${biblioId}/marc`, {
      plantilla,
      marc,
      permitir_duplicado: permitirDuplicado,
    })
    setRegistroMarc(r)
    toast.success("Registro guardado", { description: r.titulo })
    cargar()
  }

  async function eliminar() {
    setAEliminar(false)
    try {
      await apiDelete(`/catalog/items/${biblioId}`)
      toast.success("Registro eliminado")
      router.push("/catalogo")
    } catch (error) {
      toast.error("No se pudo eliminar el registro", { description: mensajeDeError(error) })
    }
  }

  if (isLoading) {
    return (
      <AppLayout>
        <Header title="Ficha bibliográfica" />
        <div className="p-6">
          <div className="rounded-lg border bg-card py-16 text-center text-muted-foreground">
            Cargando ficha...
          </div>
        </div>
      </AppLayout>
    )
  }

  if (noEncontrado || !book) {
    return (
      <AppLayout>
        <Header title="Ficha bibliográfica" />
        <div className="p-6">
          <div className="rounded-lg border border-dashed bg-card py-16 text-center">
            <p className="text-lg font-medium text-foreground">Título no encontrado</p>
            <p className="mb-4 text-sm text-muted-foreground">
              No existe ningún registro con el identificador {biblioId}.
            </p>
            <Button variant="outline" onClick={() => router.push("/catalogo")}>
              <ArrowLeft className="mr-2 h-4 w-4" />
              Volver al catálogo
            </Button>
          </div>
        </div>
      </AppLayout>
    )
  }

  const puedePrestar = book.available > 0 && Boolean(book.availableBarcode)

  return (
    <AppLayout>
      <Header title="Ficha bibliográfica" description={book.title} />

      <div className="p-6">
        <div className="mb-4 flex flex-wrap items-center justify-between gap-3">
          <Button variant="ghost" size="sm" onClick={() => router.push("/catalogo")}>
            <ArrowLeft className="mr-2 h-4 w-4" />
            Volver al catálogo
          </Button>
          {puedeCatalogar && book.copies === 0 && (
            <Button variant="ghost" size="sm" className="text-destructive" onClick={() => setAEliminar(true)}>
              <Trash2 className="mr-2 h-4 w-4" />
              Eliminar registro
            </Button>
          )}
        </div>

        <Tabs value={vista} onValueChange={cambiarVista}>
          <TabsList className="mb-4">
            <TabsTrigger value="ficha">Ficha</TabsTrigger>
            <TabsTrigger value="marc">Registro MARC</TabsTrigger>
          </TabsList>

          <TabsContent value="marc">
            {registroMarc ? (
              <EditorMarc
                key={`${registroMarc.id}-${registroMarc.plantilla}`}
                plantillaInicial={registroMarc.plantilla}
                marcInicial={registroMarc.marc}
                soloLectura={!puedeCatalogar}
                textoBoton="Guardar registro"
                onGuardar={guardarMarc}
              />
            ) : (
              <div className="rounded-lg border bg-card py-12 text-center text-muted-foreground">
                Cargando registro MARC…
              </div>
            )}
          </TabsContent>

          <TabsContent value="ficha">

            <div className="mb-6 rounded-lg border border-border bg-card p-6">
              <div className="flex flex-col gap-6 sm:flex-row">
                <div className="flex h-40 w-32 shrink-0 items-center justify-center rounded-lg bg-primary/5">
                  <BookOpen className="h-16 w-16 text-primary/40" />
                </div>

                <div className="flex-1">
                  <h2 className="text-2xl font-semibold text-foreground">{book.title}</h2>

                  <div className="mt-3 grid gap-2 text-sm text-muted-foreground sm:grid-cols-2">
                    <span className="flex items-center gap-2">
                      <User className="h-4 w-4" />
                      {book.author}
                    </span>
                    {book.year && (
                      <span className="flex items-center gap-2">
                        <Calendar className="h-4 w-4" />
                        {book.year}
                      </span>
                    )}
                    <span className="flex items-center gap-2">
                      <Tag className="h-4 w-4" />
                      {book.category}
                    </span>
                    <span className="flex items-center gap-2">
                      <Hash className="h-4 w-4" />
                      ISBN {book.isbn}
                    </span>
                    {book.location && (
                      <span className="flex items-center gap-2">
                        <MapPin className="h-4 w-4" />
                        {book.location}
                      </span>
                    )}
                    <span className="flex items-center gap-2">
                      <BookOpen className="h-4 w-4" />
                      {book.type}
                    </span>
                  </div>

                  <div className="mt-5 flex items-center gap-3">
                    <span
                      className={cn(
                        "rounded-full px-3 py-1 text-sm font-medium",
                        book.available > 0
                          ? "bg-primary/10 text-primary"
                          : "bg-destructive/10 text-destructive"
                      )}
                    >
                      {book.available} de {book.copies} ejemplar(es) disponible(s)
                    </span>
                    {circula && puedePrestar && <Button onClick={() => setAccion("prestar")}>Prestar</Button>}
                    {circula && (
                      <Button variant="outline" onClick={() => setAccion("reservar")}>
                        Reservar
                      </Button>
                    )}
                    {reservas.length > 0 && (
                      <span className="text-sm text-muted-foreground">
                        {reservas.length} reserva(s) activa(s)
                      </span>
                    )}
                  </div>
                </div>
              </div>
            </div>

            <div className="rounded-lg border border-border bg-card">
              <div className="flex items-center justify-between gap-3 border-b border-border px-6 py-4">
                <div>
                  <h3 className="font-semibold text-foreground">Ejemplares</h3>
                  <p className="text-sm text-muted-foreground">
                    Estado individual de cada copia física
                  </p>
                </div>
                {puedeCatalogar && (
                  <Button variant="outline" size="sm" onClick={() => setAgregandoEjemplar(true)}>
                    <Plus className="mr-2 h-4 w-4" />
                    Agregar ejemplar
                  </Button>
                )}
              </div>
              {ejemplares.length === 0 && (
                <p className="px-6 py-8 text-center text-sm text-muted-foreground">
                  Este registro todavía no tiene ejemplares.
                </p>
              )}

              <div className="overflow-x-auto">
                <table className="w-full">
                  <thead>
                    <tr className="border-b border-border bg-muted/50">
                      <th className="px-4 py-3 text-left text-sm font-medium text-muted-foreground">Código de barras</th>
                      <th className="px-4 py-3 text-left text-sm font-medium text-muted-foreground">Signatura</th>
                      {variasSedes && (
                        <th className="px-4 py-3 text-left text-sm font-medium text-muted-foreground">Sede</th>
                      )}
                      <th className="px-4 py-3 text-left text-sm font-medium text-muted-foreground">Estado</th>
                      <th className="px-4 py-3 text-left text-sm font-medium text-muted-foreground">Prestado a</th>
                      {puedeCatalogar && <th className="w-12 px-2 py-3"><span className="sr-only">Acciones</span></th>}
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-border">
                    {ejemplares.map((e) => (
                      <tr key={e.id} className="hover:bg-muted/30">
                        <td className="px-4 py-4 font-medium text-foreground">{e.barcode}</td>
                        <td className="px-4 py-4 text-sm text-muted-foreground">
                          {e.enumeration && <p className="font-medium text-foreground">{e.enumeration}</p>}
                          {e.location || (e.enumeration ? null : "—")}
                        </td>
                        {variasSedes && (
                          <td className="px-4 py-4 text-sm">
                            <p className="text-foreground">{e.branch ?? "—"}</p>
                            {e.homeBranch && e.homeBranch !== e.branch && (
                              <p className="text-xs text-muted-foreground">Pertenece a {e.homeBranch}</p>
                            )}
                          </td>
                        )}
                        <td className="px-4 py-4">
                          <span
                            className={cn(
                              "inline-flex rounded-full px-2.5 py-1 text-xs font-medium",
                              estadoClases[e.status] || "bg-muted text-muted-foreground"
                            )}
                          >
                            {ESTADO_EJEMPLAR[e.status] ?? e.status}
                          </span>
                          {e.transitTo && (
                            <p className="mt-1 text-xs text-muted-foreground">Hacia {e.transitTo}</p>
                          )}
                        </td>
                        <td className="px-4 py-4 text-sm">
                          {e.borrowedBy ? (
                            <div>
                              <p className="text-foreground">{e.borrowedBy}</p>
                              {e.dueDate && (
                                <p className="text-xs text-muted-foreground">Vence: {e.dueDate}</p>
                              )}
                            </div>
                          ) : (
                            <span className="text-muted-foreground">—</span>
                          )}
                        </td>
                        {puedeCatalogar && (
                          <td className="px-2 py-4 text-right">
                            <Button variant="ghost" size="icon" aria-label={`Editar ${e.barcode}`}
                                    onClick={() => setEditando(e)}>
                              <Pencil className="h-4 w-4" />
                            </Button>
                          </td>
                        )}
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>

            {reservas.length > 0 && (
              <div className="mt-6 rounded-lg border border-border bg-card">
                <div className="flex items-center justify-between gap-3 border-b border-border px-6 py-4">
                  <div>
                    <h3 className="font-semibold text-foreground">Reservas</h3>
                    <p className="text-sm text-muted-foreground">Quiénes esperan este título, en orden</p>
                  </div>
                  <Button variant="outline" size="sm" asChild>
                    <Link href="/circulacion/reservas?vista=cola">Gestionar</Link>
                  </Button>
                </div>
                <ol className="divide-y divide-border">
                  {reservas.map((r) => (
                    <li key={r.id} className="flex items-center gap-4 px-6 py-3 text-sm">
                      <span className="w-6 text-center font-semibold tabular-nums text-muted-foreground">
                        {r.status === "Pendiente" ? r.priority : "·"}
                      </span>
                      <div className="min-w-0 flex-1">
                        <p className="font-medium text-foreground">{r.userName}</p>
                        <p className="text-xs text-muted-foreground">
                          {r.userId} · desde el {r.reservedOn}
                          {variasSedes && r.pickupBranch ? ` · retira en ${r.pickupBranch}` : ""}
                        </p>
                      </div>
                      {r.suspended && <span className="text-xs text-muted-foreground">Suspendida</span>}
                      <span
                        className={cn(
                          "rounded-full px-2.5 py-1 text-xs font-medium",
                          r.status === "EnEspera" ? "bg-accent/20 text-accent-foreground" : "bg-muted text-muted-foreground",
                        )}
                      >
                        {ESTADO_RESERVA[r.status] ?? r.status}
                        {r.status === "EnEspera" && r.pickupBy ? ` hasta el ${r.pickupBy}` : ""}
                      </span>
                    </li>
                  ))}
                </ol>
              </div>
            )}
          </TabsContent>
        </Tabs>
      </div>

      <AgregarEjemplarDialog
        biblioId={book.id}
        titulo={book.title}
        open={agregandoEjemplar}
        onOpenChange={setAgregandoEjemplar}
        onSuccess={cargar}
      />

      <AlertDialog open={aEliminar} onOpenChange={setAEliminar}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>¿Eliminar este registro?</AlertDialogTitle>
            <AlertDialogDescription>
              <strong>{book.title}</strong> no tiene ejemplares. El registro bibliográfico se
              borrará del catálogo y no se puede deshacer.
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel>Cancelar</AlertDialogCancel>
            <AlertDialogAction onClick={eliminar}
                               className="bg-destructive text-destructive-foreground hover:bg-destructive/90">
              Eliminar registro
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>

      <EditarEjemplarDialog
        biblioId={book.id}
        ejemplar={editando}
        onClose={() => setEditando(null)}
        onSuccess={cargar}
      />

      <AccionEjemplarDialog
        accion={accion}
        titulo={book.title}
        biblioId={book.id}
        codigoBarras={book.availableBarcode}
        onClose={() => setAccion(null)}
        onSuccess={cargar}
      />
    </AppLayout>
  )
}
