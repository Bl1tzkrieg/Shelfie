"use client"

import { useEffect, useState } from "react"
import Link from "next/link"
import { useRouter } from "next/navigation"
import { Search } from "lucide-react"

import { FondoGeometrico } from "@/components/layout/fondo-geometrico"
import { useLector } from "@/components/opac/lector-provider"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { apiGet } from "@/lib/api"

export default function OpacInicio() {
  const router = useRouter()
  const { lector } = useLector()
  const [texto, setTexto] = useState("")
  const [materias, setMaterias] = useState<string[]>([])

  useEffect(() => {
    apiGet<string[]>("/opac/subjects").then(setMaterias).catch(() => setMaterias([]))
  }, [])

  return (
    <div className="space-y-10">
      <section className="relative isolate overflow-hidden rounded-2xl px-5 pb-8 pt-10 text-hero-foreground shadow-papel-flotante sm:px-10 sm:pb-12 sm:pt-16">
        <FondoGeometrico />
        <div className="max-w-2xl">
          <h1 className="text-balance text-3xl/tight font-semibold tracking-tight sm:text-4xl/tight">
            ¿Qué quieres leer?
          </h1>
          {/* Solo lo que el OPAC hace: buscar, ver los ejemplares libres por sede y, con la
              cuenta del lector, reservar y renovar. */}
          <p className="mt-3 text-pretty text-base text-hero-muted sm:text-lg">
            Busca por título, autor, materia o ISBN y mira cuántos ejemplares hay libres en cada
            sede. Con tu carnet puedes reservar y renovar tus préstamos.
          </p>
        </div>
        <form
          role="search"
          className="mt-8 flex flex-col gap-2 rounded-xl bg-card p-2 text-card-foreground shadow-papel-flotante sm:flex-row lg:max-w-2xl"
          onSubmit={(e) => {
            e.preventDefault()
            router.push(`/opac/buscar?q=${encodeURIComponent(texto.trim())}`)
          }}
        >
          <div className="relative flex-1">
            <Search className="pointer-events-none absolute left-3 top-1/2 h-5 w-5 -translate-y-1/2 text-primary" />
            <Input
              autoFocus
              aria-label="Buscar en el catálogo"
              placeholder="Título, autor, materia o ISBN"
              className="h-12 border-transparent pl-10 text-base shadow-none"
              value={texto}
              onChange={(e) => setTexto(e.target.value)}
            />
          </div>
          <Button type="submit" size="lg" className="h-12">Buscar</Button>
        </form>
      </section>

      {lector && (lector.para_retirar > 0 || lector.vencidos > 0) && (
        <section className="max-w-2xl rounded-xl border border-aviso/40 bg-aviso/10 p-4 text-sm shadow-papel">
          {lector.para_retirar > 0 && (
            <p>
              <strong>{lector.para_retirar === 1 ? "Una reserva te espera" : `${lector.para_retirar} reservas te esperan`}</strong>{" "}
              en la biblioteca.
            </p>
          )}
          {lector.vencidos > 0 && (
            <p>
              Tienes <strong>{lector.vencidos} préstamo{lector.vencidos === 1 ? "" : "s"} vencido{lector.vencidos === 1 ? "" : "s"}</strong>.
            </p>
          )}
          <Link href="/opac/cuenta" className="mt-1 inline-block font-medium text-primary hover:underline">
            Ver mi cuenta
          </Link>
        </section>
      )}

      {materias.length > 0 && (
        <section aria-labelledby="materias">
          <h2 id="materias" className="mb-4 text-sm font-semibold uppercase tracking-wide text-muted-foreground">
            Explorar por materia
          </h2>
          <ul className="flex flex-wrap gap-2">
            {materias.map((m) => (
              <li key={m}>
                <Link
                  href={`/opac/buscar?materia=${encodeURIComponent(m)}`}
                  className="inline-block rounded-full border border-border bg-card px-3 py-1.5 text-sm text-foreground shadow-papel transition-colors hover:border-primary hover:text-primary"
                >
                  {m}
                </Link>
              </li>
            ))}
          </ul>
        </section>
      )}
    </div>
  )
}
