"use client"

import { Suspense, useEffect, useState } from "react"
import Link from "next/link"
import { useRouter, useSearchParams } from "next/navigation"
import { Loader2 } from "lucide-react"

import { useLector } from "@/components/opac/lector-provider"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { mensajeDeError } from "@/lib/api"

/** Solo rutas del OPAC: ?next= no puede mandar a otro sitio ni a la intranet. */
function destinoSeguro(next: string | null) {
  return next && next.startsWith("/opac") && !next.startsWith("//") ? next : "/opac/cuenta"
}

export default function EntrarPage() {
  return (
    <Suspense fallback={null}>
      <Formulario />
    </Suspense>
  )
}

function Formulario() {
  const router = useRouter()
  const destino = destinoSeguro(useSearchParams().get("next"))
  const { lector, cargando, entrar } = useLector()
  const [carnet, setCarnet] = useState("")
  const [clave, setClave] = useState("")
  const [enviando, setEnviando] = useState(false)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    // Con la contraseña provisional se va primero a la cuenta, donde se pide la nueva.
    if (!cargando && lector) router.replace(lector.debe_cambiar_clave ? "/opac/cuenta" : destino)
  }, [cargando, lector, destino, router])

  async function enviar(e: React.FormEvent) {
    e.preventDefault()
    setEnviando(true)
    setError(null)
    try {
      const resumen = await entrar(carnet.trim(), clave)
      router.replace(resumen.debe_cambiar_clave ? "/opac/cuenta" : destino)
    } catch (err) {
      setError(mensajeDeError(err))
      setEnviando(false)
    }
  }

  return (
    <div className="mx-auto max-w-sm py-8">
      <div className="rounded-xl border border-border bg-card p-8 shadow-sm">
        <h1 className="text-xl font-semibold text-foreground">Entra a tu cuenta</h1>
        <p className="mt-1 text-sm text-muted-foreground">
          Renueva tus préstamos, reserva y revisa tu historial.
        </p>
        <form onSubmit={enviar} className="mt-6 space-y-4">
          <div className="space-y-2">
            <Label htmlFor="carnet">Carnet</Label>
            <Input id="carnet" autoComplete="username" autoFocus required
                   value={carnet} onChange={(e) => setCarnet(e.target.value)} />
          </div>
          <div className="space-y-2">
            <Label htmlFor="clave">Contraseña</Label>
            <Input id="clave" type="password" autoComplete="current-password" required
                   value={clave} onChange={(e) => setClave(e.target.value)} />
          </div>
          {error && (
            <p role="alert" className="rounded-md bg-destructive/10 px-3 py-2 text-sm text-destructive">{error}</p>
          )}
          <Button type="submit" className="w-full" disabled={enviando}>
            {enviando && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}
            Entrar
          </Button>
        </form>
        <Link href="/opac/recuperar" className="mt-4 inline-block text-sm text-primary hover:underline">
          ¿Olvidaste tu contraseña?
        </Link>
        <p className="mt-4 text-xs text-muted-foreground">
          La primera vez, tu contraseña es tu número de carnet.
        </p>
        <p className="mt-4 border-t pt-4 text-xs text-muted-foreground">
          ¿Eres del personal?{" "}
          <a href="/login" className="font-medium text-primary hover:underline">Entra a la intranet</a>
        </p>
      </div>
    </div>
  )
}
