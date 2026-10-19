"use client"

import { useCallback, useEffect, useState } from "react"
import Link from "next/link"
import { useParams, usePathname } from "next/navigation"
import { BookmarkPlus, ListPlus, Loader2 } from "lucide-react"

import { rutaDeEntrada, useLector, vinoDesdeElOpac } from "@/components/opac/lector-provider"
import { ListasDialog } from "@/components/opac/listas-dialog"
import { ReservarDialog } from "@/components/opac/reservar-dialog"
import { Disponibilidad } from "@/components/opac/titulo-resultado"
import { Button } from "@/components/ui/button"
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table"
import { ApiError, apiGet, mensajeDeError } from "@/lib/api"
import type { FichaPublica, ReservaLector } from "@/lib/opac"
import { cn } from "@/lib/utils"

export default function RegistroPage() {
  const { id } = useParams<{ id: string }>()
  const pathname = usePathname()
  const { lector } = useLector()
  const [ficha, setFicha] = useState<FichaPublica | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [miReserva, setMiReserva] = useState<ReservaLector | null>(null)
  const [reservando, setReservando] = useState(false)
  const [guardando, setGuardando] = useState(false)

  const cargar = useCallback(async () => {
    // Un enlace roto (/opac/registro/abc) no llega al backend: su 422 no es para el lector.
    if (!/^\d+$/.test(id)) {
      setError("Ese enlace no corresponde a ningún título del catálogo.")
      return
    }
    try {
      setFicha(await apiGet<FichaPublica>(`/opac/record/${id}`))
    } catch (e) {
      setError(e instanceof ApiError && e.status === 404
        ? "Ese título ya no está en el catálogo."
        : mensajeDeError(e))
    }
  }, [id])

  // El título del registro en la pestaña (y al compartir o guardar el enlace).
  useEffect(() => {
    if (ficha) document.title = `${ficha.titulo} · Catálogo en línea`
  }, [ficha])

  const cargarMiReserva = useCallback(async () => {
    if (!lector) return setMiReserva(null)
    const mias = await apiGet<ReservaLector[]>("/opac/account/holds").catch(() => [])
    setMiReserva(mias.find((r) => r.biblioId === id) ?? null)
  }, [lector, id])

  useEffect(() => {
    cargar()
  }, [cargar])

  useEffect(() => {
    cargarMiReserva()
  }, [cargarMiReserva])

  if (error) return <p role="alert" className="text-destructive">{error}</p>
  if (!ficha) return <Loader2 className="mx-auto mt-12 h-6 w-6 animate-spin text-muted-foreground" />

  const publicacion = [ficha.lugar, ficha.editorial, ficha.ano_publicacion].filter(Boolean)
  const datos: [string, React.ReactNode][] = [
    ["Edición", ficha.edicion],
    ["Publicación", publicacion.length ? publicacion.join(", ") : null],
    ["Descripción", ficha.descripcion_fisica],
    ["Serie", ficha.serie],
    ["ISBN", ficha.isbn],
    ["ISSN", ficha.issn],
    ["Periodicidad", ficha.periodicidad],
    ["Otros autores", ficha.otros_autores.length ? ficha.otros_autores.join("; ") : null],
  ]
  const conNumeracion = ficha.ejemplares_detalle.some((e) => e.numeracion)

  return (
    <article className="space-y-8">
      <nav className="text-sm">
        <Link href="/opac/buscar" className="text-muted-foreground hover:text-foreground hover:underline"
              onClick={(e) => {
                // Atrás solo si se llegó desde el propio catálogo: si no, saldría del sitio.
                if (vinoDesdeElOpac()) { e.preventDefault(); window.history.back() }
              }}>
          ← Volver a los resultados
        </Link>
      </nav>

      <header className="flex flex-col gap-6 lg:flex-row lg:items-start lg:justify-between">
        <div className="min-w-0 space-y-2">
          <h1 className="text-balance text-2xl font-semibold text-foreground sm:text-3xl">
            {ficha.titulo}
            {ficha.subtitulo && <span className="font-normal text-muted-foreground">: {ficha.subtitulo}</span>}
          </h1>
          {(ficha.autor || ficha.responsabilidad) && (
            <p className="text-lg text-muted-foreground">
              {ficha.autor ? (
                <Link href={`/opac/buscar?autor=${encodeURIComponent(ficha.autor)}`} className="hover:text-primary hover:underline">
                  {ficha.autor}
                </Link>
              ) : ficha.responsabilidad}
            </p>
          )}
          <Disponibilidad disponibles={ficha.disponibles} ejemplares={ficha.ejemplares} />
        </div>

        <div className="flex shrink-0 flex-col gap-2 sm:flex-row lg:flex-col">
          {miReserva ? (
            <div className="rounded-lg border border-primary/30 bg-primary/5 px-4 py-3 text-sm">
              <p className="font-medium text-primary">Ya lo reservaste</p>
              <p className="text-muted-foreground">
                {miReserva.status === "EnEspera" ? `Retíralo antes del ${miReserva.pickupBy}`
                  : miReserva.status === "EnTransito" ? "Va en camino a tu sede"
                  : `Turno ${miReserva.priority}`}
              </p>
            </div>
          ) : ficha.reservable ? (
            lector ? (
              <Button onClick={() => setReservando(true)}>
                <BookmarkPlus className="mr-2 h-4 w-4" /> Reservar
              </Button>
            ) : (
              <Button asChild>
                <Link href={rutaDeEntrada(pathname)}>
                  <BookmarkPlus className="mr-2 h-4 w-4" /> Entra para reservar
                </Link>
              </Button>
            )
          ) : ficha.ejemplares_detalle.length === 0 ? (
            <p className="text-sm text-muted-foreground">Todavía no hay ejemplares para reservar</p>
          ) : (
            <p className="text-sm text-muted-foreground">Solo para consulta en sala</p>
          )}
          {lector && (
            <Button variant="outline" onClick={() => setGuardando(true)}>
              <ListPlus className="mr-2 h-4 w-4" /> Guardar en una lista
            </Button>
          )}
          {ficha.reservas > 0 && !miReserva && (
            <p className="text-xs text-muted-foreground">
              {ficha.reservas} reserva{ficha.reservas === 1 ? "" : "s"} en espera
            </p>
          )}
        </div>
      </header>

      <div className="grid gap-8 lg:grid-cols-[1fr_18rem]">
        <div className="min-w-0 space-y-6">
          {ficha.resumen && <p className="max-w-prose text-pretty leading-relaxed text-foreground">{ficha.resumen}</p>}

          <dl className="grid gap-x-6 gap-y-2 text-sm sm:grid-cols-[10rem_1fr]">
            {datos.filter(([, v]) => v).map(([k, v]) => (
              <div key={k} className="contents">
                <dt className="text-muted-foreground">{k}</dt>
                <dd className="text-foreground">{v}</dd>
              </div>
            ))}
            {ficha.materias.length > 0 && (
              <div className="contents">
                <dt className="text-muted-foreground">Materias</dt>
                <dd className="flex flex-wrap gap-1.5">
                  {ficha.materias.map((m) => (
                    <Link key={m} href={`/opac/buscar?q=${encodeURIComponent(m)}`}
                          className="rounded-full border border-border px-2.5 py-0.5 text-xs hover:border-primary hover:text-primary">
                      {m}
                    </Link>
                  ))}
                </dd>
              </div>
            )}
          </dl>
          {ficha.notas.length > 0 && (
            <ul className="space-y-1 text-sm text-muted-foreground">
              {ficha.notas.map((n) => <li key={n}>{n}</li>)}
            </ul>
          )}
        </div>

        {ficha.por_sede.length > 0 && (
          <aside aria-label="Disponibilidad por sede" className="space-y-2">
            <h2 className="text-sm font-semibold uppercase tracking-wide text-muted-foreground">Por sede</h2>
            <ul className="divide-y divide-border rounded-lg border border-border bg-card">
              {ficha.por_sede.map((s) => (
                <li key={s.sede} className="flex items-center justify-between gap-3 px-4 py-2.5 text-sm">
                  <span className="min-w-0 text-foreground">{s.sede}</span>
                  <span className={cn("shrink-0 whitespace-nowrap tabular-nums", s.disponibles ? "font-medium text-primary" : "text-muted-foreground")}>
                    {s.disponibles} de {s.ejemplares}
                  </span>
                </li>
              ))}
            </ul>
          </aside>
        )}
      </div>

      <section aria-labelledby="ejemplares" className="space-y-3">
        <h2 id="ejemplares" className="text-lg font-semibold text-foreground">Ejemplares</h2>
        {ficha.ejemplares_detalle.length === 0 ? (
          <p className="text-sm text-muted-foreground">La biblioteca todavía no tiene ejemplares de este título.</p>
        ) : (
          <>
          {/* En el teléfono, una tarjeta por ejemplar: el estado no puede quedar fuera de la pantalla. */}
          <ul className="divide-y divide-border rounded-lg border border-border bg-card sm:hidden">
            {ficha.ejemplares_detalle.map((e) => (
              <li key={e.id} className="px-4 py-3 text-sm">
                <p className={e.disponible ? "font-medium text-primary" : "text-muted-foreground"}>{e.estado}</p>
                <p className="text-foreground">{e.sede}{e.numeracion && ` · ${e.numeracion}`}</p>
                <p className="text-xs text-muted-foreground">
                  {[e.signatura, e.tipo].filter(Boolean).join(" · ")}
                </p>
              </li>
            ))}
          </ul>
          <div className="hidden overflow-x-auto rounded-lg border border-border bg-card sm:block">
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Sede</TableHead>
                  <TableHead>Signatura</TableHead>
                  {conNumeracion && <TableHead>Número</TableHead>}
                  <TableHead>Tipo</TableHead>
                  <TableHead>Estado</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {ficha.ejemplares_detalle.map((e) => (
                  <TableRow key={e.id}>
                    <TableCell>{e.sede}</TableCell>
                    <TableCell className="font-mono text-xs">{e.signatura ?? "—"}</TableCell>
                    {conNumeracion && <TableCell>{e.numeracion ?? "—"}</TableCell>}
                    <TableCell>{e.tipo ?? "—"}</TableCell>
                    <TableCell className={e.disponible ? "font-medium text-primary" : "text-muted-foreground"}>
                      {e.estado}
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </div>
          </>
        )}
      </section>

      <ReservarDialog open={reservando} onOpenChange={setReservando} biblioId={ficha.id}
                      titulo={ficha.titulo} enCola={ficha.reservas}
                      onReservado={() => { cargar(); cargarMiReserva() }} />
      <ListasDialog open={guardando} onOpenChange={setGuardando} biblioId={ficha.id} titulo={ficha.titulo} />
    </article>
  )
}
