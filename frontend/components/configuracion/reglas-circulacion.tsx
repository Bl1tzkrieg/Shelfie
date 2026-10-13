"use client"

import { useMemo, useState } from "react"
import { Ban, Pencil, Plus, Trash2 } from "lucide-react"
import { toast } from "sonner"

import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
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
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select"
import { apiDelete, mensajeDeError } from "@/lib/api"
import type { OpcionDimension, OpcionesRegla, ReglaCirculacion } from "@/lib/types"
import { cn } from "@/lib/utils"
import { ReglaDialog } from "./regla-dialog"

const TODAS = "todas"

/** Mismo criterio que app/services/reglas.py: sede > tipo de ítem > categoría. */
function especificidad(r: ReglaCirculacion) {
  return (r.biblioteca_id ? 4 : 0) + (r.tipo_item_id ? 2 : 0) + (r.categoria_id ? 1 : 0)
}

function esGeneral(r: ReglaCirculacion) {
  return r.categoria_id === null && r.tipo_item_id === null && r.biblioteca_id === null
}

function reglaQueAplica(
  reglas: ReglaCirculacion[],
  categoria: number | null,
  tipo: number | null,
  sede: number | null
): ReglaCirculacion | undefined {
  const coinciden = reglas.filter(
    (r) =>
      (r.categoria_id === null || r.categoria_id === categoria) &&
      (r.tipo_item_id === null || r.tipo_item_id === tipo) &&
      (r.biblioteca_id === null || r.biblioteca_id === sede)
  )
  return coinciden.reduce<ReglaCirculacion | undefined>(
    (mejor, r) => (!mejor || especificidad(r) > especificidad(mejor) ? r : mejor),
    undefined
  )
}

function dinero(valor: number) {
  return `Bs. ${valor.toFixed(2)}`
}

interface ReglasCirculacionProps {
  reglas: ReglaCirculacion[]
  opciones: OpcionesRegla
  onChange: () => void
}

export function ReglasCirculacion({ reglas, opciones, onChange }: ReglasCirculacionProps) {
  const [editando, setEditando] = useState<ReglaCirculacion | "nueva" | null>(null)
  const [aEliminar, setAEliminar] = useState<ReglaCirculacion | null>(null)
  const [prueba, setPrueba] = useState<{ categoria: number | null; tipo: number | null; sede: number | null }>(
    { categoria: null, tipo: null, sede: opciones.bibliotecas[0]?.id ?? null }
  )

  const general = reglas.find(esGeneral)
  const aplicada = useMemo(
    () => reglaQueAplica(reglas, prueba.categoria, prueba.tipo, prueba.sede),
    [reglas, prueba]
  )
  const pruebaCompleta = prueba.categoria !== null && prueba.tipo !== null

  async function eliminar() {
    const regla = aEliminar
    if (!regla) return
    setAEliminar(null)
    try {
      await apiDelete(`/circulation-rules/${regla.id}`)
      toast.success("Regla eliminada", {
        description: "Esa combinación pasa a usar la siguiente regla más general.",
      })
      onChange()
    } catch (error) {
      toast.error("No se pudo eliminar la regla", { description: mensajeDeError(error) })
    }
  }

  return (
    <div className="space-y-6">
      <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
        <p className="max-w-2xl text-sm text-muted-foreground">
          Cada préstamo usa la regla <strong className="text-foreground">más específica</strong> que
          coincida con el lector, el ejemplar y la sede. La sede pesa más que el tipo de ítem, y el
          tipo de ítem más que la categoría. La regla general cubre todo lo demás.
        </p>
        <Button onClick={() => setEditando("nueva")} className="shrink-0">
          <Plus className="mr-2 h-4 w-4" />
          Nueva regla
        </Button>
      </div>

      <div className="overflow-x-auto rounded-lg border border-border">
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b border-border bg-muted/50 text-left text-muted-foreground">
              <th className="px-4 py-3 font-medium">Categoría</th>
              <th className="px-4 py-3 font-medium">Tipo de ítem</th>
              <th className="px-4 py-3 font-medium">Sede</th>
              <th className="px-4 py-3 text-right font-medium">Días</th>
              <th className="px-4 py-3 text-right font-medium">Máx.</th>
              <th className="px-4 py-3 text-right font-medium">Renov.</th>
              <th className="px-4 py-3 font-medium">Multa</th>
              <th className="px-4 py-3 text-right font-medium">Reservas</th>
              <th className="px-4 py-3">
                <span className="sr-only">Acciones</span>
              </th>
            </tr>
          </thead>
          <tbody className="divide-y divide-border">
            {reglas.map((r) => {
              const resaltada = pruebaCompleta && aplicada?.id === r.id
              return (
                <tr
                  key={r.id}
                  className={cn("hover:bg-muted/30", resaltada && "bg-primary/5 hover:bg-primary/10")}
                >
                  <Celda valor={r.categoria} todas={r.categoria_id === null} />
                  <Celda valor={r.tipo_item} todas={r.tipo_item_id === null} />
                  <Celda valor={r.biblioteca} todas={r.biblioteca_id === null} />
                  {r.prestable ? (
                    <>
                      <td className="px-4 py-3 text-right tabular-nums">{r.dias_prestamo}</td>
                      <td className="px-4 py-3 text-right tabular-nums">{r.max_prestamos}</td>
                      <td className="px-4 py-3 text-right tabular-nums">{r.max_renovaciones}</td>
                      <td className="px-4 py-3">
                        <span className="tabular-nums">{dinero(r.multa_por_dia)}</span>
                        <span className="text-muted-foreground"> / día</span>
                        {(r.multa_maxima !== null || r.dias_gracia > 0) && (
                          <p className="text-xs text-muted-foreground">
                            {[
                              r.multa_maxima !== null && `tope ${dinero(r.multa_maxima)}`,
                              r.dias_gracia > 0 && `${r.dias_gracia} día(s) de gracia`,
                            ]
                              .filter(Boolean)
                              .join(" · ")}
                          </p>
                        )}
                      </td>
                      <td className="px-4 py-3 text-right tabular-nums">{r.max_reservas}</td>
                    </>
                  ) : (
                    <td colSpan={5} className="px-4 py-3">
                      <Badge variant="secondary" className="gap-1">
                        <Ban className="h-3 w-3" />
                        No se presta
                      </Badge>
                    </td>
                  )}
                  <td className="px-4 py-3">
                    <div className="flex justify-end gap-1">
                      <Button
                        variant="ghost"
                        size="icon"
                        aria-label={`Editar la regla ${r.categoria} · ${r.tipo_item} · ${r.biblioteca}`}
                        onClick={() => setEditando(r)}
                      >
                        <Pencil className="h-4 w-4" />
                      </Button>
                      {!esGeneral(r) && (
                        <Button
                          variant="ghost"
                          size="icon"
                          aria-label={`Eliminar la regla ${r.categoria} · ${r.tipo_item} · ${r.biblioteca}`}
                          onClick={() => setAEliminar(r)}
                        >
                          <Trash2 className="h-4 w-4 text-destructive" />
                        </Button>
                      )}
                    </div>
                  </td>
                </tr>
              )
            })}
          </tbody>
        </table>
      </div>

      <div className="rounded-lg border border-dashed border-border p-4">
        <h4 className="text-sm font-medium text-foreground">¿Qué regla se aplica?</h4>
        <p className="mb-3 text-sm text-muted-foreground">
          Elige un tipo de lector y de ítem para ver qué regla usará el préstamo.
        </p>
        <div className="grid gap-3 sm:grid-cols-3">
          <Probador
            etiqueta="Categoría"
            valor={prueba.categoria}
            opciones={opciones.categorias}
            onChange={(v) => setPrueba((p) => ({ ...p, categoria: v }))}
          />
          <Probador
            etiqueta="Tipo de ítem"
            valor={prueba.tipo}
            opciones={opciones.tipos_item}
            onChange={(v) => setPrueba((p) => ({ ...p, tipo: v }))}
          />
          <Probador
            etiqueta="Sede"
            valor={prueba.sede}
            opciones={opciones.bibliotecas}
            onChange={(v) => setPrueba((p) => ({ ...p, sede: v }))}
          />
        </div>
        {pruebaCompleta && (
          <p className="mt-3 text-sm" aria-live="polite">
            {aplicada ? (
              <>
                Se aplica la regla{" "}
                <strong>
                  {aplicada.categoria} · {aplicada.tipo_item} · {aplicada.biblioteca}
                </strong>
                {aplicada.prestable
                  ? `: ${aplicada.dias_prestamo} días, hasta ${aplicada.max_prestamos} préstamos, ${aplicada.max_renovaciones} renovación(es).`
                  : ": ese material no se presta."}{" "}
                Está resaltada en la tabla.
              </>
            ) : (
              "Ninguna regla coincide: crea la regla general."
            )}
          </p>
        )}
      </div>

      <ReglaDialog
        regla={editando}
        base={general}
        opciones={opciones}
        onClose={() => setEditando(null)}
        onSaved={() => {
          setEditando(null)
          onChange()
        }}
      />

      <AlertDialog open={aEliminar !== null} onOpenChange={(v) => !v && setAEliminar(null)}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>¿Eliminar esta regla?</AlertDialogTitle>
            <AlertDialogDescription>
              Los préstamos de{" "}
              <strong>
                {aEliminar?.categoria} · {aEliminar?.tipo_item} · {aEliminar?.biblioteca}
              </strong>{" "}
              pasarán a usar la siguiente regla más general. Los préstamos ya hechos conservan su
              fecha de vencimiento.
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel>Cancelar</AlertDialogCancel>
            <AlertDialogAction
              onClick={eliminar}
              className="bg-destructive text-destructive-foreground hover:bg-destructive/90"
            >
              Eliminar regla
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </div>
  )
}

function Celda({ valor, todas }: { valor: string; todas: boolean }) {
  return (
    <td className={cn("px-4 py-3", todas ? "text-muted-foreground" : "font-medium text-foreground")}>
      {valor}
    </td>
  )
}

function Probador({
  etiqueta,
  valor,
  opciones,
  onChange,
}: {
  etiqueta: string
  valor: number | null
  opciones: OpcionDimension[]
  onChange: (valor: number | null) => void
}) {
  return (
    <Select
      value={valor === null ? TODAS : String(valor)}
      onValueChange={(v) => onChange(v === TODAS ? null : Number(v))}
    >
      <SelectTrigger aria-label={etiqueta} className="w-full">
        <SelectValue />
      </SelectTrigger>
      <SelectContent>
        <SelectItem value={TODAS}>{etiqueta}…</SelectItem>
        {opciones.map((o) => (
          <SelectItem key={o.id} value={String(o.id)}>
            {o.nombre}
          </SelectItem>
        ))}
      </SelectContent>
    </Select>
  )
}
