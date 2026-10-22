"use client"

import { useEffect, useState } from "react"
import Link from "next/link"
import { usePathname, useRouter, useSearchParams } from "next/navigation"
import { ChevronLeft, ChevronRight, Download, Eye, Loader2, Pencil, Plus, Search, Trash2, Upload } from "lucide-react"
import { toast } from "sonner"

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
import { Button } from "@/components/ui/button"
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu"
import { Input } from "@/components/ui/input"
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table"
import { apiDelete, apiDownload, apiGet, mensajeDeError } from "@/lib/api"
import type { FilaLibro, PaginaLibros } from "@/lib/types"

const PAUSA_FILTRO_MS = 300

const EXPORTACIONES = [
  { nombre: "MARC (.mrc)", ruta: "/catalog/export?formato=marc", archivo: "catalogo.mrc" },
  { nombre: "MARCXML (.xml)", ruta: "/catalog/export?formato=marcxml", archivo: "catalogo.xml" },
  { nombre: "CSV (.csv)", ruta: "/catalog/export.csv", archivo: "catalogo.csv" },
] as const

function textoBorrado(fila: FilaLibro): string {
  const n = fila.ejemplares
  const ejemplares = n === 0 ? "" : n === 1 ? " y su ejemplar" : ` y sus ${n} ejemplares`
  return `¿Borrar «${fila.titulo}»${ejemplares}? No se puede deshacer.`
}

/** Botones de la cabecera de Libros: nuevo, importar y exportar. */
export function AccionesLibros({ onImportar }: { onImportar: () => void }) {
  const [exportando, setExportando] = useState(false)

  async function exportar(ruta: string, archivo: string) {
    setExportando(true)
    try {
      await apiDownload(ruta, archivo)
    } catch (error) {
      toast.error("No se pudo exportar", { description: mensajeDeError(error) })
    } finally {
      setExportando(false)
    }
  }

  return (
    <>
      <Button asChild size="sm">
        <Link href="/ingreso/">
          <Plus /> <span className="hidden sm:inline">Nuevo libro</span>
          <span className="sm:hidden">Nuevo</span>
        </Link>
      </Button>
      <Button size="sm" variant="outline" onClick={onImportar} aria-label="Importar MARC">
        <Upload /> <span className="hidden sm:inline">Importar MARC</span>
      </Button>
      <DropdownMenu>
        <DropdownMenuTrigger asChild>
          <Button size="sm" variant="outline" disabled={exportando} aria-label="Exportar">
            {exportando ? <Loader2 className="animate-spin" /> : <Download />}
            <span className="hidden sm:inline">Exportar</span>
          </Button>
        </DropdownMenuTrigger>
        <DropdownMenuContent align="end">
          {EXPORTACIONES.map((e) => (
            <DropdownMenuItem key={e.archivo} onSelect={() => exportar(e.ruta, e.archivo)}>
              {e.nombre}
            </DropdownMenuItem>
          ))}
        </DropdownMenuContent>
      </DropdownMenu>
    </>
  )
}

type Respuesta = { clave: string; datos: PaginaLibros | null; error: string | null }

/** Los libros en el orden del estante, con filtro (?q=) y páginas de 50 (?pagina=). */
export function ListaLibros({ recarga }: { recarga: number }) {
  const router = useRouter()
  const pathname = usePathname()
  const params = useSearchParams()
  const q = params.get("q") ?? ""
  const pagina = Math.max(1, Number(params.get("pagina")) || 1)

  const [filtro, setFiltro] = useState(q)
  const [respuesta, setRespuesta] = useState<Respuesta | null>(null)
  const [aBorrar, setABorrar] = useState<FilaLibro | null>(null)
  const [borrados, setBorrados] = useState(0)

  const clave = `${q}|${pagina}|${recarga}|${borrados}`
  const cargando = respuesta?.clave !== clave

  function irA(nuevoQ: string, nuevaPagina: number) {
    const p = new URLSearchParams()
    if (nuevoQ) p.set("q", nuevoQ)
    if (nuevaPagina > 1) p.set("pagina", String(nuevaPagina))
    const busqueda = p.toString()
    router.replace(busqueda ? `${pathname}?${busqueda}` : pathname, { scroll: false })
  }

  // El filtro se aplica tras una pausa corta; cambiarlo vuelve a la primera página.
  useEffect(() => {
    const limpio = filtro.trim()
    if (limpio === q) return
    const t = setTimeout(() => irA(limpio, 1), PAUSA_FILTRO_MS)
    return () => clearTimeout(t)
    // irA depende de router y pathname, estables durante la vida de la lista.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [filtro, q])

  useEffect(() => {
    let vigente = true
    const p = new URLSearchParams({ pagina: String(pagina) })
    if (q) p.set("q", q)
    apiGet<PaginaLibros>(`/books?${p}`)
      .then((datos) => vigente && setRespuesta({ clave, datos, error: null }))
      .catch((error) => vigente && setRespuesta({ clave, datos: null, error: mensajeDeError(error) }))
    return () => {
      vigente = false
    }
  }, [clave, q, pagina])

  async function borrar(fila: FilaLibro) {
    setABorrar(null)
    try {
      await apiDelete(`/books/${fila.id}`)
      toast.success(`Borrado: ${fila.titulo}`)
      setBorrados((n) => n + 1)
    } catch (error) {
      toast.error("No se pudo borrar el libro", { description: mensajeDeError(error) })
    }
  }

  const datos = respuesta?.datos ?? null

  return (
    <div className="space-y-4">
      <div className="relative max-w-md">
        <Search className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" aria-hidden />
        <Input
          type="search"
          aria-label="Filtrar por título, autor o cota"
          placeholder="Filtrar por título, autor o cota"
          value={filtro}
          onChange={(e) => setFiltro(e.target.value)}
          className="pl-9"
        />
      </div>

      {respuesta?.error && !cargando ? (
        <p role="alert" className="rounded-lg border border-destructive/40 bg-destructive/5 p-4 text-sm text-destructive">
          No se pudo cargar la lista: {respuesta.error}
        </p>
      ) : (
        <div className="rounded-xl border border-border/80 bg-card shadow-papel">
          <Table aria-busy={cargando}>
            <TableHeader>
              <TableRow>
                <TableHead className="w-40">Cota</TableHead>
                <TableHead>Título</TableHead>
                <TableHead className="hidden md:table-cell">Autor</TableHead>
                <TableHead className="hidden w-16 sm:table-cell">Año</TableHead>
                <TableHead className="hidden w-12 text-right sm:table-cell">Ej.</TableHead>
                <TableHead className="w-28 text-right">
                  <span className="sr-only">Acciones</span>
                </TableHead>
              </TableRow>
            </TableHeader>
            <TableBody className={cargando && datos ? "opacity-60" : undefined}>
              {datos?.resultados.map((f) => (
                <TableRow key={f.id}>
                  <TableCell className="whitespace-normal font-mono">
                    {f.cota ?? <span className="font-sans text-muted-foreground">Sin cota</span>}
                  </TableCell>
                  <TableCell className="whitespace-normal">
                    <span className="font-medium text-foreground">{f.titulo || "Sin título"}</span>
                    {f.autor && <span className="block text-sm text-muted-foreground md:hidden">{f.autor}</span>}
                  </TableCell>
                  <TableCell className="hidden whitespace-normal md:table-cell">{f.autor ?? ""}</TableCell>
                  <TableCell className="hidden tabular-nums sm:table-cell">{f.ano ?? ""}</TableCell>
                  <TableCell className="hidden text-right tabular-nums sm:table-cell">{f.ejemplares}</TableCell>
                  <TableCell className="text-right">
                    <div className="flex justify-end gap-0.5">
                      <Button asChild size="icon-sm" variant="ghost">
                        <Link href={`/ingreso/?id=${f.id}`} aria-label={`Editar «${f.titulo}»`} title="Editar">
                          <Pencil />
                        </Link>
                      </Button>
                      <Button asChild size="icon-sm" variant="ghost">
                        <Link href={`/libro/?id=${f.id}`} aria-label={`Ver «${f.titulo}»`} title="Ver">
                          <Eye />
                        </Link>
                      </Button>
                      <Button size="icon-sm" variant="ghost" title="Borrar"
                              aria-label={`Borrar «${f.titulo}»`}
                              className="text-destructive hover:text-destructive"
                              onClick={() => setABorrar(f)}>
                        <Trash2 />
                      </Button>
                    </div>
                  </TableCell>
                </TableRow>
              ))}
              {!datos && cargando && (
                <TableRow>
                  <TableCell colSpan={6} className="py-10 text-center text-muted-foreground">
                    <Loader2 className="mr-2 inline h-4 w-4 animate-spin" /> Cargando…
                  </TableCell>
                </TableRow>
              )}
              {datos && datos.resultados.length === 0 && (
                <TableRow>
                  <TableCell colSpan={6} className="whitespace-normal py-10 text-center text-muted-foreground">
                    {q
                      ? `Ningún libro coincide con «${q}».`
                      : "Todavía no hay libros. Empieza con «Nuevo libro» o importa un archivo MARC."}
                  </TableCell>
                </TableRow>
              )}
            </TableBody>
          </Table>
        </div>
      )}

      {datos && datos.total > 0 && (
        <nav aria-label="Páginas" className="flex flex-wrap items-center justify-between gap-3 text-sm text-muted-foreground">
          <span>
            {datos.total === 1 ? "1 libro" : `${datos.total} libros`} · página {datos.pagina} de {datos.paginas}
          </span>
          {datos.paginas > 1 && (
            <div className="flex gap-2">
              <Button variant="outline" size="sm" disabled={pagina <= 1} onClick={() => irA(q, pagina - 1)}>
                <ChevronLeft /> Anterior
              </Button>
              <Button variant="outline" size="sm" disabled={pagina >= datos.paginas}
                      onClick={() => irA(q, pagina + 1)}>
                Siguiente <ChevronRight />
              </Button>
            </div>
          )}
        </nav>
      )}

      <AlertDialog open={aBorrar !== null} onOpenChange={(abierto) => !abierto && setABorrar(null)}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>Borrar libro</AlertDialogTitle>
            <AlertDialogDescription>{aBorrar ? textoBorrado(aBorrar) : ""}</AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel>Cancelar</AlertDialogCancel>
            <AlertDialogAction
              className="bg-destructive text-white hover:bg-destructive/90"
              onClick={() => aBorrar && borrar(aBorrar)}
            >
              Borrar
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </div>
  )
}
