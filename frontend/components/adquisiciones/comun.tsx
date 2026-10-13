"use client"

import { Badge } from "@/components/ui/badge"
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select"
import type { EstadoLinea, EstadoPedido, Fondo } from "@/lib/types"
import { cn } from "@/lib/utils"

export const bs = (n: number) => `Bs. ${n.toFixed(2)}`

const ESTADO_PEDIDO: Record<EstadoPedido, { texto: string; clase: string }> = {
  Abierta: { texto: "Abierto", clase: "bg-secondary text-secondary-foreground" },
  Cerrada: { texto: "Por recibir", clase: "bg-accent/20 text-accent-foreground" },
  Recibida: { texto: "Recibido", clase: "bg-primary/10 text-primary" },
  Cancelada: { texto: "Cancelado", clase: "bg-muted text-muted-foreground" },
}

export function EstadoPedidoBadge({ estado }: { estado: EstadoPedido }) {
  const e = ESTADO_PEDIDO[estado]
  return <span className={cn("rounded-full px-2.5 py-0.5 text-xs font-medium", e.clase)}>{e.texto}</span>
}

const ESTADO_LINEA: Record<EstadoLinea, "default" | "secondary" | "outline"> = {
  Pendiente: "outline",
  Parcial: "secondary",
  Recibida: "default",
  Cancelada: "outline",
}

export function EstadoLineaBadge({ estado }: { estado: EstadoLinea }) {
  return (
    <Badge variant={ESTADO_LINEA[estado]} className={cn(estado === "Cancelada" && "line-through")}>
      {estado}
    </Badge>
  )
}

/** Barra de un fondo: gastado, comprometido y disponible sobre lo asignado. */
export function BarraFondo({ fondo, className }: { fondo: Fondo; className?: string }) {
  const total = Math.max(fondo.asignado, fondo.gastado + fondo.comprometido, 0.01)
  const pct = (n: number) => `${Math.max(0, (n / total) * 100)}%`
  const excedido = fondo.disponible < 0
  return (
    <div className={cn("space-y-1", className)}>
      <div
        className="flex h-2 overflow-hidden rounded-full bg-muted"
        role="img"
        aria-label={`Gastado ${bs(fondo.gastado)}, comprometido ${bs(fondo.comprometido)}, disponible ${bs(fondo.disponible)}`}
      >
        <div className="bg-primary" style={{ width: pct(fondo.gastado) }} />
        <div className="bg-accent" style={{ width: pct(fondo.comprometido) }} />
      </div>
      <div className="flex flex-wrap gap-x-3 text-xs text-muted-foreground">
        <span><span className="mr-1 inline-block h-2 w-2 rounded-full bg-primary" />Gastado {bs(fondo.gastado)}</span>
        <span><span className="mr-1 inline-block h-2 w-2 rounded-full bg-accent" />Comprometido {bs(fondo.comprometido)}</span>
        <span className={cn(excedido && "font-medium text-destructive")}>Disponible {bs(fondo.disponible)}</span>
      </div>
    </div>
  )
}

const SIN_FONDO = "ninguno"

/** Selector de fondo con lo disponible; vacío = sin fondo. */
export function FondoSelect({
  id,
  fondos,
  valor,
  onChange,
  disabled,
}: {
  id: string
  fondos: Fondo[]
  valor: number | null
  onChange: (id: number | null) => void
  disabled?: boolean
}) {
  return (
    <Select
      value={valor === null ? SIN_FONDO : String(valor)}
      onValueChange={(v) => onChange(v === SIN_FONDO ? null : Number(v))}
      disabled={disabled}
    >
      <SelectTrigger id={id} className="w-full">
        <SelectValue />
      </SelectTrigger>
      <SelectContent>
        <SelectItem value={SIN_FONDO}>Sin fondo</SelectItem>
        {fondos.map((f) => (
          <SelectItem key={f.id} value={String(f.id)}>
            {f.codigo} · {f.nombre} — {bs(f.disponible)} disp.
          </SelectItem>
        ))}
      </SelectContent>
    </Select>
  )
}

export function fechaCorta(iso: string | null) {
  if (!iso) return "—"
  const d = new Date(iso.length === 10 ? `${iso}T12:00:00` : iso)
  return d.toLocaleDateString("es-VE", { day: "2-digit", month: "short", year: "numeric" })
}

export function Kpi({ titulo, valor, alerta = false }: { titulo: string; valor: number | string; alerta?: boolean }) {
  return (
    <div className="rounded-lg border bg-card p-5">
      <p className="text-sm text-muted-foreground">{titulo}</p>
      <p className={cn("mt-1 text-2xl font-bold tabular-nums", alerta && "text-destructive")}>{valor}</p>
    </div>
  )
}

export function Vacio({ children }: { children: React.ReactNode }) {
  return (
    <div className="rounded-lg border border-dashed bg-card py-12 text-center text-sm text-muted-foreground">
      {children}
    </div>
  )
}
