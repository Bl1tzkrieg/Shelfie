"use client"

import { KeyRound } from "lucide-react"

import { CamposDeClave, MINIMO_CLAVE } from "@/components/auth/cambiar-clave-dialog"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"

/**
 * Pantalla que aparece cuando la contraseña es la provisional (el usuario, o la que
 * puso el administrador al restablecerla). El backend no deja hacer nada más hasta cambiarla.
 */
export function ClaveObligatoria({ nombre, ruta, onListo, onSalir, pantallaCompleta = true }: {
  nombre: string
  ruta: string
  onListo: () => void
  onSalir: () => void
  /** Ocupa toda la pantalla salvo que se muestre dentro de otro marco. */
  pantallaCompleta?: boolean
}) {
  return (
    <div className={pantallaCompleta
      ? "flex min-h-screen items-center justify-center bg-background p-4"
      : "flex justify-center px-4 py-12"}>
      <Card className="w-full max-w-sm">
        <CardHeader>
          <KeyRound className="mb-2 h-8 w-8 text-primary" aria-hidden />
          <CardTitle>Elige tu contraseña, {nombre}</CardTitle>
          <CardDescription>
            La que usaste es provisional. Escribe una nueva de al menos {MINIMO_CLAVE} caracteres,
            distinta del usuario, para seguir.
          </CardDescription>
        </CardHeader>
        <CardContent>
          <CamposDeClave ruta={ruta} onListo={onListo} textoBoton="Guardar y seguir" />
          <Button variant="link" className="mt-2 w-full text-muted-foreground" onClick={onSalir}>
            Salir sin cambiarla
          </Button>
        </CardContent>
      </Card>
    </div>
  )
}
