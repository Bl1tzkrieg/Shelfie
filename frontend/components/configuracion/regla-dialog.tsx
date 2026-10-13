"use client"

import { useState } from "react"
import { Loader2 } from "lucide-react"
import { toast } from "sonner"

import { Button } from "@/components/ui/button"
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select"
import { Switch } from "@/components/ui/switch"
import { apiPut, mensajeDeError } from "@/lib/api"
import type { DatosRegla, OpcionDimension, OpcionesRegla, ReglaCirculacion } from "@/lib/types"

/** Radix Select no admite "" como valor: "todas" representa el null de la API. */
const TODAS = "todas"

const NUEVA: DatosRegla = {
  categoria_id: null,
  tipo_item_id: null,
  biblioteca_id: null,
  prestable: true,
  dias_prestamo: 14,
  max_prestamos: 3,
  max_renovaciones: 2,
  multa_por_dia: 1.5,
  multa_maxima: null,
  dias_gracia: 0,
  max_reservas: 5,
}

interface ReglaDialogProps {
  /** null = cerrado; "nueva" = alta; una regla = edición. */
  regla: ReglaCirculacion | "nueva" | null
  /** Valores con que arranca una regla nueva (normalmente, los de la regla general). */
  base?: ReglaCirculacion
  opciones: OpcionesRegla
  onClose: () => void
  onSaved: () => void
}

export function ReglaDialog({ regla, base, opciones, onClose, onSaved }: ReglaDialogProps) {
  const clave = regla === null ? "cerrado" : regla === "nueva" ? "nueva" : String(regla.id)
  return (
    <Dialog open={regla !== null} onOpenChange={(v) => !v && onClose()}>
      <DialogContent className="sm:max-w-2xl">
        {regla !== null && (
          <FormularioRegla
            key={clave}
            regla={regla === "nueva" ? null : regla}
            base={base}
            opciones={opciones}
            onClose={onClose}
            onSaved={onSaved}
          />
        )}
      </DialogContent>
    </Dialog>
  )
}

function desde(regla: ReglaCirculacion | DatosRegla): DatosRegla {
  return {
    categoria_id: regla.categoria_id,
    tipo_item_id: regla.tipo_item_id,
    biblioteca_id: regla.biblioteca_id,
    prestable: regla.prestable,
    dias_prestamo: regla.dias_prestamo,
    max_prestamos: regla.max_prestamos,
    max_renovaciones: regla.max_renovaciones,
    multa_por_dia: regla.multa_por_dia,
    multa_maxima: regla.multa_maxima,
    dias_gracia: regla.dias_gracia,
    max_reservas: regla.max_reservas,
  }
}

function FormularioRegla({
  regla,
  base,
  opciones,
  onClose,
  onSaved,
}: {
  regla: ReglaCirculacion | null
  base?: ReglaCirculacion
  opciones: OpcionesRegla
  onClose: () => void
  onSaved: () => void
}) {
  const editando = regla !== null
  const [datos, setDatos] = useState<DatosRegla>(() =>
    regla ? desde(regla) : { ...(base ? desde(base) : NUEVA), categoria_id: null,
                             tipo_item_id: null, biblioteca_id: null }
  )
  // Los números se editan como texto para permitir borrar el campo mientras se escribe.
  const [textos, setTextos] = useState(() => ({
    dias_prestamo: String(datos.dias_prestamo),
    max_prestamos: String(datos.max_prestamos),
    max_renovaciones: String(datos.max_renovaciones),
    multa_por_dia: String(datos.multa_por_dia),
    multa_maxima: datos.multa_maxima === null ? "" : String(datos.multa_maxima),
    dias_gracia: String(datos.dias_gracia),
    max_reservas: String(datos.max_reservas),
  }))
  const [guardando, setGuardando] = useState(false)

  const esGeneral =
    datos.categoria_id === null && datos.tipo_item_id === null && datos.biblioteca_id === null

  function setTexto(campo: keyof typeof textos, valor: string) {
    setTextos((t) => ({ ...t, [campo]: valor }))
  }

  function numero(texto: string, decimales: boolean): number | null {
    if (texto.trim() === "") return null
    const n = Number(texto)
    if (!Number.isFinite(n) || n < 0) return null
    return decimales ? n : Math.trunc(n)
  }

  async function guardar(e: React.FormEvent) {
    e.preventDefault()
    const enteros = ["dias_prestamo", "max_prestamos", "max_renovaciones", "dias_gracia",
                     "max_reservas"] as const
    const cuerpo: DatosRegla = { ...datos }
    for (const campo of enteros) {
      const n = numero(textos[campo], false)
      if (n === null) {
        toast.error("Revisa los valores", { description: "Los campos numéricos no pueden quedar vacíos ni ser negativos." })
        return
      }
      cuerpo[campo] = n
    }
    const multa = numero(textos.multa_por_dia, true)
    if (multa === null) {
      toast.error("Revisa los valores", { description: "Indica la multa por día (puede ser 0)." })
      return
    }
    cuerpo.multa_por_dia = multa
    cuerpo.multa_maxima = numero(textos.multa_maxima, true)

    setGuardando(true)
    try {
      await apiPut<ReglaCirculacion>("/circulation-rules", cuerpo)
      toast.success(editando ? "Regla actualizada" : "Regla guardada")
      onSaved()
    } catch (error) {
      toast.error("No se pudo guardar la regla", { description: mensajeDeError(error) })
    } finally {
      setGuardando(false)
    }
  }

  return (
    <form onSubmit={guardar}>
      <DialogHeader>
        <DialogTitle>{editando ? "Editar regla de circulación" : "Nueva regla de circulación"}</DialogTitle>
        <DialogDescription>
          {editando
            ? "La combinación no se cambia: para otra combinación, crea una regla nueva."
            : "Elige a qué lectores, tipos de ítem y sede se aplica. Si ya existe una regla para esa combinación, se reemplaza."}
        </DialogDescription>
      </DialogHeader>

      <div className="space-y-5 py-4">
        <div className="grid gap-4 sm:grid-cols-3">
          <Dimension
            id="regla-categoria"
            label="Categoría de lector"
            todas="Todas las categorías"
            valor={datos.categoria_id}
            opciones={opciones.categorias}
            disabled={editando}
            onChange={(v) => setDatos((d) => ({ ...d, categoria_id: v }))}
          />
          <Dimension
            id="regla-tipo"
            label="Tipo de ítem"
            todas="Todos los tipos"
            valor={datos.tipo_item_id}
            opciones={opciones.tipos_item}
            disabled={editando}
            onChange={(v) => setDatos((d) => ({ ...d, tipo_item_id: v }))}
          />
          <Dimension
            id="regla-sede"
            label="Sede"
            todas="Todas las sedes"
            valor={datos.biblioteca_id}
            opciones={opciones.bibliotecas}
            disabled={editando}
            onChange={(v) => setDatos((d) => ({ ...d, biblioteca_id: v }))}
          />
        </div>
        {esGeneral && !editando && (
          <p className="text-sm text-muted-foreground">
            Con las tres dimensiones en “todas” estarás editando la regla general.
          </p>
        )}

        <div className="flex items-center justify-between rounded-lg border border-border p-3">
          <div>
            <Label htmlFor="regla-prestable">Se presta</Label>
            <p className="text-sm text-muted-foreground">
              Apágalo para material de consulta en sala (no sale de la biblioteca).
            </p>
          </div>
          <Switch
            id="regla-prestable"
            checked={datos.prestable}
            onCheckedChange={(v) => setDatos((d) => ({ ...d, prestable: v }))}
          />
        </div>

        <fieldset disabled={!datos.prestable} className="space-y-4 disabled:opacity-50">
          <div className="grid gap-4 sm:grid-cols-3">
            <Numero id="regla-dias" label="Días de préstamo" valor={textos.dias_prestamo}
                    onChange={(v) => setTexto("dias_prestamo", v)} />
            <Numero id="regla-max" label="Préstamos simultáneos" valor={textos.max_prestamos}
                    onChange={(v) => setTexto("max_prestamos", v)} />
            <Numero id="regla-renov" label="Renovaciones" valor={textos.max_renovaciones}
                    onChange={(v) => setTexto("max_renovaciones", v)} />
          </div>
          <div className="grid gap-4 sm:grid-cols-3">
            <Numero id="regla-multa" label="Multa por día (Bs.)" decimales
                    valor={textos.multa_por_dia} onChange={(v) => setTexto("multa_por_dia", v)} />
            <Numero id="regla-tope" label="Tope de multa (Bs.)" decimales placeholder="Sin tope"
                    valor={textos.multa_maxima} onChange={(v) => setTexto("multa_maxima", v)} />
            <Numero id="regla-gracia" label="Días de gracia" valor={textos.dias_gracia}
                    onChange={(v) => setTexto("dias_gracia", v)} />
          </div>
          <div className="grid gap-4 sm:grid-cols-3">
            <Numero id="regla-reservas" label="Reservas simultáneas" valor={textos.max_reservas}
                    onChange={(v) => setTexto("max_reservas", v)} />
          </div>
        </fieldset>
      </div>

      <DialogFooter>
        <Button type="button" variant="outline" onClick={onClose} disabled={guardando}>
          Cancelar
        </Button>
        <Button type="submit" disabled={guardando}>
          {guardando && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}
          Guardar regla
        </Button>
      </DialogFooter>
    </form>
  )
}

function Dimension({
  id,
  label,
  todas,
  valor,
  opciones,
  disabled,
  onChange,
}: {
  id: string
  label: string
  todas: string
  valor: number | null
  opciones: OpcionDimension[]
  disabled?: boolean
  onChange: (valor: number | null) => void
}) {
  return (
    <div className="space-y-2">
      <Label htmlFor={id}>{label}</Label>
      <Select
        value={valor === null ? TODAS : String(valor)}
        onValueChange={(v) => onChange(v === TODAS ? null : Number(v))}
        disabled={disabled}
      >
        <SelectTrigger id={id} className="w-full">
          <SelectValue />
        </SelectTrigger>
        <SelectContent>
          <SelectItem value={TODAS}>{todas}</SelectItem>
          {opciones.map((o) => (
            <SelectItem key={o.id} value={String(o.id)}>
              {o.nombre}
            </SelectItem>
          ))}
        </SelectContent>
      </Select>
    </div>
  )
}

function Numero({
  id,
  label,
  valor,
  onChange,
  decimales = false,
  placeholder,
}: {
  id: string
  label: string
  valor: string
  onChange: (valor: string) => void
  decimales?: boolean
  placeholder?: string
}) {
  return (
    <div className="space-y-2">
      <Label htmlFor={id}>{label}</Label>
      <Input
        id={id}
        type="number"
        min={0}
        step={decimales ? "0.01" : "1"}
        inputMode={decimales ? "decimal" : "numeric"}
        placeholder={placeholder}
        value={valor}
        onChange={(e) => onChange(e.target.value)}
      />
    </div>
  )
}
