"use client"

import { useEffect, useState } from "react"
import { Loader2 } from "lucide-react"
import { toast } from "sonner"

import { Button } from "@/components/ui/button"
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select"
import { apiGet, apiPost, apiPut, mensajeDeError } from "@/lib/api"
import { useSedes } from "@/components/layout/sede-provider"
import type { ApiUser, Categoria } from "@/lib/types"

interface UsuarioDialogProps {
  open: boolean
  onOpenChange: (open: boolean) => void
  /** Presente en modo edición; ausente en alta. */
  usuario?: ApiUser | null
  onSuccess?: () => void
}

const VACIO = {
  nro_carnet: "",
  nombre: "",
  apellido: "",
  email: "",
  departamento: "",
  categoria_codigo: "EST",
  /** "" = la propuesta (la sede de trabajo actual); "ninguna" = sin sede. */
  biblioteca_id: "",
}

export function UsuarioDialog({
  open,
  onOpenChange,
  usuario,
  onSuccess,
}: UsuarioDialogProps) {
  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-lg">
        {/* La key remonta el formulario al cambiar de usuario, de modo que el
            estado inicial se toma de las props sin necesidad de un efecto. */}
        {open && (
          <FormularioUsuario
            key={usuario?.nro_carnet ?? "nuevo"}
            usuario={usuario}
            onOpenChange={onOpenChange}
            onSuccess={onSuccess}
          />
        )}
      </DialogContent>
    </Dialog>
  )
}

function FormularioUsuario({
  usuario,
  onOpenChange,
  onSuccess,
}: Omit<UsuarioDialogProps, "open">) {
  const esEdicion = Boolean(usuario)
  const [form, setForm] = useState(() =>
    usuario
      ? {
          nro_carnet: usuario.nro_carnet,
          nombre: usuario.nombre,
          apellido: usuario.apellido,
          email: usuario.email,
          departamento: usuario.departamento || "",
          categoria_codigo: usuario.categoria?.codigo || "EST",
          biblioteca_id: usuario.biblioteca_id ? String(usuario.biblioteca_id) : "ninguna",
        }
      : VACIO
  )
  const [categorias, setCategorias] = useState<Categoria[]>([])
  const [enviando, setEnviando] = useState(false)
  const { sedes, sedeId } = useSedes()
  // Al dar de alta se propone la sede de trabajo actual.
  const sedeElegida = form.biblioteca_id || (sedeId ? String(sedeId) : "ninguna")

  useEffect(() => {
    apiGet<Categoria[]>("/categories")
      .then(setCategorias)
      .catch(() => setCategorias([]))
  }, [])

  function set(campo: keyof typeof VACIO, valor: string) {
    setForm((f) => ({ ...f, [campo]: valor }))
  }

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault()
    if (enviando) return

    setEnviando(true)
    try {
      if (esEdicion && usuario) {
        await apiPut(`/users/${encodeURIComponent(usuario.nro_carnet)}`, {
          nombre: form.nombre.trim(),
          apellido: form.apellido.trim(),
          email: form.email.trim(),
          departamento: form.departamento.trim() || null,
          categoria_codigo: form.categoria_codigo,
          biblioteca_id: sedeElegida === "ninguna" ? null : Number(sedeElegida),
        })
        toast.success("Usuario actualizado", { description: `${form.nombre} ${form.apellido}` })
      } else {
        await apiPost("/users", {
          nro_carnet: form.nro_carnet.trim(),
          nombre: form.nombre.trim(),
          apellido: form.apellido.trim(),
          email: form.email.trim(),
          departamento: form.departamento.trim() || null,
          categoria_codigo: form.categoria_codigo,
          biblioteca_id: sedeElegida === "ninguna" ? null : Number(sedeElegida),
        })
        toast.success("Usuario registrado", {
          description: `La contraseña inicial es su carnet (${form.nro_carnet.trim()}); se le pedirá cambiarla al entrar.`,
        })
      }
      onOpenChange(false)
      onSuccess?.()
    } catch (error) {
      toast.error(
        esEdicion ? "No se pudo actualizar" : "No se pudo registrar",
        { description: mensajeDeError(error) }
      )
    } finally {
      setEnviando(false)
    }
  }

  const completo =
    form.nombre.trim() &&
    form.apellido.trim() &&
    form.email.trim() &&
    (esEdicion || form.nro_carnet.trim())

  return (
    <form onSubmit={handleSubmit}>
      <DialogHeader>
        <DialogTitle>{esEdicion ? "Editar usuario" : "Registrar usuario"}</DialogTitle>
        <DialogDescription>
          {esEdicion
            ? "El número de carnet no se puede modificar."
            : "La contraseña inicial será el número de carnet; el lector podrá cambiarla luego."}
        </DialogDescription>
      </DialogHeader>

      <div className="grid gap-4 py-4 sm:grid-cols-2">
        <div className="space-y-2">
          <Label htmlFor="u-carnet">N° de carnet *</Label>
          <Input
            id="u-carnet"
            value={form.nro_carnet}
            onChange={(e) => set("nro_carnet", e.target.value)}
            disabled={esEdicion}
            required
          />
        </div>
        <div className="space-y-2">
          <Label htmlFor="u-categoria">Categoría</Label>
          <Select
            value={form.categoria_codigo}
            onValueChange={(v) => set("categoria_codigo", v)}
          >
            <SelectTrigger id="u-categoria">
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              {categorias.map((c) => (
                <SelectItem key={c.codigo} value={c.codigo}>
                  {c.descripcion}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        </div>
        <div className="space-y-2">
          <Label htmlFor="u-nombre">Nombre *</Label>
          <Input
            id="u-nombre"
            value={form.nombre}
            onChange={(e) => set("nombre", e.target.value)}
            required
          />
        </div>
        <div className="space-y-2">
          <Label htmlFor="u-apellido">Apellido *</Label>
          <Input
            id="u-apellido"
            value={form.apellido}
            onChange={(e) => set("apellido", e.target.value)}
            required
          />
        </div>
        <div className="space-y-2 sm:col-span-2">
          <Label htmlFor="u-email">Email *</Label>
          <Input
            id="u-email"
            type="email"
            value={form.email}
            onChange={(e) => set("email", e.target.value)}
            required
          />
        </div>
        {sedes.length > 0 && (
          <div className="space-y-2 sm:col-span-2">
            <Label htmlFor="u-sede">Sede</Label>
            <Select value={sedeElegida} onValueChange={(v) => set("biblioteca_id", v)}>
              <SelectTrigger id="u-sede"><SelectValue /></SelectTrigger>
              <SelectContent>
                <SelectItem value="ninguna">Sin sede asignada</SelectItem>
                {sedes.map((s) => (
                  <SelectItem key={s.id} value={String(s.id)}>{s.nombre}</SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>
        )}
        <div className="space-y-2 sm:col-span-2">
          <Label htmlFor="u-depto">Departamento</Label>
          <Input
            id="u-depto"
            value={form.departamento}
            onChange={(e) => set("departamento", e.target.value)}
            placeholder="Ingeniería Agronómica"
          />
        </div>
      </div>

      <DialogFooter>
        <Button
          type="button"
          variant="outline"
          onClick={() => onOpenChange(false)}
          disabled={enviando}
        >
          Cancelar
        </Button>
        <Button type="submit" disabled={enviando || !completo}>
          {enviando && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}
          {esEdicion ? "Guardar cambios" : "Registrar"}
        </Button>
      </DialogFooter>
    </form>
  )
}
