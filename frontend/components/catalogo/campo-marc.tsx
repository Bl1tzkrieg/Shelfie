"use client"

import { Copy, Plus, Trash2, X } from "lucide-react"

import { Button } from "@/components/ui/button"
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu"
import { Input } from "@/components/ui/input"
import { Textarea } from "@/components/ui/textarea"
import { nuevoId, type CampoEditor } from "@/lib/marc"
import type { DefinicionCampo, OpcionIndicador } from "@/lib/types"
import { cn } from "@/lib/utils"

/** Notas y resúmenes (5XX) suelen ser largos: se editan en un área de texto. */
const esTextoLargo = (tag: string, codigo: string) =>
  tag.startsWith("5") && codigo === "a"

interface CampoMarcProps {
  campo: CampoEditor
  definicion?: DefinicionCampo
  /** Errores del backend que apuntan a este campo: [subcampo | null, mensaje]. */
  errores: { subcampo: string | null; msg: string }[]
  soloLectura: boolean
  onChange: (campo: CampoEditor) => void
  onRepetir?: () => void
  onQuitar: () => void
}

export function CampoMarc({
  campo,
  definicion,
  errores,
  soloLectura,
  onChange,
  onRepetir,
  onQuitar,
}: CampoMarcProps) {
  const conError = errores.length > 0
  const nombre = definicion?.nombre ?? "Campo fuera de la plantilla"

  return (
    <div
      id={`campo-${campo.id}`}
      data-tag={campo.tag}
      className={cn(
        "rounded-lg border bg-card shadow-papel p-3",
        conError ? "border-destructive/60 bg-destructive/5" : "border-border"
      )}
    >
      <div className="flex flex-wrap items-center gap-2">
        <span className="rounded bg-muted px-1.5 py-0.5 font-mono text-sm font-semibold text-foreground">
          {campo.tag}
        </span>
        <span className={cn("text-sm font-medium", definicion ? "text-foreground" : "text-muted-foreground italic")}>
          {nombre}
        </span>
        {definicion?.obligatorio && (
          <span className="text-xs text-destructive" aria-label="obligatorio">obligatorio</span>
        )}

        {!campo.control && (
          <div className="ml-auto flex items-center gap-1">
            <Indicador
              etiqueta={`Indicador 1 de ${campo.tag}`}
              valor={campo.ind1}
              opciones={definicion?.ind1 ?? []}
              disabled={soloLectura}
              onChange={(v) => onChange({ ...campo, ind1: v })}
            />
            <Indicador
              etiqueta={`Indicador 2 de ${campo.tag}`}
              valor={campo.ind2}
              opciones={definicion?.ind2 ?? []}
              disabled={soloLectura}
              onChange={(v) => onChange({ ...campo, ind2: v })}
            />
          </div>
        )}
        {!soloLectura && (
          <div className={cn("flex items-center", campo.control && "ml-auto")}>
            {onRepetir && (
              <Button type="button" variant="ghost" size="icon" className="h-8 w-8"
                      aria-label={`Repetir el campo ${campo.tag}`} onClick={onRepetir}>
                <Copy className="h-4 w-4" />
              </Button>
            )}
            <Button type="button" variant="ghost" size="icon" className="h-8 w-8"
                    aria-label={`Quitar el campo ${campo.tag}`} onClick={onQuitar}>
              <Trash2 className="h-4 w-4 text-muted-foreground" />
            </Button>
          </div>
        )}
      </div>

      {campo.control ? (
        <div className="mt-2">
          <Input
            aria-label={`${campo.tag} ${nombre}`}
            value={campo.valor}
            readOnly={soloLectura}
            spellCheck={false}
            className="font-mono text-sm"
            onChange={(e) => onChange({ ...campo, valor: e.target.value })}
          />
          {campo.tag === "008" && (
            <p className="mt-1 text-xs tabular-nums text-muted-foreground">
              {campo.valor.length} de 40 posiciones
            </p>
          )}
        </div>
      ) : (
        <div className="mt-2 space-y-1.5">
          {campo.subcampos.map((sub, i) => {
            const defSub = definicion?.subcampos.find((s) => s.codigo === sub.codigo)
            const subError = errores.some((e) => e.subcampo === sub.codigo)
            const etiqueta = `${campo.tag} $${sub.codigo} ${defSub?.nombre ?? ""}`.trim()
            const actualizar = (valor: string) =>
              onChange({
                ...campo,
                subcampos: campo.subcampos.map((s, j) => (j === i ? { ...s, valor } : s)),
              })
            return (
              <div key={sub.id} className="flex items-start gap-2">
                <span
                  className="mt-2 w-48 shrink-0 truncate text-xs text-muted-foreground"
                  title={defSub?.nombre}
                >
                  <span className="font-mono font-semibold text-foreground">${sub.codigo}</span>{" "}
                  {defSub?.nombre ?? ""}
                </span>
                {esTextoLargo(campo.tag, sub.codigo) ? (
                  <Textarea
                    aria-label={etiqueta}
                    value={sub.valor}
                    readOnly={soloLectura}
                    rows={2}
                    className={cn("min-h-9 text-sm", subError && "border-destructive")}
                    onChange={(e) => actualizar(e.target.value)}
                  />
                ) : (
                  <Input
                    aria-label={etiqueta}
                    value={sub.valor}
                    readOnly={soloLectura}
                    className={cn("h-9 text-sm", subError && "border-destructive")}
                    onChange={(e) => actualizar(e.target.value)}
                  />
                )}
                {!soloLectura && (
                  <Button type="button" variant="ghost" size="icon" className="h-9 w-9 shrink-0"
                          aria-label={`Quitar $${sub.codigo} de ${campo.tag}`}
                          onClick={() => onChange({
                            ...campo, subcampos: campo.subcampos.filter((_, j) => j !== i),
                          })}>
                    <X className="h-4 w-4 text-muted-foreground" />
                  </Button>
                )}
              </div>
            )
          })}
          {!soloLectura && (
            <AgregarSubcampo
              campo={campo}
              definicion={definicion}
              onAgregar={(codigo) =>
                onChange({
                  ...campo,
                  subcampos: [...campo.subcampos, { id: nuevoId(), codigo, valor: "" }],
                })
              }
            />
          )}
        </div>
      )}

      {conError && (
        <ul className="mt-2 space-y-0.5 text-xs text-destructive">
          {errores.map((e, i) => (
            <li key={i}>{e.msg}</li>
          ))}
        </ul>
      )}
    </div>
  )
}

function Indicador({
  etiqueta,
  valor,
  opciones,
  disabled,
  onChange,
}: {
  etiqueta: string
  valor: string
  opciones: OpcionIndicador[]
  disabled: boolean
  onChange: (v: string) => void
}) {
  // Sin opciones definidas: un carácter libre (blanco por defecto).
  if (opciones.length === 0) {
    return (
      <Input
        aria-label={etiqueta}
        value={valor === " " ? "" : valor}
        maxLength={1}
        disabled={disabled}
        placeholder="#"
        className="h-8 w-9 px-0 text-center font-mono text-sm"
        onChange={(e) => onChange(e.target.value.slice(-1) || " ")}
      />
    )
  }
  const conBlanco = opciones.some((o) => o.valor === " ")
    ? opciones
    : [{ valor: " ", nombre: "Sin definir" }, ...opciones]
  return (
    <select
      aria-label={etiqueta}
      value={valor}
      disabled={disabled}
      title={conBlanco.find((o) => o.valor === valor)?.nombre}
      onChange={(e) => onChange(e.target.value)}
      className="h-8 w-12 rounded-md border border-input bg-background px-1 font-mono text-sm"
    >
      {conBlanco.map((o) => (
        <option key={o.valor} value={o.valor} title={o.nombre}>
          {o.valor === " " ? "#" : o.valor} — {o.nombre}
        </option>
      ))}
    </select>
  )
}

function AgregarSubcampo({
  campo,
  definicion,
  onAgregar,
}: {
  campo: Extract<CampoEditor, { control: false }>
  definicion?: DefinicionCampo
  onAgregar: (codigo: string) => void
}) {
  const presentes = new Set(campo.subcampos.map((s) => s.codigo))
  const disponibles = (definicion?.subcampos ?? []).filter(
    (s) => s.repetible || !presentes.has(s.codigo)
  )
  return (
    <DropdownMenu>
      <DropdownMenuTrigger asChild>
        <Button type="button" variant="ghost" size="sm" className="h-7 px-2 text-xs text-primary">
          <Plus className="mr-1 h-3.5 w-3.5" />
          Subcampo
        </Button>
      </DropdownMenuTrigger>
      <DropdownMenuContent align="start" className="max-h-72 overflow-y-auto">
        {disponibles.map((s) => (
          <DropdownMenuItem key={s.codigo} onClick={() => onAgregar(s.codigo)}>
            <span className="mr-2 font-mono font-semibold">${s.codigo}</span>
            {s.nombre}
          </DropdownMenuItem>
        ))}
        {"abcdefghijklmnopqrstuvwxyz0123456789"
          .split("")
          .filter((c) => !definicion?.subcampos.some((s) => s.codigo === c))
          .slice(0, definicion ? 0 : 36)
          .map((c) => (
            <DropdownMenuItem key={c} onClick={() => onAgregar(c)}>
              <span className="font-mono">${c}</span>
            </DropdownMenuItem>
          ))}
      </DropdownMenuContent>
    </DropdownMenu>
  )
}
