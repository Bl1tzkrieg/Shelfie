"use client"

import { useEffect, useState } from "react"
import { HandCoins, Loader2, Receipt, Undo2 } from "lucide-react"
import { toast } from "sonner"

import { useSesion } from "@/components/auth/sesion-provider"
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
import { apiGet, apiPost, mensajeDeError } from "@/lib/api"
import type { CargoPendiente, EstadoCuenta, MovimientoCuenta } from "@/lib/types"
import { cn } from "@/lib/utils"

const NOMBRE_TIPO: Record<MovimientoCuenta["tipo"], string> = {
  MULTA_ATRASO: "Multa por atraso",
  REPOSICION: "Reposición",
  PAGO: "Pago",
  CONDONACION: "Condonación",
  AJUSTE: "Ajuste",
  REINTEGRO: "Reintegro",
}

type Operacion = "pago" | "condonacion"

interface CuentaLectorProps {
  carnet: string
  /** Se llama tras un pago o condonación, para refrescar la ficha. */
  onChange?: () => void
}

/** Saldo, movimientos y cobro de la cuenta de un lector (accountlines de Koha). */
export function CuentaLector({ carnet, onChange }: CuentaLectorProps) {
  const { tienePermiso } = useSesion()
  const [cuenta, setCuenta] = useState<EstadoCuenta | null>(null)
  const [operacion, setOperacion] = useState<Operacion | null>(null)

  useEffect(() => {
    let vigente = true
    apiGet<EstadoCuenta>(`/users/${encodeURIComponent(carnet)}/account`)
      .then((c) => vigente && setCuenta(c))
      .catch((error) =>
        toast.error("No se pudo cargar la cuenta", { description: mensajeDeError(error) }),
      )
    return () => {
      vigente = false
    }
  }, [carnet])

  function alRegistrar(nueva: EstadoCuenta) {
    setCuenta(nueva)
    setOperacion(null)
    onChange?.()
  }

  if (!cuenta) {
    return (
      <div className="mb-6 rounded-lg border border-border bg-card py-8 text-center text-sm text-muted-foreground">
        Cargando cuenta…
      </div>
    )
  }

  const debe = cuenta.saldo > 0

  return (
    <div className="mb-6 rounded-lg border border-border bg-card">
      <div className="flex flex-col gap-3 border-b border-border px-6 py-4 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <h3 className="font-semibold text-foreground">Cuenta del lector</h3>
          <p className="text-sm text-muted-foreground">
            {debe ? (
              <>
                Debe{" "}
                <span className={cn("font-medium", cuenta.bloqueado && "text-destructive")}>
                  Bs. {cuenta.saldo.toFixed(2)}
                </span>
                {cuenta.bloqueado
                  ? ` · supera el máximo de Bs. ${cuenta.umbral_bloqueo.toFixed(2)}: no puede retirar material`
                  : ` · por debajo del máximo de Bs. ${cuenta.umbral_bloqueo.toFixed(2)}, puede seguir retirando`}
              </>
            ) : cuenta.saldo < 0 ? (
              <>
                Saldo a favor:{" "}
                <span className="font-medium text-primary">
                  Bs. {Math.abs(cuenta.saldo).toFixed(2)}
                </span>{" "}
                · se descuenta de sus próximos cargos
              </>
            ) : (
              "Sin deuda pendiente"
            )}
          </p>
        </div>
        {debe && (
          <div className="flex gap-2">
            {tienePermiso("circulacion") && (
              <Button size="sm" onClick={() => setOperacion("pago")}>
                <HandCoins className="mr-2 h-4 w-4" />
                Registrar pago
              </Button>
            )}
            {tienePermiso("lectores") && (
              <Button size="sm" variant="outline" onClick={() => setOperacion("condonacion")}>
                <Undo2 className="mr-2 h-4 w-4" />
                Condonar
              </Button>
            )}
          </div>
        )}
      </div>

      {cuenta.movimientos.length === 0 ? (
        <div className="flex items-center justify-center gap-2 py-8 text-sm text-muted-foreground">
          <Receipt className="h-4 w-4" />
          Sin movimientos registrados.
        </div>
      ) : (
        <div className="max-h-80 overflow-y-auto">
          <table className="w-full">
            <thead className="sticky top-0 bg-card">
              <tr className="border-b border-border bg-muted/50">
                <th className="px-4 py-2 text-left text-sm font-medium text-muted-foreground">
                  Fecha
                </th>
                <th className="px-4 py-2 text-left text-sm font-medium text-muted-foreground">
                  Concepto
                </th>
                <th className="px-4 py-2 text-right text-sm font-medium text-muted-foreground">
                  Monto
                </th>
              </tr>
            </thead>
            <tbody className="divide-y divide-border">
              {cuenta.movimientos.map((m) => (
                <tr key={m.id}>
                  <td className="whitespace-nowrap px-4 py-3 text-sm text-muted-foreground">
                    {m.fecha}
                  </td>
                  <td className="px-4 py-3">
                    <p className="text-sm font-medium text-foreground">{NOMBRE_TIPO[m.tipo]}</p>
                    {m.descripcion && (
                      <p className="text-xs text-muted-foreground">{m.descripcion}</p>
                    )}
                  </td>
                  <td
                    className={cn(
                      "whitespace-nowrap px-4 py-3 text-right text-sm font-medium tabular-nums",
                      m.monto < 0 ? "text-primary" : "text-foreground",
                    )}
                  >
                    {m.monto < 0 ? "−" : ""}Bs. {Math.abs(m.monto).toFixed(2)}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      <OperacionDialog
        key={operacion ?? "cerrado"}
        operacion={operacion}
        carnet={carnet}
        saldo={cuenta.saldo}
        cargos={cuenta.cargos ?? []}
        onClose={() => setOperacion(null)}
        onSuccess={alRegistrar}
      />
    </div>
  )
}

interface OperacionDialogProps {
  operacion: Operacion | null
  carnet: string
  saldo: number
  cargos: CargoPendiente[]
  onClose: () => void
  onSuccess: (cuenta: EstadoCuenta) => void
}

const GENERAL = "general"
const NOMBRE_CARGO: Record<string, string> = {
  MULTA_ATRASO: "Multa", REPOSICION: "Reposición", AJUSTE: "Ajuste",
}

function OperacionDialog({ operacion, carnet, saldo, cargos, onClose, onSuccess }: OperacionDialogProps) {
  const [monto, setMonto] = useState(saldo.toFixed(2))
  // Condonar una reposición concreta evita reintegrarla si el ejemplar aparece.
  const [cargo, setCargo] = useState(GENERAL)
  const elegido = cargos.find((c) => String(c.id) === cargo)
  const tope = elegido ? elegido.pendiente : saldo
  const [texto, setTexto] = useState("")
  const [enviando, setEnviando] = useState(false)
  const esPago = operacion === "pago"

  async function enviar(e: React.FormEvent) {
    e.preventDefault()
    setEnviando(true)
    try {
      const ruta = `/users/${encodeURIComponent(carnet)}/account/${esPago ? "payments" : "waivers"}`
      const cuerpo = esPago
        ? { monto: Number(monto), descripcion: texto.trim() || undefined }
        : { monto: Number(monto), motivo: texto.trim(), cargo_id: elegido?.id ?? null }
      const cuenta = await apiPost<EstadoCuenta>(ruta, cuerpo)
      toast.success(esPago ? "Pago registrado" : "Deuda condonada", {
        description: `Saldo actual: Bs. ${cuenta.saldo.toFixed(2)}`,
      })
      onSuccess(cuenta)
    } catch (error) {
      toast.error(esPago ? "No se pudo registrar el pago" : "No se pudo condonar", {
        description: mensajeDeError(error),
      })
    } finally {
      setEnviando(false)
    }
  }

  return (
    <Dialog open={operacion !== null} onOpenChange={(abierto) => !abierto && onClose()}>
      <DialogContent className="sm:max-w-md">
        <form onSubmit={enviar} className="space-y-4">
          <DialogHeader>
            <DialogTitle>{esPago ? "Registrar pago" : "Condonar deuda"}</DialogTitle>
            <DialogDescription>
              Deuda actual: Bs. {saldo.toFixed(2)}.{" "}
              {esPago
                ? "Puede ser un pago parcial."
                : "La condonación queda registrada con su motivo."}
            </DialogDescription>
          </DialogHeader>

          {!esPago && cargos.length > 0 && (
            <div className="space-y-2">
              <Label htmlFor="cargo">Aplicar a</Label>
              <Select
                value={cargo}
                onValueChange={(v) => {
                  setCargo(v)
                  const c = cargos.find((x) => String(x.id) === v)
                  setMonto((c ? c.pendiente : saldo).toFixed(2))
                }}
              >
                <SelectTrigger id="cargo" className="w-full"><SelectValue /></SelectTrigger>
                <SelectContent>
                  <SelectItem value={GENERAL}>La deuda en general</SelectItem>
                  {cargos.map((c) => (
                    <SelectItem key={c.id} value={String(c.id)}>
                      {NOMBRE_CARGO[c.tipo] ?? c.tipo} · Bs. {c.pendiente.toFixed(2)}
                      {c.descripcion ? ` · ${c.descripcion}` : ""}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
          )}

          <div className="space-y-2">
            <Label htmlFor="monto">Monto (Bs.)</Label>
            <Input
              id="monto"
              type="number"
              inputMode="decimal"
              min="0.01"
              max={tope}
              step="0.01"
              required
              value={monto}
              onChange={(e) => setMonto(e.target.value)}
            />
          </div>
          <div className="space-y-2">
            <Label htmlFor="detalle">{esPago ? "Nota (opcional)" : "Motivo"}</Label>
            <Input
              id="detalle"
              required={!esPago}
              minLength={esPago ? undefined : 3}
              placeholder={esPago ? "Pago en mostrador" : "Ej.: error en la fecha de devolución"}
              value={texto}
              onChange={(e) => setTexto(e.target.value)}
            />
          </div>

          <DialogFooter>
            <Button type="button" variant="outline" onClick={onClose} disabled={enviando}>
              Cancelar
            </Button>
            <Button type="submit" disabled={enviando}>
              {enviando && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}
              {esPago ? "Registrar pago" : "Condonar"}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  )
}
