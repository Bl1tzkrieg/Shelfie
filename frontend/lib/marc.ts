/**
 * Modelo del editor MARC: el registro como lista editable de campos, y su ida y
 * vuelta con MARC-in-JSON (la forma que guarda el backend).
 */
import type {
  CampoMarcDatos,
  DefinicionCampo,
  PlantillaMarc,
  RegistroMarc,
} from "@/lib/types"

export type SubcampoEditor = { id: string; codigo: string; valor: string }

export type CampoEditor =
  | { id: string; tag: string; control: true; valor: string }
  | { id: string; tag: string; control: false; ind1: string; ind2: string; subcampos: SubcampoEditor[] }

let secuencia = 0
export const nuevoId = () => `m${++secuencia}`

export const esDeControl = (tag: string) => tag < "010"

/** Subcampos que se ofrecen vacíos al agregar un campo: los obligatorios y los primeros. */
const SUBCAMPOS_INICIALES = 3

export function campoVacio(def: DefinicionCampo): CampoEditor {
  if (def.control) return { id: nuevoId(), tag: def.tag, control: true, valor: "" }
  const iniciales = def.subcampos.filter(
    (s, i) => s.obligatorio || i < SUBCAMPOS_INICIALES
  )
  return {
    id: nuevoId(),
    tag: def.tag,
    control: false,
    ind1: def.ind1_defecto,
    ind2: def.ind2_defecto,
    subcampos: (iniciales.length ? iniciales : [{ codigo: "a" }]).map((s) => ({
      id: nuevoId(),
      codigo: s.codigo,
      valor: "",
    })),
  }
}

export function campoLibre(tag: string): CampoEditor {
  return esDeControl(tag)
    ? { id: nuevoId(), tag, control: true, valor: "" }
    : { id: nuevoId(), tag, control: false, ind1: " ", ind2: " ",
        subcampos: [{ id: nuevoId(), codigo: "a", valor: "" }] }
}

/** 008 básico para un registro nuevo (mismo formato que el backend). */
export function campo008(ano?: number): string {
  const hoy = new Date()
  const dos = (n: number) => String(n).padStart(2, "0")
  const fecha = `${dos(hoy.getFullYear() % 100)}${dos(hoy.getMonth() + 1)}${dos(hoy.getDate())}`
  const fecha1 = ano ? String(ano).padStart(4, "0") : "    "
  return `${fecha}s${fecha1}    ve ${" ".repeat(17)}spa d`
}

/** Campos con que arranca un registro nuevo: los "visibles" de la plantilla. */
export function registroNuevo(plantilla: PlantillaMarc): CampoEditor[] {
  return plantilla.campos
    .filter((c) => c.visible)
    .map((def) => {
      const campo = campoVacio(def)
      if (campo.control && def.tag === "008") return { ...campo, valor: campo008() }
      return campo
    })
}

export function desdeMarc(marc: RegistroMarc): CampoEditor[] {
  return marc.fields.map((f) => {
    const [tag, valor] = Object.entries(f)[0]
    if (typeof valor === "string") return { id: nuevoId(), tag, control: true, valor }
    const datos = valor as CampoMarcDatos
    return {
      id: nuevoId(),
      tag,
      control: false,
      ind1: datos.ind1 || " ",
      ind2: datos.ind2 || " ",
      subcampos: datos.subfields.map((s) => {
        const [codigo, texto] = Object.entries(s)[0]
        return { id: nuevoId(), codigo, valor: texto }
      }),
    }
  })
}

/** Al guardar, los subcampos y campos vacíos se descartan (el backend hace lo mismo). */
export function aMarc(lider: string, campos: CampoEditor[]): RegistroMarc {
  const fields: RegistroMarc["fields"] = []
  for (const c of campos) {
    if (c.control) {
      if (c.valor.trim()) fields.push({ [c.tag]: c.valor })
      continue
    }
    const subfields = c.subcampos
      .filter((s) => s.valor.trim())
      .map((s) => ({ [s.codigo]: s.valor.trim() }))
    if (subfields.length) fields.push({ [c.tag]: { ind1: c.ind1 || " ", ind2: c.ind2 || " ", subfields } })
  }
  return { leader: lider, fields }
}

/** Vista "mnemónica" de MarcEdit, la misma que devuelve el backend. */
export function textoLegible(lider: string, campos: CampoEditor[]): string {
  const marc = aMarc(lider, campos)
  const lineas = [`=LDR  ${marc.leader}`]
  for (const f of [...marc.fields].sort((a, b) => Object.keys(a)[0].localeCompare(Object.keys(b)[0]))) {
    const [tag, valor] = Object.entries(f)[0]
    if (typeof valor === "string") {
      lineas.push(`=${tag}  ${valor.replaceAll(" ", "\\")}`)
    } else {
      const ind = `${valor.ind1}${valor.ind2}`.replaceAll(" ", "\\")
      const subs = valor.subfields.map((s) => Object.entries(s).map(([k, v]) => `$${k}${v}`).join("")).join("")
      lineas.push(`=${tag}  ${ind}${subs}`)
    }
  }
  return lineas.join("\n")
}

/** Inserta un campo respetando el orden por etiqueta (detrás de los de su misma etiqueta). */
export function insertarOrdenado(campos: CampoEditor[], nuevo: CampoEditor): CampoEditor[] {
  const i = campos.findIndex((c) => c.tag > nuevo.tag)
  return i === -1 ? [...campos, nuevo] : [...campos.slice(0, i), nuevo, ...campos.slice(i)]
}
