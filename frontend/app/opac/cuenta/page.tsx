"use client"

import { Suspense, useEffect, useState } from "react"
import { usePathname, useRouter, useSearchParams } from "next/navigation"
import { KeyRound, Loader2 } from "lucide-react"

import { CambiarClaveDialog } from "@/components/auth/cambiar-clave-dialog"
import { ClaveObligatoria } from "@/components/auth/clave-obligatoria"
import { AvisosLector } from "@/components/opac/cuenta/avisos-lector"
import { HistorialLector } from "@/components/opac/cuenta/historial-lector"
import { ListasLector } from "@/components/opac/cuenta/listas-lector"
import { MultasLector } from "@/components/opac/cuenta/multas-lector"
import { PrestamosLector } from "@/components/opac/cuenta/prestamos-lector"
import { ReservasLector } from "@/components/opac/cuenta/reservas-lector"
import { SugerenciasLector } from "@/components/opac/cuenta/sugerencias-lector"
import { rutaDeEntrada, useLector } from "@/components/opac/lector-provider"
import { Button } from "@/components/ui/button"
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs"
import { formatoBs } from "@/lib/opac"

const VISTAS = ["prestamos", "reservas", "multas", "historial", "listas", "sugerencias", "avisos"] as const
type Vista = (typeof VISTAS)[number]

export default function CuentaPage() {
  return (
    <Suspense fallback={null}>
      <Cuenta />
    </Suspense>
  )
}

function Cuenta() {
  const router = useRouter()
  const pathname = usePathname()
  const params = useSearchParams()
  const { lector, cargando, errorDeConexion, recargar, salir } = useLector()
  const [cambiandoClave, setCambiandoClave] = useState(false)
  const pedida = params.get("vista")
  const vista: Vista = VISTAS.find((v) => v === pedida) ?? "prestamos"

  useEffect(() => {
    if (!cargando && !lector && !errorDeConexion) {
      const actual = params.toString() ? `${pathname}?${params}` : pathname
      router.replace(rutaDeEntrada(actual))
    }
  }, [cargando, lector, errorDeConexion, pathname, params, router])

  if (!lector && errorDeConexion && !cargando) {
    return (
      <div role="alert" className="mx-auto mt-12 max-w-md space-y-3 text-center">
        <p className="font-medium text-foreground">No pudimos abrir tu cuenta</p>
        <p className="text-sm text-muted-foreground">{errorDeConexion}</p>
        <Button variant="outline" onClick={() => void recargar()}>Reintentar</Button>
      </div>
    )
  }
  if (!lector) return <Loader2 className="mx-auto mt-12 h-6 w-6 animate-spin text-muted-foreground" />
  if (lector.debe_cambiar_clave) {
    return (
      <ClaveObligatoria nombre={lector.nombre} ruta="/opac/account/password" pantallaCompleta={false}
                        onListo={() => void recargar()} onSalir={() => void salir()} />
    )
  }

  const contadores: Partial<Record<Vista, number>> = {
    prestamos: lector.prestamos,
    reservas: lector.reservas,
  }

  return (
    <div className="space-y-6">
      <header className="flex flex-wrap items-start justify-between gap-4">
        <div>
          <h1 className="text-2xl font-semibold text-foreground">Hola, {lector.nombre}</h1>
          <p className="text-sm text-muted-foreground">
            {[`Carnet ${lector.carnet}`, lector.categoria, lector.sede].filter(Boolean).join(" · ")}
          </p>
        </div>
        <Button variant="outline" size="sm" onClick={() => setCambiandoClave(true)}>
          <KeyRound className="mr-2 h-4 w-4" /> Cambiar contraseña
        </Button>
      </header>

      {(lector.para_retirar > 0 || lector.vencidos > 0 || lector.bloqueado) && (
        <ul className="space-y-2 text-sm">
          {lector.para_retirar > 0 && (
            <li className="rounded-md border border-accent/50 bg-accent/10 px-4 py-2">
              {lector.para_retirar === 1 ? "Una reserva está lista" : `${lector.para_retirar} reservas están listas`} para retirar.
            </li>
          )}
          {lector.vencidos > 0 && (
            <li className="rounded-md border border-destructive/40 bg-destructive/5 px-4 py-2 text-destructive">
              Tienes {lector.vencidos} préstamo{lector.vencidos === 1 ? "" : "s"} vencido{lector.vencidos === 1 ? "" : "s"}: cada día de atraso suma multa.
            </li>
          )}
          {lector.bloqueado && (
            <li className="rounded-md border border-destructive/40 bg-destructive/5 px-4 py-2 text-destructive">
              Debes {formatoBs(lector.saldo)}. Hasta pagar en la biblioteca no puedes renovar ni reservar.
            </li>
          )}
        </ul>
      )}

      <Tabs value={vista} onValueChange={(v) => router.replace(`${pathname}?vista=${v}`, { scroll: false })}>
        <div className="-mx-4 overflow-x-auto px-4 sm:mx-0 sm:px-0">
          <TabsList>
            {VISTAS.map((v) => (
              <TabsTrigger key={v} value={v}>
                {{ prestamos: "Préstamos", reservas: "Reservas", multas: "Multas", historial: "Historial",
                   listas: "Mis listas", sugerencias: "Sugerencias", avisos: "Avisos" }[v]}
                {contadores[v] ? <span className="ml-1.5 tabular-nums text-muted-foreground">{contadores[v]}</span> : null}
              </TabsTrigger>
            ))}
          </TabsList>
        </div>
        <TabsContent value="prestamos" className="pt-4"><PrestamosLector /></TabsContent>
        <TabsContent value="reservas" className="pt-4"><ReservasLector /></TabsContent>
        <TabsContent value="multas" className="pt-4"><MultasLector /></TabsContent>
        <TabsContent value="historial" className="pt-4"><HistorialLector /></TabsContent>
        <TabsContent value="listas" className="pt-4"><ListasLector /></TabsContent>
        <TabsContent value="sugerencias" className="pt-4"><SugerenciasLector /></TabsContent>
        <TabsContent value="avisos" className="pt-4"><AvisosLector /></TabsContent>
      </Tabs>

      <CambiarClaveDialog open={cambiandoClave} onOpenChange={setCambiandoClave} ruta="/opac/account/password" />
    </div>
  )
}
