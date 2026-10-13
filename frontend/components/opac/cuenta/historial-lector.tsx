"use client"

import { useEffect, useState } from "react"
import Link from "next/link"
import { Loader2 } from "lucide-react"
import { toast } from "sonner"

import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table"
import { apiGet, mensajeDeError } from "@/lib/api"
import type { HistorialLector as Fila } from "@/lib/opac"

export function HistorialLector() {
  const [filas, setFilas] = useState<Fila[] | null>(null)

  useEffect(() => {
    apiGet<Fila[]>("/opac/account/history")
      .then(setFilas)
      .catch((e) => toast.error("No se pudo cargar tu historial", { description: mensajeDeError(e) }))
  }, [])

  if (!filas) return <Loader2 className="mx-auto my-8 h-5 w-5 animate-spin text-muted-foreground" />
  if (filas.length === 0) return <p className="py-8 text-center text-muted-foreground">Aún no has devuelto nada.</p>

  return (
    <div className="overflow-x-auto rounded-lg border border-border bg-card">
      <Table>
        <TableHeader>
          <TableRow>
            <TableHead>Título</TableHead>
            <TableHead>Prestado</TableHead>
            <TableHead>Devuelto</TableHead>
          </TableRow>
        </TableHeader>
        <TableBody>
          {filas.map((f) => (
            <TableRow key={f.id}>
              <TableCell className="max-w-md">
                <Link href={`/opac/registro/${f.biblio_id}`} className="font-medium hover:text-primary hover:underline">{f.titulo}</Link>
                {f.autor && <span className="block text-xs text-muted-foreground">{f.autor}</span>}
              </TableCell>
              <TableCell className="whitespace-nowrap tabular-nums">{f.prestado}</TableCell>
              <TableCell className="whitespace-nowrap tabular-nums">{f.perdido ? "Declarado perdido" : f.devuelto}</TableCell>
            </TableRow>
          ))}
        </TableBody>
      </Table>
    </div>
  )
}
