"use client"

import { useCallback, useEffect, useState } from "react"
import Link from "next/link"
import { useParams } from "next/navigation"
import { Globe, Loader2, Lock, X } from "lucide-react"
import { toast } from "sonner"

import { useLector } from "@/components/opac/lector-provider"
import { TituloResultado } from "@/components/opac/titulo-resultado"
import { Button } from "@/components/ui/button"
import { apiDelete, apiGet, mensajeDeError } from "@/lib/api"
import type { ListaConTitulos } from "@/lib/opac"

/** Una lista: la propia (con sesión) o una pública que alguien compartió. */
export default function ListaPage() {
  const { id } = useParams<{ id: string }>()
  const { lector, cargando } = useLector()
  const [lista, setLista] = useState<ListaConTitulos | null>(null)
  const [error, setError] = useState<string | null>(null)

  const cargar = useCallback(async () => {
    try {
      setLista(await apiGet<ListaConTitulos>(`/opac/lists/${id}`))
      setError(null)
    } catch (e) {
      setError(mensajeDeError(e))
    }
  }, [id])

  useEffect(() => {
    // Se espera a saber si hay sesión: una lista privada propia solo se ve con ella.
    if (!cargando) cargar()
  }, [cargando, lector, cargar])

  async function quitar(biblioId: string, titulo: string) {
    try {
      await apiDelete(`/opac/account/lists/${id}/titles/${biblioId}`)
      toast.success("Quitado de la lista", { description: titulo })
      await cargar()
    } catch (e) {
      toast.error("No se pudo quitar", { description: mensajeDeError(e) })
    }
  }

  if (error) {
    return (
      <div className="py-12 text-center">
        <p className="font-medium text-foreground">Esta lista no existe o es privada.</p>
        <Link href="/opac" className="mt-2 inline-block text-sm text-primary hover:underline">Ir al catálogo</Link>
      </div>
    )
  }
  if (!lista) return <Loader2 className="mx-auto mt-12 h-6 w-6 animate-spin text-muted-foreground" />

  return (
    <div className="space-y-6">
      {lista.propia && (
        <Link href="/opac/cuenta?vista=listas" className="text-sm text-muted-foreground hover:text-foreground hover:underline">
          ← Mis listas
        </Link>
      )}
      <header>
        <h1 className="text-2xl font-semibold text-foreground">{lista.nombre}</h1>
        <p className="mt-1 flex items-center gap-1.5 text-sm text-muted-foreground">
          {lista.publica ? <Globe className="h-3.5 w-3.5" /> : <Lock className="h-3.5 w-3.5" />}
          {lista.propia ? (lista.publica ? "Pública: la ve cualquiera con el enlace" : "Privada: solo tú la ves")
            : `Lista de ${lista.autor ?? "un lector"}`}
          {" · "}{lista.cantidad} título{lista.cantidad === 1 ? "" : "s"}
        </p>
      </header>
      {lista.titulos.length === 0 ? (
        <p className="text-muted-foreground">La lista está vacía. Agrega títulos desde su ficha en el catálogo.</p>
      ) : (
        <ul className="space-y-3">
          {lista.titulos.map((t) => (
            <TituloResultado key={t.id} titulo={t} acciones={lista.propia ? (
              <Button size="sm" variant="ghost" aria-label={`Quitar ${t.titulo}`} onClick={() => quitar(t.id, t.titulo)}>
                <X className="h-4 w-4" />
              </Button>
            ) : undefined} />
          ))}
        </ul>
      )}
    </div>
  )
}
