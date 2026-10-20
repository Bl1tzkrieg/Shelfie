"use client"

import { useCallback, useEffect, useState } from "react"
import { KeyRound, Loader2, Plus, Shuffle, UserCheck, UserX } from "lucide-react"
import { toast } from "sonner"

import { useSesion } from "@/components/auth/sesion-provider"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import {
  Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle,
} from "@/components/ui/dialog"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select"
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table"
import { apiGet, apiPost, apiPut, mensajeDeError } from "@/lib/api"
import { NOMBRE_ROL, type Personal, type Rol } from "@/lib/types"

/** Lo mismo que exige el backend para una clave temporal. */
const MINIMO_CLAVE = 8
const AYUDA_CLAVE = `Mínimo ${MINIMO_CLAVE} caracteres. La persona deberá cambiarla al entrar.`
const NO_PROPIA = "No puedes cambiar tu propia cuenta aquí"
const ROLES: Rol[] = ["catalogador", "administrador"]

/** 10 caracteres al azar, sin los que se confunden al leerlos (0/O, 1/l/I). */
export function generarClave(largo = 10): string {
  const letras = "abcdefghjkmnpqrstuvwxyzABCDEFGHJKLMNPQRSTUVWXYZ23456789"
  const azar = new Uint32Array(largo)
  crypto.getRandomValues(azar)
  return Array.from(azar, (n) => letras[n % letras.length]).join("")
}

export function ListaUsuarios() {
  const { usuario: yo } = useSesion()
  const [personal, setPersonal] = useState<Personal[] | null>(null)
  const [creando, setCreando] = useState(false)
  const [restableciendo, setRestableciendo] = useState<Personal | null>(null)
  const [ocupado, setOcupado] = useState<number | null>(null)

  const cargar = useCallback(async () => {
    try {
      setPersonal(await apiGet<Personal[]>("/staff"))
    } catch (e) {
      toast.error("No se pudo cargar el personal", { description: mensajeDeError(e) })
      setPersonal((actual) => actual ?? [])
    }
  }, [])

  useEffect(() => {
    apiGet<Personal[]>("/staff")
      .then(setPersonal)
      .catch((e) => {
        toast.error("No se pudo cargar el personal", { description: mensajeDeError(e) })
        setPersonal([])
      })
  }, [])

  async function cambiar(p: Personal, ruta: "role" | "active", cuerpo: object, ok: string) {
    setOcupado(p.id)
    try {
      await apiPut(`/staff/${p.id}/${ruta}`, cuerpo)
      toast.success(ok)
    } catch (e) {
      toast.error(mensajeDeError(e))  // p. ej. «no quedar sin administradores», tal cual
    } finally {
      setOcupado(null)
      await cargar()
    }
  }

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between gap-3">
        <p className="text-sm text-muted-foreground">
          Quién puede entrar al sistema. Los catalogadores ingresan y editan libros; los
          administradores, además, manejan usuarios, configuración y respaldo.
        </p>
        <Button onClick={() => setCreando(true)} className="shrink-0">
          <Plus className="mr-2 h-4 w-4" />Nuevo
        </Button>
      </div>

      <div className="rounded-lg border border-border bg-card">
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>Usuario</TableHead>
              <TableHead>Nombre</TableHead>
              <TableHead>Rol</TableHead>
              <TableHead>Estado</TableHead>
              <TableHead className="text-right">Acciones</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {personal === null && (
              <TableRow>
                <TableCell colSpan={5} className="py-8 text-center text-muted-foreground">
                  <Loader2 className="mx-auto h-5 w-5 animate-spin" />
                </TableCell>
              </TableRow>
            )}
            {personal?.map((p) => {
              const esYo = p.id === yo?.id
              const bloqueado = ocupado === p.id
              return (
                <TableRow key={p.id} className={p.activo ? "" : "opacity-60"}>
                  <TableCell className="font-mono text-sm">
                    {p.username}
                    {esYo && <Badge variant="secondary" className="ml-2 font-sans">Tú</Badge>}
                  </TableCell>
                  <TableCell>{p.nombre} {p.apellido}</TableCell>
                  <TableCell>
                    <span title={esYo ? NO_PROPIA : undefined}>
                      <Select value={p.rol} disabled={esYo || bloqueado}
                              onValueChange={(rol) => cambiar(p, "role", { rol },
                                `${p.username} ahora es ${NOMBRE_ROL[rol as Rol]}`)}>
                        <SelectTrigger className="w-40" aria-label={`Rol de ${p.username}`}>
                          <SelectValue />
                        </SelectTrigger>
                        <SelectContent>
                          {ROLES.map((r) => <SelectItem key={r} value={r}>{NOMBRE_ROL[r]}</SelectItem>)}
                        </SelectContent>
                      </Select>
                    </span>
                  </TableCell>
                  <TableCell>
                    {p.activo
                      ? <Badge>Activo</Badge>
                      : <Badge variant="outline">Desactivado</Badge>}
                    {p.debe_cambiar_clave && (
                      <span className="ml-2 text-xs text-muted-foreground">Clave por cambiar</span>
                    )}
                  </TableCell>
                  <TableCell>
                    <div className="flex justify-end gap-2">
                      <span title={esYo ? NO_PROPIA : undefined}>
                        <Button variant="outline" size="sm" disabled={esYo || bloqueado}
                                onClick={() => cambiar(p, "active", { activo: !p.activo },
                                  p.activo ? `${p.username} fue desactivado` : `${p.username} fue activado`)}>
                          {p.activo
                            ? <><UserX className="mr-1.5 h-4 w-4" />Desactivar</>
                            : <><UserCheck className="mr-1.5 h-4 w-4" />Activar</>}
                        </Button>
                      </span>
                      <Button variant="outline" size="sm" disabled={bloqueado}
                              onClick={() => setRestableciendo(p)}>
                        <KeyRound className="mr-1.5 h-4 w-4" />Restablecer clave
                      </Button>
                    </div>
                  </TableCell>
                </TableRow>
              )
            })}
          </TableBody>
        </Table>
      </div>

      <DialogoNuevo open={creando} onOpenChange={setCreando} onCreado={cargar} />
      <DialogoClave persona={restableciendo} onCerrar={() => setRestableciendo(null)} />
    </div>
  )
}

function CampoClave({ valor, onCambio }: { valor: string; onCambio: (v: string) => void }) {
  return (
    <div className="space-y-1.5">
      <Label htmlFor="clave-temporal">Clave temporal</Label>
      <div className="flex gap-2">
        <Input id="clave-temporal" value={valor} autoComplete="off" spellCheck={false}
               className="font-mono" onChange={(e) => onCambio(e.target.value)}
               aria-describedby="clave-ayuda" />
        <Button type="button" variant="outline" onClick={() => onCambio(generarClave())}>
          <Shuffle className="mr-1.5 h-4 w-4" />Generar
        </Button>
      </div>
      <p id="clave-ayuda" className="text-xs text-muted-foreground">
        {AYUDA_CLAVE} Anótala y entrégasela: no se vuelve a mostrar.
      </p>
    </div>
  )
}

function DialogoNuevo({ open, onOpenChange, onCreado }: {
  open: boolean
  onOpenChange: (abierto: boolean) => void
  onCreado: () => Promise<void>
}) {
  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      {/* El contenido se monta al abrir: el formulario siempre empieza vacío. */}
      <DialogContent>
        <FormularioNuevo onOpenChange={onOpenChange} onCreado={onCreado} />
      </DialogContent>
    </Dialog>
  )
}

function FormularioNuevo({ onOpenChange, onCreado }: {
  onOpenChange: (abierto: boolean) => void
  onCreado: () => Promise<void>
}) {
  const [f, setF] = useState({ username: "", nombre: "", apellido: "", rol: "catalogador" as Rol, clave: "" })
  const [guardando, setGuardando] = useState(false)
  const completo = f.username.trim() && f.nombre.trim() && f.apellido.trim()
    && f.clave.length >= MINIMO_CLAVE

  async function crear(e: React.FormEvent) {
    e.preventDefault()
    setGuardando(true)
    try {
      await apiPost("/staff", {
        username: f.username.trim(), nombre: f.nombre.trim(), apellido: f.apellido.trim(),
        rol: f.rol, clave_temporal: f.clave,
      })
      toast.success(`Se creó el usuario ${f.username.trim()}`)
      onOpenChange(false)
      await onCreado()
    } catch (error) {
      toast.error(mensajeDeError(error))
    } finally {
      setGuardando(false)
    }
  }

  const set = (k: "username" | "nombre" | "apellido") =>
    (e: React.ChangeEvent<HTMLInputElement>) => setF((a) => ({ ...a, [k]: e.target.value }))

  return (
        <form onSubmit={crear} className="space-y-4">
          <DialogHeader>
            <DialogTitle>Nuevo usuario</DialogTitle>
            <DialogDescription>Se le pedirá cambiar la clave temporal al entrar.</DialogDescription>
          </DialogHeader>
          <div className="space-y-1.5">
            <Label htmlFor="nu-usuario">Usuario</Label>
            <Input id="nu-usuario" value={f.username} onChange={set("username")}
                   autoComplete="off" placeholder="maria.perez" />
          </div>
          <div className="grid gap-3 sm:grid-cols-2">
            <div className="space-y-1.5">
              <Label htmlFor="nu-nombre">Nombre</Label>
              <Input id="nu-nombre" value={f.nombre} onChange={set("nombre")} />
            </div>
            <div className="space-y-1.5">
              <Label htmlFor="nu-apellido">Apellido</Label>
              <Input id="nu-apellido" value={f.apellido} onChange={set("apellido")} />
            </div>
          </div>
          <div className="space-y-1.5">
            <Label htmlFor="nu-rol">Rol</Label>
            <Select value={f.rol} onValueChange={(rol) => setF((a) => ({ ...a, rol: rol as Rol }))}>
              <SelectTrigger id="nu-rol" className="w-full"><SelectValue /></SelectTrigger>
              <SelectContent>
                {ROLES.map((r) => <SelectItem key={r} value={r}>{NOMBRE_ROL[r]}</SelectItem>)}
              </SelectContent>
            </Select>
          </div>
          <CampoClave valor={f.clave} onCambio={(clave) => setF((a) => ({ ...a, clave }))} />
          <DialogFooter>
            <Button type="button" variant="outline" onClick={() => onOpenChange(false)}>Cancelar</Button>
            <Button type="submit" disabled={!completo || guardando}>
              {guardando && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}Crear usuario
            </Button>
          </DialogFooter>
        </form>
  )
}

function DialogoClave({ persona, onCerrar }: { persona: Personal | null; onCerrar: () => void }) {
  return (
    <Dialog open={persona !== null} onOpenChange={(abierto) => !abierto && onCerrar()}>
      <DialogContent>
        {persona && <FormularioClave persona={persona} onCerrar={onCerrar} />}
      </DialogContent>
    </Dialog>
  )
}

function FormularioClave({ persona, onCerrar }: { persona: Personal; onCerrar: () => void }) {
  const [clave, setClave] = useState("")
  const [guardando, setGuardando] = useState(false)

  async function restablecer(e: React.FormEvent) {
    e.preventDefault()
    setGuardando(true)
    try {
      await apiPost(`/staff/${persona.id}/password`, { clave_temporal: clave })
      toast.success(`Se restableció la clave de ${persona.username}`)
      onCerrar()
    } catch (error) {
      toast.error(mensajeDeError(error))
    } finally {
      setGuardando(false)
    }
  }

  return (
        <form onSubmit={restablecer} className="space-y-4">
          <DialogHeader>
            <DialogTitle>Restablecer clave</DialogTitle>
            <DialogDescription>
              Clave temporal para {persona.nombre} {persona.apellido} ({persona.username}).
              Se le pedirá cambiarla al entrar.
            </DialogDescription>
          </DialogHeader>
          <CampoClave valor={clave} onCambio={setClave} />
          <DialogFooter>
            <Button type="button" variant="outline" onClick={onCerrar}>Cancelar</Button>
            <Button type="submit" disabled={clave.length < MINIMO_CLAVE || guardando}>
              {guardando && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}Restablecer
            </Button>
          </DialogFooter>
        </form>
  )
}
