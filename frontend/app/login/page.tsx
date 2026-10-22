"use client"

import { Suspense, useEffect, useState } from "react"
import { useRouter, useSearchParams } from "next/navigation"
import Link from "next/link"
import { BookMarked, Loader2 } from "lucide-react"

import { useSesion } from "@/components/auth/sesion-provider"
import { FondoGeometrico } from "@/components/lite/fondo-geometrico"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { mensajeDeError } from "@/lib/api"

/** Solo rutas internas: evita que ?next= redirija a otro sitio. */
function destinoSeguro(next: string | null) {
  return next && next.startsWith("/") && !next.startsWith("//") ? next : "/"
}

export default function LoginPage() {
  return (
    <Suspense fallback={null}>
      <FormularioLogin />
    </Suspense>
  )
}

function FormularioLogin() {
  const router = useRouter()
  const searchParams = useSearchParams()
  const { usuario, cargando, iniciarSesion } = useSesion()
  const destino = destinoSeguro(searchParams.get("next"))

  const [username, setUsername] = useState("")
  const [password, setPassword] = useState("")
  const [enviando, setEnviando] = useState(false)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    if (!cargando && usuario) router.replace(destino)
  }, [cargando, usuario, destino, router])

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault()
    if (enviando) return
    setEnviando(true)
    setError(null)
    try {
      await iniciarSesion(username.trim(), password)
      router.replace(destino)
    } catch (err) {
      setError(mensajeDeError(err))
      setEnviando(false)
    }
  }

  return (
    <div className="relative isolate flex min-h-screen items-center justify-center overflow-hidden p-4">
      <FondoGeometrico pantalla />
      <div className="w-full max-w-sm rounded-2xl border border-white/10 bg-card p-8 shadow-papel-flotante">
        <div className="mb-6 flex flex-col items-center gap-3 text-center">
          <div className="flex h-12 w-12 items-center justify-center rounded-xl bg-hero shadow-papel-alzado">
            <BookMarked className="h-6 w-6 text-sidebar-primary" aria-hidden />
          </div>
          <div>
            <h1 className="text-xl font-semibold text-foreground">Shelfie</h1>
            <p className="text-sm text-muted-foreground">Intranet de la biblioteca</p>
          </div>
        </div>

        <form onSubmit={handleSubmit} className="space-y-4">
          <div className="space-y-2">
            <Label htmlFor="username">Usuario</Label>
            <Input
              id="username"
              autoComplete="username"
              autoFocus
              required
              value={username}
              onChange={(e) => setUsername(e.target.value)}
            />
          </div>
          <div className="space-y-2">
            <Label htmlFor="password">Contraseña</Label>
            <Input
              id="password"
              type="password"
              autoComplete="current-password"
              required
              value={password}
              onChange={(e) => setPassword(e.target.value)}
            />
          </div>

          {error && (
            <p
              role="alert"
              className="rounded-md bg-destructive/10 px-3 py-2 text-sm text-destructive"
            >
              {error}
            </p>
          )}

          <Button type="submit" className="w-full" disabled={enviando}>
            {enviando && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}
            Entrar
          </Button>
        </form>
        <p className="mt-4 text-center text-sm text-muted-foreground">
          ¿Olvidaste tu contraseña? Pídele al administrador que la restablezca.
        </p>
        <p className="mt-6 text-center text-sm">
          <Link href="/" className="font-medium text-primary hover:underline">Volver a la búsqueda</Link>
        </p>
      </div>
    </div>
  )
}
