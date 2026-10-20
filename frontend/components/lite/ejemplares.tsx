"use client"

import { useState } from "react"
import { Check, Loader2, Pencil, Plus, Trash2, X } from "lucide-react"
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
import { Input } from "@/components/ui/input"
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table"
import { ApiError, apiDelete, apiPatch, apiPost, mensajeDeError } from "@/lib/api"
import type { EjemplarLibro, LibroCatalogo } from "@/lib/types"

type Borrador = { cota: string; numero_copia: string; codigo_barras: string; nota: string }
type CampoEjemplar = keyof Borrador

const BORRADOR_VACIO: Borrador = { cota: "", numero_copia: "", codigo_barras: "", nota: "" }
/** Los mismos topes que la API (schemas.EjemplarRequest). */
const LARGO_MAXIMO: Record<keyof Borrador, number> = {
  cota: 100, numero_copia: 20, codigo_barras: 50, nota: 9000,
}

function borradorDe(e: EjemplarLibro): Borrador {
  return {
    cota: e.cota ?? "",
    numero_copia: e.numero_copia ?? "",
    codigo_barras: e.codigo_barras ?? "",
    nota: e.nota ?? "",
  }
}

function nombreEjemplar(e: EjemplarLibro) {
  const partes = [e.numero_copia, e.codigo_barras].filter(Boolean)
  return partes.length ? partes.join(" · ") : "sin número"
}

interface EjemplaresProps {
  libroId: number
  cotaLibro: string
  ejemplares: EjemplarLibro[]
  onCambio: (ejemplares: EjemplarLibro[]) => void
}

/** Las copias del libro: agregar, corregir en la misma fila o quitar con confirmación. */
export function Ejemplares({ libroId, cotaLibro, ejemplares, onCambio }: EjemplaresProps) {
  // "nuevo" = la fila de alta; un número = el ejemplar que se está corrigiendo.
  const [editando, setEditando] = useState<number | "nuevo" | null>(null)
  const [borrador, setBorrador] = useState<Borrador>(BORRADOR_VACIO)
  const [errorCodigo, setErrorCodigo] = useState<string | null>(null)
  const [guardando, setGuardando] = useState(false)
  const [aQuitar, setAQuitar] = useState<EjemplarLibro | null>(null)

  function empezar(objetivo: number | "nuevo", inicial: Borrador) {
    setEditando(objetivo)
    setBorrador(inicial)
    setErrorCodigo(null)
  }

  function cancelar() {
    setEditando(null)
    setErrorCodigo(null)
  }

  async function guardar() {
    if (editando === null || guardando) return
    setGuardando(true)
    try {
      let r: LibroCatalogo
      if (editando === "nuevo") {
        // Lo vacío no se envía: el backend pone la cota del libro y la copia siguiente.
        const cuerpo = Object.fromEntries(
          Object.entries(borrador).map(([k, v]) => [k, v.trim()]).filter(([, v]) => v),
        )
        r = await apiPost<LibroCatalogo>(`/books/${libroId}/copies`, cuerpo)
        toast.success("Ejemplar agregado")
      } else {
        r = await apiPatch<LibroCatalogo>(`/books/${libroId}/copies/${editando}`, borrador)
        toast.success("Ejemplar corregido")
      }
      onCambio(r.ejemplares)
      setEditando(null)
    } catch (error) {
      if (error instanceof ApiError && error.status === 409) {
        setErrorCodigo(error.message)
      }
      toast.error("No se pudo guardar el ejemplar", { description: mensajeDeError(error) })
    } finally {
      setGuardando(false)
    }
  }

  async function quitar(ejemplar: EjemplarLibro) {
    setAQuitar(null)
    try {
      await apiDelete(`/books/${libroId}/copies/${ejemplar.id}`)
      onCambio(ejemplares.filter((e) => e.id !== ejemplar.id))
      if (editando === ejemplar.id) setEditando(null)
      toast.success("Ejemplar quitado")
    } catch (error) {
      toast.error("No se pudo quitar el ejemplar", { description: mensajeDeError(error) })
    }
  }

  function alPresionarTecla(e: React.KeyboardEvent) {
    if (e.key === "Enter") {
      e.preventDefault()
      guardar()
    } else if (e.key === "Escape") {
      e.preventDefault()
      cancelar()
    }
  }

  // La fila en edición ocupa las cuatro columnas: en el celular las casillas van apiladas.
  const filaEdicion = (clave: string) => (
    <TableRow key={clave} onKeyDown={alPresionarTecla} className="bg-muted/40 hover:bg-muted/40">
      <TableCell colSpan={4} className="whitespace-normal">
        <div className="grid gap-2 sm:grid-cols-[1.4fr_0.8fr_1fr_1.4fr]">
          <Entrada campo="cota" rotulo="Cota" borrador={borrador} onCambio={setBorrador}
                   placeholder={editando === "nuevo" ? cotaLibro || "Cota" : undefined} mono autoFocus />
          <Entrada campo="numero_copia" rotulo="Copia" borrador={borrador} onCambio={setBorrador}
                   placeholder={editando === "nuevo" ? "La siguiente" : undefined} />
          <Entrada campo="codigo_barras" rotulo="Código" borrador={borrador} onCambio={setBorrador}
                   mono error={errorCodigo} onEditar={() => setErrorCodigo(null)} />
          <Entrada campo="nota" rotulo="Nota" borrador={borrador} onCambio={setBorrador} />
        </div>
      </TableCell>
      <TableCell className="align-top text-right">
        <div className="flex justify-end gap-1">
          <Button type="button" size="icon-sm" aria-label="Guardar el ejemplar" disabled={guardando}
                  onClick={guardar}>
            {guardando ? <Loader2 className="animate-spin" /> : <Check />}
          </Button>
          <Button type="button" size="icon-sm" variant="ghost" aria-label="Cancelar" onClick={cancelar}>
            <X />
          </Button>
        </div>
      </TableCell>
    </TableRow>
  )

  return (
    <section aria-labelledby="titulo-ejemplares" className="mx-auto max-w-3xl space-y-3 rounded-lg border border-border bg-card p-4 sm:p-6">
      <div className="flex items-center justify-between gap-3">
        <h2 id="titulo-ejemplares" className="text-base font-semibold text-foreground">
          Ejemplares <span className="font-normal text-muted-foreground">({ejemplares.length})</span>
        </h2>
        <Button type="button" variant="outline" size="sm" disabled={editando === "nuevo"}
                onClick={() => empezar("nuevo", BORRADOR_VACIO)}>
          <Plus /> Agregar ejemplar
        </Button>
      </div>
      <div className="overflow-x-auto">
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>Cota</TableHead>
              <TableHead>Copia</TableHead>
              <TableHead className="hidden sm:table-cell">Código</TableHead>
              <TableHead className="hidden sm:table-cell">Nota</TableHead>
              <TableHead className="w-24 text-right">
                <span className="sr-only">Acciones</span>
              </TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {ejemplares.map((e) =>
              editando === e.id ? (
                filaEdicion(String(e.id))
              ) : (
                <TableRow key={e.id}>
                  <TableCell className="whitespace-normal">
                    <span className="font-mono">
                      {e.cota ?? <span className="font-sans text-muted-foreground">Sin cota</span>}
                    </span>
                    {(e.codigo_barras || e.nota) && (
                      <span className="block text-xs text-muted-foreground sm:hidden">
                        {[e.codigo_barras, e.nota].filter(Boolean).join(" · ")}
                      </span>
                    )}
                  </TableCell>
                  <TableCell>{e.numero_copia ?? "—"}</TableCell>
                  <TableCell className="hidden font-mono sm:table-cell">
                    {e.codigo_barras ?? <span className="text-muted-foreground">—</span>}
                  </TableCell>
                  <TableCell className="hidden whitespace-normal sm:table-cell">{e.nota ?? ""}</TableCell>
                  <TableCell className="text-right">
                    <div className="flex justify-end gap-1">
                      <Button type="button" size="icon-sm" variant="ghost"
                              aria-label={`Editar el ejemplar ${nombreEjemplar(e)}`}
                              onClick={() => empezar(e.id, borradorDe(e))}>
                        <Pencil />
                      </Button>
                      <Button type="button" size="icon-sm" variant="ghost"
                              aria-label={`Quitar el ejemplar ${nombreEjemplar(e)}`}
                              className="text-destructive hover:text-destructive"
                              onClick={() => setAQuitar(e)}>
                        <Trash2 />
                      </Button>
                    </div>
                  </TableCell>
                </TableRow>
              ),
            )}
            {editando === "nuevo" && filaEdicion("nuevo")}
            {ejemplares.length === 0 && editando !== "nuevo" && (
              <TableRow>
                <TableCell colSpan={5} className="py-6 text-center text-muted-foreground">
                  Este libro no tiene ejemplares.
                </TableCell>
              </TableRow>
            )}
          </TableBody>
        </Table>
      </div>
      <p className="text-xs text-muted-foreground">
        Sin cota, el ejemplar nuevo lleva la del libro; sin copia, la siguiente (c.1, c.2…).
      </p>

      <AlertDialog open={aQuitar !== null} onOpenChange={(abierto) => !abierto && setAQuitar(null)}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>¿Quitar este ejemplar?</AlertDialogTitle>
            <AlertDialogDescription>
              Se borra el ejemplar {aQuitar ? nombreEjemplar(aQuitar) : ""} de este libro. No se
              puede deshacer.
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel>Cancelar</AlertDialogCancel>
            <AlertDialogAction
              className="bg-destructive text-white hover:bg-destructive/90"
              onClick={() => aQuitar && quitar(aQuitar)}
            >
              Quitar
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </section>
  )
}

function Entrada({ campo, rotulo, borrador, onCambio, placeholder, mono, autoFocus, error,
                  onEditar }: {
  campo: CampoEjemplar
  rotulo: string
  borrador: Borrador
  onCambio: (b: Borrador) => void
  placeholder?: string
  mono?: boolean
  autoFocus?: boolean
  error?: string | null
  onEditar?: () => void
}) {
  const id = `ejemplar-${campo}`
  return (
    <div className="space-y-1">
      <label htmlFor={id} className="text-xs font-medium text-muted-foreground">{rotulo}</label>
      <Input
        id={id}
        value={borrador[campo]}
        maxLength={LARGO_MAXIMO[campo]}
        placeholder={placeholder}
        autoFocus={autoFocus}
        autoComplete="off"
        spellCheck={mono ? false : undefined}
        aria-invalid={error ? true : undefined}
        aria-describedby={error ? `${id}-error` : undefined}
        className={`h-8 ${mono ? "font-mono" : ""}`}
        onChange={(e) => {
          onCambio({ ...borrador, [campo]: e.target.value })
          onEditar?.()
        }}
      />
      {error && <p id={`${id}-error`} role="alert" className="text-xs text-destructive">{error}</p>}
    </div>
  )
}
