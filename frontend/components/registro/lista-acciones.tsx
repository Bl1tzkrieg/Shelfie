"use client"

import { Fragment, useState } from "react"
import Link from "next/link"
import { ChevronDown, ChevronRight } from "lucide-react"

import { Button } from "@/components/ui/button"
import type { AccionRegistrada } from "@/lib/types"
import { cn } from "@/lib/utils"

/** Nombre corto de cada módulo del registro; uno que falte se muestra con su clave. */
export const NOMBRE_MODULO: Record<string, string> = {
  catalogo: "Catálogo",
  configuracion: "Configuración",
  sesion: "Sesiones",
  respaldo: "Respaldo",
}

type Cambios = Record<string, [unknown, unknown]>

function texto(valor: unknown) {
  if (valor === null || valor === undefined || valor === "") return "—"
  if (typeof valor === "boolean") return valor ? "Sí" : "No"
  if (typeof valor === "object") return JSON.stringify(valor)
  return String(valor)
}

/** El detalle de una anotación: los cambios campo por campo y el resto de los datos. */
function Detalle({ fila }: { fila: AccionRegistrada }) {
  const { cambios, ...resto } = (fila.datos ?? {}) as { cambios?: Cambios } & Record<string, unknown>
  const otros = Object.entries(resto)
  return (
    <div className="space-y-3 text-sm">
      {cambios && Object.keys(cambios).length > 0 && (
        <table className="w-full max-w-2xl text-left">
          <thead>
            <tr className="text-xs text-muted-foreground">
              <th className="py-1 pr-4 font-medium">Campo</th>
              <th className="py-1 pr-4 font-medium">Antes</th>
              <th className="py-1 font-medium">Después</th>
            </tr>
          </thead>
          <tbody>
            {Object.entries(cambios).map(([campo, [antes, despues]]) => (
              <tr key={campo} className="align-top">
                <td className="py-1 pr-4 font-mono text-xs">{campo}</td>
                <td className="py-1 pr-4 text-muted-foreground line-through decoration-muted-foreground/40">{texto(antes)}</td>
                <td className="py-1 text-foreground">{texto(despues)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
      {otros.length > 0 && (
        <details>
          <summary className="cursor-pointer text-xs text-muted-foreground">Datos guardados</summary>
          <pre className="mt-2 max-h-72 overflow-auto rounded bg-muted p-3 text-xs">{JSON.stringify(resto, null, 2)}</pre>
        </details>
      )}
      <p className="text-xs text-muted-foreground">
        {fila.ip && <>IP {fila.ip} · </>}Anotación n.º {fila.id}
      </p>
    </div>
  )
}

/** Lista de acciones del registro. `compacta`: para el historial dentro de una ficha. */
export function ListaAcciones({ filas, compacta = false }: { filas: AccionRegistrada[]; compacta?: boolean }) {
  const [abierta, setAbierta] = useState<number | null>(null)
  if (filas.length === 0) {
    return <p className="py-8 text-center text-sm text-muted-foreground">No hay acciones registradas.</p>
  }
  return (
    <div className="overflow-x-auto">
      <table className="w-full min-w-[640px]">
        <thead>
          <tr className="border-b border-border bg-muted/50 text-left text-sm text-muted-foreground">
            <th className="w-8 px-2 py-2" />
            <th className="px-3 py-2 font-medium">Cuándo</th>
            <th className="px-3 py-2 font-medium">Quién</th>
            <th className="px-3 py-2 font-medium">Qué</th>
            {!compacta && <th className="px-3 py-2 font-medium">Sobre</th>}
          </tr>
        </thead>
        <tbody className="divide-y divide-border">
          {filas.map((f) => {
            const detalle = !!f.datos || !!f.ip
            const expandida = abierta === f.id
            return (
              <Fragment key={f.id}>
                <tr className={cn("align-top", detalle && "cursor-pointer hover:bg-muted/30")}
                    onClick={() => detalle && setAbierta(expandida ? null : f.id)}>
                  <td className="px-2 py-3">
                    {detalle && (
                      <Button variant="ghost" size="icon" className="h-6 w-6"
                              aria-label={expandida ? "Ocultar el detalle" : "Ver el detalle"}
                              aria-expanded={expandida}>
                        {expandida ? <ChevronDown className="h-4 w-4" /> : <ChevronRight className="h-4 w-4" />}
                      </Button>
                    )}
                  </td>
                  <td className="whitespace-nowrap px-3 py-3 text-sm tabular-nums text-muted-foreground">{f.fecha}</td>
                  <td className="px-3 py-3 text-sm">
                    <p className="text-foreground">{f.actor}</p>
                  </td>
                  <td className="px-3 py-3 text-sm">
                    <p className="text-xs font-medium uppercase tracking-wide text-muted-foreground">
                      {NOMBRE_MODULO[f.modulo] ?? f.modulo} · {f.accion_nombre}
                    </p>
                    <p className="text-foreground">{f.descripcion}</p>
                  </td>
                  {!compacta && (
                    <td className="px-3 py-3 text-sm">
                      {f.usuario_afectado && <p className="text-foreground">{f.usuario_afectado}</p>}
                      {f.biblio_id && f.titulo && (
                        <Link href={`/libro/?id=${f.biblio_id}`} onClick={(e) => e.stopPropagation()}
                              className="block truncate text-primary hover:underline">{f.titulo}</Link>
                      )}
                      {f.codigo_barras && <p className="font-mono text-xs text-muted-foreground">{f.codigo_barras}</p>}
                    </td>
                  )}
                </tr>
                {expandida && (
                  <tr className="bg-muted/20">
                    <td />
                    <td colSpan={compacta ? 3 : 4} className="px-3 pb-4 pt-1"><Detalle fila={f} /></td>
                  </tr>
                )}
              </Fragment>
            )
          })}
        </tbody>
      </table>
    </div>
  )
}
