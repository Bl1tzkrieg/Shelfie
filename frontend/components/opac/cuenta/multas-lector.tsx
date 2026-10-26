"use client"

import { useEffect, useState } from "react"
import { Loader2 } from "lucide-react"
import { toast } from "sonner"

import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table"
import { apiGet, mensajeDeError } from "@/lib/api"
import { formatoBs, TIPOS_MOVIMIENTO, type MultasLector as Cuenta } from "@/lib/opac"
import { cn } from "@/lib/utils"

export function MultasLector() {
  const [cuenta, setCuenta] = useState<Cuenta | null>(null)

  useEffect(() => {
    apiGet<Cuenta>("/opac/account/charges")
      .then(setCuenta)
      .catch((e) => toast.error("No se pudo cargar tu cuenta", { description: mensajeDeError(e) }))
  }, [])

  if (!cuenta) return <Loader2 className="mx-auto my-8 h-5 w-5 animate-spin text-muted-foreground" />

  return (
    <div className="space-y-4">
      <div className={cn("rounded-lg border p-4",
                         cuenta.bloqueado ? "border-destructive/40 bg-destructive/5" : "border-border bg-card")}>
        <p className="text-sm text-muted-foreground">Debes</p>
        <p className={cn("text-2xl font-semibold tabular-nums", cuenta.saldo > 0 ? "text-foreground" : "text-primary")}>
          {formatoBs(Math.max(cuenta.saldo, 0))}
        </p>
        {cuenta.saldo < 0 && <p className="text-sm text-primary">Tienes {formatoBs(-cuenta.saldo)} a tu favor.</p>}
        {cuenta.bloqueado && (
          <p className="mt-1 text-sm text-destructive">
            Pasaste el máximo de {formatoBs(cuenta.umbral_bloqueo)}: no puedes pedir prestado, renovar ni
            reservar hasta pagar en la biblioteca.
          </p>
        )}
      </div>

      {cuenta.movimientos.length > 0 && (
        <div className="overflow-x-auto rounded-lg border border-border bg-card shadow-papel">
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Fecha</TableHead>
                <TableHead>Concepto</TableHead>
                <TableHead className="text-right">Monto</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {cuenta.movimientos.map((m) => (
                <TableRow key={m.id}>
                  <TableCell className="whitespace-nowrap tabular-nums">{m.fecha}</TableCell>
                  <TableCell>
                    {TIPOS_MOVIMIENTO[m.tipo] ?? m.tipo}
                    {m.descripcion && <span className="block text-xs text-muted-foreground">{m.descripcion}</span>}
                  </TableCell>
                  <TableCell className={cn("text-right tabular-nums", m.monto < 0 && "text-primary")}>
                    {m.monto < 0 ? `−${formatoBs(-m.monto)}` : formatoBs(m.monto)}
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </div>
      )}
    </div>
  )
}
