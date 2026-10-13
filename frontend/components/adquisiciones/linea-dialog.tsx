"use client"

import { useEffect, useRef, useState } from "react"
import { Check, Loader2, Search } from "lucide-react"
import { toast } from "sonner"

import type { Book } from "@/components/catalogo/book-card"
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
import { Tabs, TabsList, TabsTrigger } from "@/components/ui/tabs"
import { Textarea } from "@/components/ui/textarea"
import { apiGet, apiPost, apiPut, mensajeDeError } from "@/lib/api"
import type { BusquedaCatalogo, Fondo, LineaPedido, Pedido } from "@/lib/types"
import { cn } from "@/lib/utils"
import { bs, FondoSelect } from "./comun"

type Origen = "catalogo" | "nuevo"

/** Agregar un título al pedido (del catálogo o nuevo) o editar una línea existente. */
export function LineaDialog({
  open,
  pedido,
  linea,
  fondos,
  descuentoProveedor,
  onOpenChange,
  onGuardado,
}: {
  open: boolean
  pedido: Pedido
  /** Con línea, se edita; sin ella, se agrega. */
  linea: LineaPedido | null
  fondos: Fondo[]
  descuentoProveedor: number
  onOpenChange: (open: boolean) => void
  onGuardado: (p: Pedido) => void
}) {
  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-xl">
        {open && (
          <Formulario pedido={pedido} linea={linea} fondos={fondos}
                      descuentoProveedor={descuentoProveedor}
                      onCancel={() => onOpenChange(false)} onGuardado={onGuardado} />
        )}
      </DialogContent>
    </Dialog>
  )
}

function Formulario({
  pedido,
  linea,
  fondos,
  descuentoProveedor,
  onCancel,
  onGuardado,
}: {
  pedido: Pedido
  linea: LineaPedido | null
  fondos: Fondo[]
  descuentoProveedor: number
  onCancel: () => void
  onGuardado: (p: Pedido) => void
}) {
  const [origen, setOrigen] = useState<Origen>("catalogo")
  const [q, setQ] = useState("")
  const [resultados, setResultados] = useState<Book[] | null>(null)
  const [elegido, setElegido] = useState<Book | null>(null)
  const [titulo, setTitulo] = useState("")
  const [autor, setAutor] = useState("")
  const [isbn, setIsbn] = useState("")
  const [cantidad, setCantidad] = useState(String(linea?.cantidad ?? 1))
  const [precio, setPrecio] = useState(linea ? String(linea.precio_unitario) : "")
  const [descuento, setDescuento] = useState(String(linea?.descuento ?? descuentoProveedor))
  const [fondo, setFondo] = useState<number | null>(linea?.fondo_id ?? (fondos.length === 1 ? fondos[0].id : null))
  const [notas, setNotas] = useState(linea?.notas ?? "")
  const [enviando, setEnviando] = useState(false)
  const ultima = useRef(0)

  useEffect(() => {
    if (linea || origen !== "catalogo") return
    const texto = q.trim()
    if (texto.length < 2) {
      setResultados(null)
      return
    }
    const id = ++ultima.current
    const t = setTimeout(() => {
      apiGet<BusquedaCatalogo<Book>>(`/catalog/search?q=${encodeURIComponent(texto)}&por_pagina=6`)
        .then((r) => id === ultima.current && setResultados(r.resultados))
        .catch(() => id === ultima.current && setResultados([]))
    }, 250)
    return () => clearTimeout(t)
  }, [q, origen, linea])

  const n = Number(cantidad)
  const p = Number(precio)
  const d = Number(descuento)
  const valido =
    Number.isInteger(n) && n >= 1 && precio.trim() !== "" && p >= 0 && d >= 0 && d <= 100 &&
    (linea !== null || (origen === "catalogo" ? elegido !== null : titulo.trim() !== ""))
  const costo = Math.round(p * (100 - d)) / 100
  const fondoElegido = fondos.find((f) => f.id === fondo)
  const previo = linea && linea.fondo_id === fondo ? linea.total_estimado : 0
  const excede = fondoElegido && valido && costo * n > fondoElegido.disponible + previo

  async function guardar(e: React.FormEvent) {
    e.preventDefault()
    setEnviando(true)
    const comun = {
      cantidad: n,
      precio_unitario: p,
      descuento: d,
      fondo_id: fondo,
      notas: notas.trim() || null,
    }
    try {
      const r = linea
        ? await apiPut<Pedido>(`/acquisitions/orders/${pedido.id}/lines/${linea.id}`, comun)
        : await apiPost<Pedido>(`/acquisitions/orders/${pedido.id}/lines`, {
            ...comun,
            ...(origen === "catalogo"
              ? { biblio_id: Number(elegido!.id) }
              : { titulo: titulo.trim(), autor: autor.trim() || null, isbn: isbn.trim() || null }),
          })
      toast.success(linea ? "Línea actualizada" : "Título agregado al pedido")
      onGuardado(r)
    } catch (error) {
      toast.error("No se pudo guardar", { description: mensajeDeError(error) })
    } finally {
      setEnviando(false)
    }
  }

  return (
    <form onSubmit={guardar}>
      <DialogHeader>
        <DialogTitle>{linea ? `Editar: ${linea.titulo}` : "Agregar título"}</DialogTitle>
        <DialogDescription>
          {linea
            ? "Cantidad, precio, descuento, fondo y notas."
            : "Un registro del catálogo (más ejemplares) o uno nuevo, que se crea al pedirlo."}
        </DialogDescription>
      </DialogHeader>

      <div className="space-y-4 py-4">
        {!linea && (
          <Tabs value={origen} onValueChange={(v) => setOrigen(v as Origen)}>
            <TabsList>
              <TabsTrigger value="catalogo">Del catálogo</TabsTrigger>
              <TabsTrigger value="nuevo">Título nuevo</TabsTrigger>
            </TabsList>
          </Tabs>
        )}

        {!linea && origen === "catalogo" && (
          <div className="space-y-2">
            <Label htmlFor="linea-buscar">Buscar en el catálogo</Label>
            <div className="relative">
              <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
              <Input id="linea-buscar" className="pl-9" autoFocus value={q} placeholder="Título, autor o ISBN"
                     onChange={(e) => setQ(e.target.value)} />
            </div>
            {resultados !== null && (
              <ul className="max-h-48 divide-y divide-border overflow-y-auto rounded-md border border-border">
                {resultados.length === 0 && (
                  <li className="px-3 py-2 text-sm text-muted-foreground">
                    Sin resultados. Agrégalo como título nuevo.
                  </li>
                )}
                {resultados.map((b) => (
                  <li key={b.id}>
                    <button type="button" onClick={() => setElegido(b)}
                            className={cn("flex w-full items-center gap-3 px-3 py-2 text-left text-sm hover:bg-muted",
                                          elegido?.id === b.id && "bg-primary/10")}>
                      <span className="min-w-0 flex-1">
                        <span className="block truncate font-medium text-foreground">{b.title}</span>
                        <span className="block truncate text-xs text-muted-foreground">
                          {b.author} · {b.copies} ejemplar(es){b.isbn ? ` · ISBN ${b.isbn}` : ""}
                        </span>
                      </span>
                      {elegido?.id === b.id && <Check className="h-4 w-4 shrink-0 text-primary" />}
                    </button>
                  </li>
                ))}
              </ul>
            )}
          </div>
        )}

        {!linea && origen === "nuevo" && (
          <div className="grid gap-4 sm:grid-cols-2">
            <div className="space-y-2 sm:col-span-2">
              <Label htmlFor="linea-titulo">Título</Label>
              <Input id="linea-titulo" autoFocus value={titulo} onChange={(e) => setTitulo(e.target.value)} />
            </div>
            <div className="space-y-2">
              <Label htmlFor="linea-autor">Autor</Label>
              <Input id="linea-autor" value={autor} placeholder="Apellido, Nombre"
                     onChange={(e) => setAutor(e.target.value)} />
            </div>
            <div className="space-y-2">
              <Label htmlFor="linea-isbn">ISBN</Label>
              <Input id="linea-isbn" value={isbn} onChange={(e) => setIsbn(e.target.value)} />
            </div>
          </div>
        )}

        <div className="grid gap-4 sm:grid-cols-3">
          <div className="space-y-2">
            <Label htmlFor="linea-cantidad">Cantidad</Label>
            <Input id="linea-cantidad" type="number" min={1} required value={cantidad}
                   onChange={(e) => setCantidad(e.target.value)} />
          </div>
          <div className="space-y-2">
            <Label htmlFor="linea-precio">Precio de lista (Bs.)</Label>
            <Input id="linea-precio" type="number" min={0} step="0.01" required value={precio}
                   onChange={(e) => setPrecio(e.target.value)} />
          </div>
          <div className="space-y-2">
            <Label htmlFor="linea-descuento">Descuento (%)</Label>
            <Input id="linea-descuento" type="number" min={0} max={100} step="0.01" value={descuento}
                   onChange={(e) => setDescuento(e.target.value)} />
          </div>
        </div>

        <div className="space-y-2">
          <Label htmlFor="linea-fondo">Fondo</Label>
          <FondoSelect id="linea-fondo" fondos={fondos} valor={fondo} onChange={setFondo} />
          {valido && (
            <p className={cn("text-xs", excede ? "text-destructive" : "text-muted-foreground")}>
              Costo {bs(costo)} c/u · compromete {bs(costo * n)}
              {excede && ` · supera lo disponible del fondo (${bs(fondoElegido!.disponible + previo)})`}
            </p>
          )}
        </div>

        <div className="space-y-2">
          <Label htmlFor="linea-notas">Notas</Label>
          <Textarea id="linea-notas" rows={2} value={notas} onChange={(e) => setNotas(e.target.value)} />
        </div>
      </div>

      <DialogFooter>
        <Button type="button" variant="outline" onClick={onCancel}>
          Cancelar
        </Button>
        <Button type="submit" disabled={enviando || !valido || !!excede}>
          {enviando && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}
          {linea ? "Guardar" : "Agregar"}
        </Button>
      </DialogFooter>
    </form>
  )
}
