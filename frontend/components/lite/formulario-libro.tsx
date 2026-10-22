"use client"

import { useEffect, useRef, useState } from "react"
import Link from "next/link"
import { useRouter } from "next/navigation"
import { ExternalLink, Loader2, Plus, Save, X } from "lucide-react"
import { toast } from "sonner"

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
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { Textarea } from "@/components/ui/textarea"
import { ApiError, apiPost, apiPut, mensajeDeError } from "@/lib/api"
import type { CoincidenciaDuplicado, FichaLibro, LibroCatalogo, NuevoLibro } from "@/lib/types"
import { cn } from "@/lib/utils"

// --- Estado del formulario ----------------------------------------------------------

/** Lo que se escribe: todo como texto; las listas siempre con al menos una casilla. */
type Valores = {
  cota: string
  titulo: string
  subtitulo: string
  mencion: string
  autor: string
  otros_autores: string[]
  edicion: string
  lugar: string
  editorial: string
  ano: string
  paginas: string
  ilustraciones: string
  dimensiones: string
  isbn: string[]
  materias: string[]
  descripcion: string
  notas: string
  ejemplares: string
  nota_ejemplares: string
}

type CampoTexto = Exclude<keyof Valores, CampoLista>
type CampoLista = "otros_autores" | "isbn" | "materias"

const MAX_EJEMPLARES = 50
/** Topes de la API (schemas.FichaLibro): la cota cabe en su columna y la descripción y las
 * notas en un campo ISO 2709. La API cuenta 9000 bytes; aquí son caracteres (aproximado:
 * una letra con tilde ocupa 2 bytes, y entonces avisa la API). */
const MAX_COTA = 100
const MAX_TEXTO_LARGO = 9000

function vacio(): Valores {
  return {
    cota: "", titulo: "", subtitulo: "", mencion: "", autor: "", otros_autores: [""],
    edicion: "", lugar: "", editorial: "", ano: "", paginas: "", ilustraciones: "",
    dimensiones: "", isbn: [""], materias: [""], descripcion: "", notas: "",
    ejemplares: "1", nota_ejemplares: "",
  }
}

function lista(valores: string[] | null | undefined): string[] {
  return valores && valores.length ? [...valores] : [""]
}

function desdeFicha(f: FichaLibro): Valores {
  return {
    ...vacio(),
    cota: f.cota ?? "",
    titulo: f.titulo ?? "",
    subtitulo: f.subtitulo ?? "",
    mencion: f.mencion ?? "",
    autor: f.autor ?? "",
    otros_autores: lista(f.otros_autores),
    edicion: f.edicion ?? "",
    lugar: f.lugar ?? "",
    editorial: f.editorial ?? "",
    ano: f.ano != null ? String(f.ano) : "",
    paginas: f.paginas ?? "",
    ilustraciones: f.ilustraciones ?? "",
    dimensiones: f.dimensiones ?? "",
    isbn: lista(f.isbn),
    materias: lista(f.materias),
    descripcion: f.descripcion ?? "",
    notas: f.notas ?? "",
  }
}

const texto = (v: string) => v.trim() || null
const limpiarLista = (vs: string[]) => vs.map((v) => v.trim()).filter(Boolean)

function aFicha(v: Valores): FichaLibro {
  return {
    cota: v.cota.trim(),
    titulo: v.titulo.trim(),
    subtitulo: texto(v.subtitulo),
    mencion: texto(v.mencion),
    autor: texto(v.autor),
    otros_autores: limpiarLista(v.otros_autores),
    edicion: texto(v.edicion),
    lugar: texto(v.lugar),
    editorial: texto(v.editorial),
    ano: v.ano.trim() ? Number(v.ano.trim()) : null,
    paginas: texto(v.paginas),
    ilustraciones: texto(v.ilustraciones),
    dimensiones: texto(v.dimensiones),
    isbn: limpiarLista(v.isbn),
    materias: limpiarLista(v.materias),
    descripcion: texto(v.descripcion),
    notas: texto(v.notas),
  }
}

/** Para saber si hay cambios sin guardar: lo que se enviaría, no las casillas vacías. */
function huella(v: Valores, alta: boolean): string {
  return JSON.stringify(alta
    ? { ficha: aFicha(v), ejemplares: v.ejemplares.trim(), nota: v.nota_ejemplares.trim() }
    : aFicha(v))
}

type Errores = Partial<Record<keyof Valores, string>>

/** Validación previa: lo que el backend rechazaría con un 422 se marca sin ir al servidor. */
function validar(v: Valores, alta: boolean): Errores {
  const e: Errores = {}
  if (!v.cota.trim()) e.cota = "Es obligatoria: es lo que se busca en el estante"
  if (!v.titulo.trim()) e.titulo = "Es obligatorio"
  if (v.ano.trim() && !/^\d{1,4}$/.test(v.ano.trim())) e.ano = "Escribe el año con números, p. ej. 1998"
  if (alta) {
    const n = Number(v.ejemplares)
    if (!/^\d+$/.test(v.ejemplares.trim()) || n < 1 || n > MAX_EJEMPLARES) {
      e.ejemplares = `Entre 1 y ${MAX_EJEMPLARES}`
    }
  }
  return e
}

const CAMPOS = new Set<string>(Object.keys(vacio()))

/** Mensaje de Pydantic en castellano llano (los de los validadores propios ya vienen en español). */
function traducir(msg: string): string {
  const limpio = msg.replace(/^Value error, /, "")
  if (/valid integer/i.test(limpio)) return "Debe ser un número entero"
  if (/greater than or equal/i.test(limpio)) return "Es demasiado pequeño"
  if (/less than or equal/i.test(limpio)) return "Es demasiado grande"
  if (/at most \d+ characters/i.test(limpio)) return "Es demasiado largo"
  if (/field required/i.test(limpio)) return "Es obligatorio"
  return limpio
}

/** 422 → error junto a su campo: el primer elemento de `loc` que es un campo del formulario. */
function erroresDelServidor(error: ApiError): Errores {
  const e: Errores = {}
  for (const { loc, msg } of error.errores) {
    const campo = (loc ?? []).map(String).find((p) => CAMPOS.has(p)) as keyof Valores | undefined
    if (campo && !e[campo]) e[campo] = traducir(msg)
  }
  return e
}

function esDuplicado(error: unknown): CoincidenciaDuplicado[] | null {
  if (!(error instanceof ApiError) || error.status !== 409) return null
  if (error.detalle?.codigo !== "POSIBLE_DUPLICADO") return null
  const c = error.detalle.coincidencias
  return Array.isArray(c) ? (c as CoincidenciaDuplicado[]) : []
}

// --- Formulario ---------------------------------------------------------------------

type Accion = "guardar" | "nuevo"

interface FormularioLibroProps {
  /** null = alta. En edición, el libro tal como lo devolvió GET /books/{id}. */
  libro: LibroCatalogo | null
}

/**
 * La ficha simple de la §6 del spec, en su orden. En alta se ingresan muchos libros
 * seguidos: "Guardar y nuevo" (o Ctrl+Enter) guarda, limpia y deja el cursor en Cota.
 */
export function FormularioLibro({ libro }: FormularioLibroProps) {
  const router = useRouter()
  const alta = libro === null
  const [inicial, setInicial] = useState(() => (libro ? desdeFicha(libro.ficha) : vacio()))
  const [valores, setValores] = useState(inicial)
  const [errores, setErrores] = useState<Errores>({})
  const [guardando, setGuardando] = useState<Accion | null>(null)
  const [duplicados, setDuplicados] = useState<{ accion: Accion; lista: CoincidenciaDuplicado[] } | null>(null)
  const formulario = useRef<HTMLFormElement>(null)
  const cota = useRef<HTMLInputElement>(null)
  // Casilla de lista a enfocar después de agregarla: [campo, índice].
  const [enfocar, setEnfocar] = useState<[CampoLista, number] | null>(null)

  const hayCambios = huella(valores, alta) !== huella(inicial, alta)

  // Avisar antes de cerrar o recargar la pestaña con cambios sin guardar.
  useEffect(() => {
    if (!hayCambios) return
    const avisar = (e: BeforeUnloadEvent) => {
      e.preventDefault()
      e.returnValue = ""
    }
    window.addEventListener("beforeunload", avisar)
    return () => window.removeEventListener("beforeunload", avisar)
  }, [hayCambios])

  useEffect(() => {
    if (!enfocar) return
    const [campo, i] = enfocar
    formulario.current?.querySelector<HTMLInputElement>(`[data-lista="${campo}-${i}"]`)?.focus()
  }, [enfocar])

  // En alta el cursor arranca en Cota.
  useEffect(() => {
    if (alta) cota.current?.focus()
  }, [alta])

  function cambiar(campo: CampoTexto, valor: string) {
    setValores((v) => ({ ...v, [campo]: valor }))
    if (errores[campo]) setErrores((e) => ({ ...e, [campo]: undefined }))
  }

  function cambiarLista(campo: CampoLista, actual: string[]) {
    setValores((v) => ({ ...v, [campo]: actual.length ? actual : [""] }))
    if (errores[campo]) setErrores((e) => ({ ...e, [campo]: undefined }))
  }

  function agregarALista(campo: CampoLista, despuesDe: number) {
    const actual = [...valores[campo]]
    actual.splice(despuesDe + 1, 0, "")
    cambiarLista(campo, actual)
    setEnfocar([campo, despuesDe + 1])
  }

  function enfocarPrimerError(e: Errores) {
    const primero = Object.keys(vacio()).find((c) => e[c as keyof Valores])
    if (!primero) return
    formulario.current
      ?.querySelector<HTMLElement>(`#libro-${primero}, [data-lista="${primero}-0"]`)
      ?.focus()
  }

  async function guardar(accion: Accion, forzar = false) {
    if (guardando) return
    const previos = validar(valores, alta)
    if (Object.keys(previos).length) {
      setErrores(previos)
      toast.error("Revisa los campos marcados")
      enfocarPrimerError(previos)
      return
    }
    setGuardando(accion)
    setErrores({})
    try {
      if (alta) {
        const cuerpo: NuevoLibro = {
          ficha: aFicha(valores),
          ejemplares: Number(valores.ejemplares),
          nota_ejemplares: texto(valores.nota_ejemplares),
          forzar,
        }
        const r = await apiPost<LibroCatalogo>("/books", cuerpo)
        if (accion === "nuevo") {
          toast.success(`Guardado: ${r.ficha.titulo} (${r.ficha.cota})`)
          const limpio = vacio()
          setInicial(limpio)
          setValores(limpio)
          window.scrollTo({ top: 0 })
          // Tras el render del formulario limpio.
          setTimeout(() => cota.current?.focus(), 0)
        } else {
          setInicial(valores)
          toast.success(`Guardado: ${r.ficha.titulo} (${r.ficha.cota})`)
          router.push(`/libro/?id=${r.id}`)
        }
      } else {
        const r = await apiPut<LibroCatalogo>(`/books/${libro.id}`, aFicha(valores))
        setInicial(valores)
        toast.success(`Guardado: ${r.ficha.titulo} (${r.ficha.cota})`)
        router.push(`/libro/?id=${r.id}`)
      }
    } catch (error) {
      const coincidencias = esDuplicado(error)
      if (coincidencias) {
        setDuplicados({ accion, lista: coincidencias })
      } else if (error instanceof ApiError && error.status === 422) {
        const del = erroresDelServidor(error)
        setErrores(del)
        toast.error("Revisa los campos marcados", { description: error.message })
        enfocarPrimerError(del)
      } else {
        toast.error("No se pudo guardar el libro", { description: mensajeDeError(error) })
      }
    } finally {
      setGuardando(null)
    }
  }

  function alPresionarTecla(e: React.KeyboardEvent<HTMLFormElement>) {
    if (e.key !== "Enter") return
    const destino = e.target as HTMLElement
    if (e.ctrlKey || e.metaKey) {
      e.preventDefault()
      guardar(alta ? "nuevo" : "guardar")
      return
    }
    // Enter en una casilla de una línea no envía el formulario: así no se guarda un
    // libro a medias. En una lista, agrega otra casilla debajo.
    if (destino.tagName === "INPUT") {
      e.preventDefault()
      const enLista = destino.dataset.lista
      if (enLista) {
        const [campo, i] = enLista.split("-") as [CampoLista, string]
        if ((destino as HTMLInputElement).value.trim()) agregarALista(campo, Number(i))
      }
    }
  }

  const props = (campo: CampoTexto) => ({
    id: `libro-${campo}`,
    value: valores[campo],
    "aria-invalid": errores[campo] ? true : undefined,
    "aria-describedby": errores[campo] ? `libro-${campo}-error` : undefined,
    onChange: (e: React.ChangeEvent<HTMLInputElement | HTMLTextAreaElement>) => cambiar(campo, e.target.value),
  })

  return (
    <form
      ref={formulario}
      noValidate
      onSubmit={(e) => e.preventDefault()}
      onKeyDown={alPresionarTecla}
      className="mx-auto max-w-3xl space-y-6"
    >
      <section className="space-y-4 rounded-xl border border-border/80 bg-card shadow-papel p-4 sm:p-6">
        <Campo campo="cota" rotulo="Cota" obligatorio error={errores.cota}
               ayuda="Clase y librística, p. ej. 616.39 H37">
          <Input {...props("cota")} ref={cota} required maxLength={MAX_COTA} autoComplete="off"
                 spellCheck={false}
                 className="font-mono text-lg" />
        </Campo>
        <Campo campo="titulo" rotulo="Título" obligatorio error={errores.titulo}>
          <Input {...props("titulo")} required autoComplete="off" />
        </Campo>
        <Campo campo="subtitulo" rotulo="Subtítulo" error={errores.subtitulo}>
          <Input {...props("subtitulo")} autoComplete="off" />
        </Campo>
        <Campo campo="mencion" rotulo="Mención de responsabilidad" error={errores.mencion}
               ayuda="Como aparece en la portada, p. ej. «Gabriel García Márquez ; ilustraciones de…»">
          <Input {...props("mencion")} autoComplete="off" />
        </Campo>
        <Campo campo="autor" rotulo="Autor principal" error={errores.autor}>
          <Input {...props("autor")} autoComplete="off" placeholder="Apellido, Nombre" />
        </Campo>
        <Lista campo="otros_autores" rotulo="Otros autores" valores={valores.otros_autores}
               error={errores.otros_autores} placeholder="Apellido, Nombre"
               onCambiar={cambiarLista} onAgregar={agregarALista} />
        <Campo campo="edicion" rotulo="Edición" error={errores.edicion}>
          <Input {...props("edicion")} autoComplete="off" placeholder="p. ej. 2.ª ed." />
        </Campo>
        <div className="grid gap-4 sm:grid-cols-[1fr_1fr_8rem]">
          <Campo campo="lugar" rotulo="Lugar" error={errores.lugar}>
            <Input {...props("lugar")} autoComplete="off" />
          </Campo>
          <Campo campo="editorial" rotulo="Editorial" error={errores.editorial}>
            <Input {...props("editorial")} autoComplete="off" />
          </Campo>
          <Campo campo="ano" rotulo="Año" error={errores.ano}>
            <Input {...props("ano")} inputMode="numeric" maxLength={4} autoComplete="off" />
          </Campo>
        </div>
        <div className="grid gap-4 sm:grid-cols-3">
          <Campo campo="paginas" rotulo="Páginas" error={errores.paginas}>
            <Input {...props("paginas")} autoComplete="off" placeholder="p. ej. 320 p." />
          </Campo>
          <Campo campo="ilustraciones" rotulo="Ilustraciones" error={errores.ilustraciones}>
            <Input {...props("ilustraciones")} autoComplete="off" placeholder="p. ej. il." />
          </Campo>
          <Campo campo="dimensiones" rotulo="Dimensiones" error={errores.dimensiones}>
            <Input {...props("dimensiones")} autoComplete="off" placeholder="p. ej. 23 cm" />
          </Campo>
        </div>
        <Lista campo="isbn" rotulo="ISBN" valores={valores.isbn} error={errores.isbn}
               mono onCambiar={cambiarLista} onAgregar={agregarALista} />
        <Lista campo="materias" rotulo="Materias" valores={valores.materias}
               error={errores.materias} onCambiar={cambiarLista} onAgregar={agregarALista} />
        <Campo campo="descripcion" rotulo="Descripción / resumen" error={errores.descripcion}>
          <Textarea {...props("descripcion")} rows={3} maxLength={MAX_TEXTO_LARGO} />
        </Campo>
        <Campo campo="notas" rotulo="Notas" error={errores.notas}>
          <Textarea {...props("notas")} rows={2} maxLength={MAX_TEXTO_LARGO} />
        </Campo>
      </section>

      {alta && (
        <section className="grid gap-4 rounded-xl border border-border/80 bg-card shadow-papel p-4 sm:grid-cols-[10rem_1fr] sm:p-6">
          <Campo campo="ejemplares" rotulo="N.º de ejemplares" error={errores.ejemplares}>
            <Input {...props("ejemplares")} type="number" min={1} max={MAX_EJEMPLARES}
                   inputMode="numeric" />
          </Campo>
          <Campo campo="nota_ejemplares" rotulo="Nota de ejemplares" error={errores.nota_ejemplares}
                 ayuda="La misma para todos, p. ej. «Donación»">
            <Input {...props("nota_ejemplares")} maxLength={MAX_TEXTO_LARGO} autoComplete="off" />
          </Campo>
        </section>
      )}

      <div className="sticky bottom-0 z-10 -mx-4 flex flex-wrap items-center justify-end gap-2 border-t border-border bg-background/95 px-4 py-3 backdrop-blur sm:mx-0 sm:rounded-lg sm:border">
        {alta && (
          <p className="mr-auto hidden text-xs text-muted-foreground md:block">
            Ctrl+Enter: guardar y nuevo
          </p>
        )}
        <Button type="button" variant={alta ? "outline" : "default"} disabled={guardando !== null}
                onClick={() => guardar("guardar")}>
          {guardando === "guardar" ? <Loader2 className="animate-spin" /> : <Save />}
          Guardar
        </Button>
        {alta && (
          <Button type="button" disabled={guardando !== null} onClick={() => guardar("nuevo")}>
            {guardando === "nuevo" ? <Loader2 className="animate-spin" /> : <Plus />}
            Guardar y nuevo
          </Button>
        )}
      </div>

      <AlertDialog open={duplicados !== null} onOpenChange={(abierto) => !abierto && setDuplicados(null)}>
        <AlertDialogContent onCloseAutoFocus={(e) => e.preventDefault()}>
          <AlertDialogHeader>
            <AlertDialogTitle>Puede que este libro ya esté en el catálogo</AlertDialogTitle>
            <AlertDialogDescription>
              Hay libros con el mismo ISBN, o con el mismo título y autor. Revísalos (se abren en
              otra pestaña) y, si es otra edición u otro libro, guárdalo igual.
            </AlertDialogDescription>
          </AlertDialogHeader>
          <ul className="max-h-64 space-y-2 overflow-y-auto">
            {duplicados?.lista.map((c) => (
              <li key={c.id} className="rounded-md border border-border p-3">
                <a href={`/libro/?id=${c.id}`} target="_blank" rel="noopener noreferrer"
                   className="group flex items-start justify-between gap-3">
                  <span className="min-w-0">
                    <span className="block font-medium text-foreground group-hover:underline">{c.titulo}</span>
                    <span className="block text-sm text-muted-foreground">
                      {c.autor ?? "Sin autor"} ·{" "}
                      {c.cota ? <span className="font-mono">{c.cota}</span> : "Sin cota"}
                    </span>
                  </span>
                  <ExternalLink className="mt-1 h-4 w-4 shrink-0 text-muted-foreground" aria-label="Abre en otra pestaña" />
                </a>
              </li>
            ))}
          </ul>
          <AlertDialogFooter>
            <AlertDialogCancel onClick={() => setTimeout(() => cota.current?.focus(), 0)}>
              Cancelar
            </AlertDialogCancel>
            <AlertDialogAction
              onClick={() => {
                const accion = duplicados?.accion ?? "guardar"
                setDuplicados(null)
                guardar(accion, true)
              }}
            >
              Guardar igual
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </form>
  )
}

// --- Piezas -------------------------------------------------------------------------

function Obligatorio() {
  return (
    <span className="text-destructive" aria-hidden>
      {" "}*
    </span>
  )
}

function MensajeError({ id, children }: { id: string; children?: string }) {
  if (!children) return null
  return (
    <p id={id} role="alert" className="text-sm text-destructive">
      {children}
    </p>
  )
}

function Campo({ campo, rotulo, obligatorio, error, ayuda, children }: {
  campo: keyof Valores
  rotulo: string
  obligatorio?: boolean
  error?: string
  ayuda?: string
  children: React.ReactNode
}) {
  return (
    <div className="space-y-1.5">
      <Label htmlFor={`libro-${campo}`}>
        {rotulo}
        {obligatorio && <Obligatorio />}
        {obligatorio && <span className="sr-only"> (obligatorio)</span>}
      </Label>
      {children}
      {ayuda && !error && <p className="text-xs text-muted-foreground">{ayuda}</p>}
      <MensajeError id={`libro-${campo}-error`}>{error}</MensajeError>
    </div>
  )
}

/** Campo repetible: una casilla por valor, "+" agrega otra debajo y "×" la quita. */
function Lista({ campo, rotulo, valores, error, placeholder, mono, onCambiar, onAgregar }: {
  campo: CampoLista
  rotulo: string
  valores: string[]
  error?: string
  placeholder?: string
  mono?: boolean
  onCambiar: (campo: CampoLista, valores: string[]) => void
  onAgregar: (campo: CampoLista, despuesDe: number) => void
}) {
  return (
    <fieldset className="space-y-1.5" aria-describedby={error ? `libro-${campo}-error` : undefined}>
      <legend className="mb-1.5 text-sm font-medium leading-none">{rotulo}</legend>
      {valores.map((valor, i) => (
        <div key={i} className="flex gap-2">
          <Input
            data-lista={`${campo}-${i}`}
            aria-label={valores.length > 1 ? `${rotulo} ${i + 1}` : rotulo}
            aria-invalid={error ? true : undefined}
            value={valor}
            placeholder={placeholder}
            autoComplete="off"
            spellCheck={mono ? false : undefined}
            className={cn(mono && "font-mono")}
            onChange={(e) => onCambiar(campo, valores.map((v, j) => (j === i ? e.target.value : v)))}
          />
          <Button type="button" variant="ghost" size="icon" aria-label={`Quitar ${rotulo.toLowerCase()} ${i + 1}`}
                  disabled={valores.length === 1 && !valor}
                  onClick={() => onCambiar(campo, valores.filter((_, j) => j !== i))}>
            <X />
          </Button>
          {i === valores.length - 1 && (
            <Button type="button" variant="outline" size="icon" aria-label={`Agregar otro: ${rotulo.toLowerCase()}`}
                    onClick={() => onAgregar(campo, i)}>
              <Plus />
            </Button>
          )}
        </div>
      ))}
      <MensajeError id={`libro-${campo}-error`}>{error}</MensajeError>
    </fieldset>
  )
}

/** Enlace a la ficha pública, para la cabecera de la edición. */
export function EnlaceFicha({ id }: { id: number }) {
  return (
    <Button asChild variant="outline" size="sm">
      <Link href={`/libro/?id=${id}`}>Ver ficha</Link>
    </Button>
  )
}
