"use client"

import { useEffect, useMemo, useState } from "react"
import { AlertTriangle, FileText, Loader2, Plus, Save } from "lucide-react"
import { toast } from "sonner"

import { Button } from "@/components/ui/button"
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
} from "@/components/ui/alert-dialog"
import { Input } from "@/components/ui/input"
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select"
import { ApiError, apiGet, mensajeDeError, type ErrorValidacion } from "@/lib/api"
import {
  aMarc,
  campoLibre,
  campoVacio,
  desdeMarc,
  insertarOrdenado,
  registroNuevo,
  textoLegible,
  type CampoEditor,
} from "@/lib/marc"
import type { PlantillaMarc, RegistroMarc, ResumenPlantilla } from "@/lib/types"
import { cn } from "@/lib/utils"
import { CampoMarc } from "./campo-marc"

interface EditorMarcProps {
  plantillaInicial: string
  /** null = registro nuevo (arranca con los campos visibles de la plantilla). */
  marcInicial: RegistroMarc | null
  soloLectura?: boolean
  textoBoton: string
  /** Lanza ApiError si el backend rechaza el registro. */
  onGuardar: (plantilla: string, marc: RegistroMarc, permitirDuplicado: boolean) => Promise<void>
}

/** Editor MARC21 por campos y subcampos, guiado por la plantilla de catalogación. */
export function EditorMarc({
  plantillaInicial,
  marcInicial,
  soloLectura = false,
  textoBoton,
  onGuardar,
}: EditorMarcProps) {
  const [plantillas, setPlantillas] = useState<ResumenPlantilla[]>([])
  const [codigo, setCodigo] = useState(plantillaInicial)
  const [definiciones, setDefiniciones] = useState<Record<string, PlantillaMarc>>({})
  const plantilla = definiciones[codigo]

  const [lider, setLider] = useState(marcInicial?.leader ?? "")
  const [campos, setCampos] = useState<CampoEditor[] | null>(
    marcInicial ? desdeMarc(marcInicial) : null
  )
  const [errores, setErrores] = useState<ErrorValidacion[]>([])
  const [guardando, setGuardando] = useState(false)
  const [verTexto, setVerTexto] = useState(false)
  const [duplicado, setDuplicado] = useState<string | null>(null)
  const [tagLibre, setTagLibre] = useState("")

  useEffect(() => {
    apiGet<ResumenPlantilla[]>("/catalog/frameworks").then(setPlantillas).catch(() => {})
  }, [])

  // La definición de cada plantilla se pide una vez; un registro nuevo se arma con ella.
  useEffect(() => {
    if (definiciones[codigo]) return
    apiGet<PlantillaMarc>(`/catalog/frameworks/${codigo}`)
      .then((p) => {
        setDefiniciones((d) => ({ ...d, [p.codigo]: p }))
        setCampos((actuales) => actuales ?? registroNuevo(p))
        setLider((actual) => actual || p.lider)
      })
      .catch((e) => toast.error("No se pudo cargar la plantilla", { description: mensajeDeError(e) }))
  }, [codigo, definiciones])

  function cambiarPlantilla(nuevo: string) {
    setCodigo(nuevo)
    setErrores([])
    const def = definiciones[nuevo]
    // En un registro nuevo y todavía vacío, la plantilla define con qué campos arranca.
    const vacio = campos?.every((c) => (c.control ? c.tag === "008" : c.subcampos.every((s) => !s.valor.trim())))
    if (!marcInicial && vacio) {
      setCampos(def ? registroNuevo(def) : null)
      setLider(def?.lider ?? "")
    }
  }

  const porTag = useMemo(
    () => Object.fromEntries((plantilla?.campos ?? []).map((c) => [c.tag, c])),
    [plantilla]
  )

  const erroresPorTag = useMemo(() => {
    const mapa: Record<string, { subcampo: string | null; msg: string }[]> = {}
    for (const e of errores) {
      const [tag, sub] = (e.loc ?? []).map(String)
      if (!tag) continue
      ;(mapa[tag] ??= []).push({ subcampo: sub && sub.length === 1 ? sub : null, msg: e.msg })
    }
    return mapa
  }, [errores])

  if (!campos || !plantilla) {
    return (
      <div className="rounded-lg border bg-card py-12 text-center text-muted-foreground">
        Cargando plantilla…
      </div>
    )
  }

  function actualizar(id: string, campo: CampoEditor) {
    setCampos((cs) => cs!.map((c) => (c.id === id ? campo : c)))
    // Al tocar un campo marcado, su aviso se va; el resumen de arriba queda hasta guardar.
    setErrores((es) => es.filter((e) => String(e.loc?.[0]) !== campo.tag || !e.loc?.[1]))
  }

  function agregarCampo(tag: string) {
    const def = porTag[tag]
    setCampos((cs) => insertarOrdenado(cs!, def ? campoVacio(def) : campoLibre(tag)))
    // Lleva la vista al campo recién agregado.
    setTimeout(() => document.querySelector(`[data-tag="${tag}"]:last-of-type`)?.scrollIntoView({ block: "center", behavior: "smooth" }), 50)
  }

  async function guardar(permitirDuplicado = false) {
    setGuardando(true)
    setErrores([])
    try {
      await onGuardar(codigo, aMarc(lider, campos!), permitirDuplicado)
    } catch (error) {
      if (error instanceof ApiError && error.status === 422 && error.errores.length) {
        setErrores(error.errores)
        toast.error("Revisa el registro", {
          description: `${error.errores.length} problema(s) marcados en rojo.`,
        })
      } else if (error instanceof ApiError && error.status === 400 && /ya está en/.test(error.message)) {
        setDuplicado(error.message)
      } else {
        toast.error("No se pudo guardar el registro", { description: mensajeDeError(error) })
      }
    } finally {
      setGuardando(false)
    }
  }

  const presentes = new Set(campos.map((c) => c.tag))
  const paraAgregar = plantilla.campos.filter((c) => c.repetible || !presentes.has(c.tag))
  const bloques = Array.from(new Set(campos.map((c) => c.tag[0]))).sort()

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-end gap-3 rounded-lg border border-border bg-card p-4">
        <div className="space-y-1">
          <label className="text-xs font-medium text-muted-foreground" htmlFor="marc-plantilla">
            Plantilla
          </label>
          <Select value={codigo} onValueChange={cambiarPlantilla} disabled={soloLectura}>
            <SelectTrigger id="marc-plantilla" className="w-56">
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              {(plantillas.length ? plantillas : [plantilla]).map((p) => (
                <SelectItem key={p.codigo} value={p.codigo}>
                  {p.nombre}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        </div>
        <div className="space-y-1">
          <label className="text-xs font-medium text-muted-foreground" htmlFor="marc-lider">
            Líder
          </label>
          <Input
            id="marc-lider"
            value={lider}
            maxLength={24}
            readOnly={soloLectura}
            spellCheck={false}
            className="w-64 font-mono text-sm"
            onChange={(e) => setLider(e.target.value)}
          />
        </div>
        <div className="ml-auto flex gap-2">
          <Button type="button" variant="outline" onClick={() => setVerTexto((v) => !v)}
                  aria-pressed={verTexto}>
            <FileText className="mr-2 h-4 w-4" />
            {verTexto ? "Ver editor" : "Ver como texto"}
          </Button>
          {!soloLectura && (
            <Button type="button" onClick={() => guardar()} disabled={guardando}>
              {guardando ? <Loader2 className="mr-2 h-4 w-4 animate-spin" /> : <Save className="mr-2 h-4 w-4" />}
              {textoBoton}
            </Button>
          )}
        </div>
        <p className="w-full text-xs text-muted-foreground">{plantilla.descripcion}</p>
      </div>

      {errores.length > 0 && (
        <div role="alert" className="rounded-lg border border-destructive/40 bg-destructive/5 p-4 text-sm">
          <p className="mb-1 flex items-center gap-2 font-medium text-destructive">
            <AlertTriangle className="h-4 w-4" />
            El registro no se guardó
          </p>
          <ul className="list-inside list-disc space-y-0.5 text-destructive">
            {errores.map((e, i) => (
              <li key={i}>{e.msg}</li>
            ))}
          </ul>
        </div>
      )}

      {verTexto ? (
        <pre className="overflow-x-auto rounded-lg border border-border bg-muted/40 p-4 font-mono text-sm leading-relaxed">
          {textoLegible(lider, campos)}
        </pre>
      ) : (
        bloques.map((bloque) => (
          <section key={bloque} aria-label={plantilla.bloques[bloque] ?? `${bloque}XX`}>
            <h3 className="mb-2 mt-4 text-xs font-semibold uppercase tracking-wide text-muted-foreground">
              {bloque}XX · {plantilla.bloques[bloque] ?? "Otros"}
            </h3>
            <div className="space-y-2">
              {campos
                .filter((c) => c.tag[0] === bloque)
                .map((c) => {
                  const def = porTag[c.tag]
                  return (
                    <CampoMarc
                      key={c.id}
                      campo={c}
                      definicion={def}
                      errores={erroresPorTag[c.tag] ?? []}
                      soloLectura={soloLectura}
                      onChange={(nuevo) => actualizar(c.id, nuevo)}
                      onRepetir={def?.repetible ? () => agregarCampo(c.tag) : undefined}
                      onQuitar={() => setCampos((cs) => cs!.filter((x) => x.id !== c.id))}
                    />
                  )
                })}
            </div>
          </section>
        ))
      )}

      {/* Errores de campos que faltan (no hay dónde marcarlos): se listan arriba. */}

      {!soloLectura && !verTexto && (
        <div className="flex flex-wrap items-center gap-2 rounded-lg border border-dashed border-border p-3">
          <span className="text-sm text-muted-foreground">Agregar campo:</span>
          <Select value="" onValueChange={agregarCampo}>
            <SelectTrigger className="w-80" aria-label="Agregar un campo de la plantilla">
              <SelectValue placeholder="De la plantilla…" />
            </SelectTrigger>
            <SelectContent className="max-h-80">
              {paraAgregar.map((c) => (
                <SelectItem key={c.tag} value={c.tag}>
                  <span className="mr-2 font-mono">{c.tag}</span>
                  {c.nombre}
                  {c.obligatorio && !presentes.has(c.tag) ? " · obligatorio" : ""}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
          <form
            className="flex items-center gap-2"
            onSubmit={(e) => {
              e.preventDefault()
              if (/^\d{3}$/.test(tagLibre)) {
                agregarCampo(tagLibre)
                setTagLibre("")
              }
            }}
          >
            <Input
              aria-label="Otra etiqueta"
              placeholder="Otra etiqueta (p. ej. 590)"
              value={tagLibre}
              maxLength={3}
              inputMode="numeric"
              className={cn("w-48 font-mono", tagLibre && !/^\d{3}$/.test(tagLibre) && "border-destructive")}
              onChange={(e) => setTagLibre(e.target.value.replace(/\D/g, ""))}
            />
            <Button type="submit" variant="outline" size="icon" aria-label="Agregar esa etiqueta"
                    disabled={!/^\d{3}$/.test(tagLibre)}>
              <Plus className="h-4 w-4" />
            </Button>
          </form>
        </div>
      )}

      <AlertDialog open={duplicado !== null} onOpenChange={(v) => !v && setDuplicado(null)}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>Ese ISBN ya está catalogado</AlertDialogTitle>
            <AlertDialogDescription>{duplicado}</AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel>Revisar</AlertDialogCancel>
            <AlertDialogAction
              onClick={() => {
                setDuplicado(null)
                guardar(true)
              }}
            >
              Guardar igualmente
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </div>
  )
}
