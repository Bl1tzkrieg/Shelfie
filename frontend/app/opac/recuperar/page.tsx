"use client"

import { Suspense, useEffect, useState } from "react"
import Link from "next/link"
import { useRouter, useSearchParams } from "next/navigation"
import { Loader2, MailCheck } from "lucide-react"
import { toast } from "sonner"

import { MINIMO_CLAVE } from "@/components/auth/cambiar-clave-dialog"
import { PanelEntrada } from "@/components/opac/panel-entrada"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { apiGet, apiPost, mensajeDeError } from "@/lib/api"

/** Sin token: pedir el enlace por correo. Con token: elegir la contraseña nueva. */
export default function RecuperarPage() {
  return (
    <Suspense fallback={null}>
      <Recuperar />
    </Suspense>
  )
}

function Recuperar() {
  const token = useSearchParams().get("token")
  return (
    <PanelEntrada>
      {token ? <NuevaClave token={token} /> : <PedirEnlace />}
    </PanelEntrada>
  )
}

function PedirEnlace() {
  const [identificador, setIdentificador] = useState("")
  const [enviando, setEnviando] = useState(false)
  const [enviado, setEnviado] = useState(false)

  async function enviar(e: React.FormEvent) {
    e.preventDefault()
    setEnviando(true)
    try {
      await apiPost("/opac/password/forgot", { identificador: identificador.trim() })
      setEnviado(true)
    } catch (err) {
      toast.error("No se pudo enviar", { description: mensajeDeError(err) })
    } finally {
      setEnviando(false)
    }
  }

  if (enviado) {
    return (
      <div className="space-y-3 text-center">
        <MailCheck className="mx-auto h-10 w-10 text-primary" />
        <h1 className="text-xl font-semibold text-foreground">Revisa tu correo</h1>
        <p className="text-sm text-muted-foreground">
          Si el carnet está registrado, te llegará un enlace para elegir una contraseña nueva. Vale
          una hora y se usa una sola vez.
        </p>
        <p className="text-sm text-muted-foreground">
          ¿No llega? Revisa el correo no deseado o pide en la biblioteca que la restablezcan.
        </p>
        <Link href="/opac/entrar" className="inline-block text-sm font-medium text-primary hover:underline">
          Volver a entrar
        </Link>
      </div>
    )
  }

  return (
    <>
      <h1 className="text-xl font-semibold text-foreground">Recupera tu contraseña</h1>
      <p className="mt-1 text-sm text-muted-foreground">
        Te mandamos un enlace al correo registrado en la biblioteca.
      </p>
      <form onSubmit={enviar} className="mt-6 space-y-4">
        <div className="space-y-2">
          <Label htmlFor="recuperar-carnet">Carnet o usuario</Label>
          <Input id="recuperar-carnet" autoComplete="username" autoFocus required
                 value={identificador} onChange={(e) => setIdentificador(e.target.value)} />
        </div>
        <Button type="submit" className="w-full" disabled={enviando || !identificador.trim()}>
          {enviando && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}
          Enviar el enlace
        </Button>
      </form>
      <Link href="/opac/entrar" className="mt-6 inline-block text-sm text-muted-foreground hover:text-foreground hover:underline">
        ← Volver a entrar
      </Link>
    </>
  )
}

function NuevaClave({ token }: { token: string }) {
  const router = useRouter()
  const [estado, setEstado] = useState<"verificando" | "valido" | "invalido">("verificando")
  const [nombre, setNombre] = useState("")
  const [nueva, setNueva] = useState("")
  const [repetida, setRepetida] = useState("")
  const [enviando, setEnviando] = useState(false)
  const coinciden = nueva === repetida

  useEffect(() => {
    apiGet<{ nombre: string }>(`/opac/password/reset?token=${encodeURIComponent(token)}`)
      .then((r) => {
        setNombre(r.nombre)
        setEstado("valido")
      })
      .catch(() => setEstado("invalido"))
  }, [token])

  async function guardar(e: React.FormEvent) {
    e.preventDefault()
    setEnviando(true)
    try {
      await apiPost("/opac/password/reset", { token, nueva })
      toast.success("Contraseña cambiada", { description: "Ya puedes entrar con la nueva." })
      router.replace("/opac/entrar")
    } catch (err) {
      toast.error("No se pudo cambiar", { description: mensajeDeError(err) })
      setEnviando(false)
    }
  }

  if (estado === "verificando") return <Loader2 className="mx-auto my-6 h-6 w-6 animate-spin text-muted-foreground" />
  if (estado === "invalido") {
    return (
      <div className="space-y-3 text-center">
        <h1 className="text-xl font-semibold text-foreground">El enlace ya no sirve</h1>
        <p className="text-sm text-muted-foreground">
          Venció, ya se usó o se pidió uno más nuevo. Pide otro y usa el último que te llegue.
        </p>
        <Button asChild variant="outline"><Link href="/opac/recuperar">Pedir un enlace nuevo</Link></Button>
      </div>
    )
  }

  return (
    <>
      <h1 className="text-xl font-semibold text-foreground">Hola, {nombre}</h1>
      <p className="mt-1 text-sm text-muted-foreground">
        Elige tu contraseña nueva: al menos {MINIMO_CLAVE} caracteres y distinta de tu carnet.
      </p>
      <form onSubmit={guardar} className="mt-6 space-y-4">
        <div className="space-y-2">
          <Label htmlFor="clave-nueva">Contraseña nueva</Label>
          <Input id="clave-nueva" type="password" autoComplete="new-password" autoFocus required
                 minLength={MINIMO_CLAVE} value={nueva} onChange={(e) => setNueva(e.target.value)} />
        </div>
        <div className="space-y-2">
          <Label htmlFor="clave-repetida">Repite la nueva</Label>
          <Input id="clave-repetida" type="password" autoComplete="new-password" required
                 value={repetida} onChange={(e) => setRepetida(e.target.value)}
                 aria-invalid={repetida !== "" && !coinciden} />
          {repetida !== "" && !coinciden && <p className="text-xs text-destructive">No coincide con la nueva.</p>}
        </div>
        <Button type="submit" className="w-full" disabled={enviando || nueva.length < MINIMO_CLAVE || !coinciden}>
          {enviando && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}
          Guardar contraseña
        </Button>
      </form>
    </>
  )
}
