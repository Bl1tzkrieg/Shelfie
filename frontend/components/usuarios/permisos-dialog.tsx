"use client"

import { useEffect, useState } from "react"
import { Loader2 } from "lucide-react"
import { toast } from "sonner"

import { Button } from "@/components/ui/button"
import { Checkbox } from "@/components/ui/checkbox"
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog"
import { Label } from "@/components/ui/label"
import { Switch } from "@/components/ui/switch"
import { apiGet, apiPut, mensajeDeError } from "@/lib/api"
import { NOMBRE_PERMISO, type ApiUser, type CatalogoPermisos, type Permiso } from "@/lib/types"

interface PermisosDialogProps {
  usuario: ApiUser | null
  onClose: () => void
  onSuccess?: () => void
}

/** Da o quita acceso a la intranet y asigna permisos por módulo (solo superbibliotecarios). */
export function PermisosDialog({ usuario, onClose, onSuccess }: PermisosDialogProps) {
  const [catalogo, setCatalogo] = useState<CatalogoPermisos | null>(null)

  useEffect(() => {
    if (!usuario || catalogo) return
    apiGet<CatalogoPermisos>("/staff/permissions")
      .then(setCatalogo)
      .catch((error) =>
        toast.error("No se pudieron cargar los permisos", { description: mensajeDeError(error) }),
      )
  }, [usuario, catalogo])

  return (
    <Dialog open={usuario !== null} onOpenChange={(abierto) => !abierto && onClose()}>
      <DialogContent className="sm:max-w-lg">
        {usuario && (
          // El key reinicia el formulario con los valores de cada persona.
          <FormularioPermisos
            key={usuario.nro_carnet}
            usuario={usuario}
            catalogo={catalogo}
            onClose={onClose}
            onSuccess={onSuccess}
          />
        )}
      </DialogContent>
    </Dialog>
  )
}

interface FormularioPermisosProps {
  usuario: ApiUser
  catalogo: CatalogoPermisos | null
  onClose: () => void
  onSuccess?: () => void
}

function FormularioPermisos({ usuario, catalogo, onClose, onSuccess }: FormularioPermisosProps) {
  const [esPersonal, setEsPersonal] = useState(usuario.es_personal)
  const [seleccion, setSeleccion] = useState<Set<Permiso>>(() => new Set(usuario.permisos))
  const [guardando, setGuardando] = useState(false)

  function alternar(permiso: Permiso, marcado: boolean) {
    setSeleccion((actual) => {
      const nuevo = new Set(actual)
      if (marcado) nuevo.add(permiso)
      else nuevo.delete(permiso)
      return nuevo
    })
  }

  async function guardar() {
    setGuardando(true)
    try {
      await apiPut(`/staff/${encodeURIComponent(usuario.nro_carnet)}`, {
        es_personal: esPersonal,
        permisos: Array.from(seleccion),
      })
      toast.success("Permisos actualizados", {
        description: `${usuario.nombre} ${usuario.apellido}`,
      })
      onSuccess?.()
      onClose()
    } catch (error) {
      toast.error("No se pudieron guardar los permisos", { description: mensajeDeError(error) })
    } finally {
      setGuardando(false)
    }
  }

  const esTotal = seleccion.has("superbibliotecario")

  return (
    <>
      <DialogHeader>
        <DialogTitle>Acceso a la intranet</DialogTitle>
        <DialogDescription>
          {usuario.nombre} {usuario.apellido} · carnet {usuario.nro_carnet}
        </DialogDescription>
      </DialogHeader>

      <div className="flex items-center justify-between rounded-lg border border-border p-3">
        <div>
          <Label htmlFor="es-personal" className="font-medium">
            Es personal de la biblioteca
          </Label>
          <p className="text-sm text-muted-foreground">
            Puede iniciar sesión y consultar la intranet.
          </p>
        </div>
        <Switch id="es-personal" checked={esPersonal} onCheckedChange={setEsPersonal} />
      </div>

      {esPersonal && catalogo && (
        <div className="space-y-4">
          <div className="flex flex-wrap items-center gap-2">
            <span className="text-sm text-muted-foreground">Aplicar perfil:</span>
            {catalogo.perfiles.map((perfil) => (
              <Button
                key={perfil.codigo}
                type="button"
                variant="outline"
                size="sm"
                onClick={() => setSeleccion(new Set(perfil.permisos))}
              >
                {perfil.nombre}
              </Button>
            ))}
          </div>

          <div className="max-h-72 space-y-1 overflow-y-auto rounded-lg border border-border p-2">
            {catalogo.permisos.map((p) => {
              const incluidoPorTotal = esTotal && p.codigo !== "superbibliotecario"
              return (
                <label
                  key={p.codigo}
                  className="flex cursor-pointer items-start gap-3 rounded-md p-2 hover:bg-muted/50"
                >
                  <Checkbox
                    className="mt-0.5"
                    checked={seleccion.has(p.codigo) || incluidoPorTotal}
                    disabled={incluidoPorTotal}
                    onCheckedChange={(v) => alternar(p.codigo, v === true)}
                  />
                  <span>
                    <span className="block text-sm font-medium text-foreground">
                      {NOMBRE_PERMISO[p.codigo] ?? p.codigo}
                    </span>
                    <span className="block text-xs text-muted-foreground">{p.descripcion}</span>
                  </span>
                </label>
              )
            })}
          </div>
          {seleccion.size === 0 && (
            <p className="text-xs text-muted-foreground">
              Sin permisos marcados podrá consultar, pero no registrar ni modificar nada.
            </p>
          )}
        </div>
      )}

      <DialogFooter>
        <Button variant="outline" onClick={onClose} disabled={guardando}>
          Cancelar
        </Button>
        <Button onClick={guardar} disabled={guardando}>
          {guardando && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}
          Guardar
        </Button>
      </DialogFooter>
    </>
  )
}
