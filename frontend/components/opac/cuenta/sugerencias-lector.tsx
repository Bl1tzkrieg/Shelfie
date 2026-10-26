"use client"

import { useCallback, useEffect, useState } from "react"
import { Loader2 } from "lucide-react"
import { toast } from "sonner"

import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { Textarea } from "@/components/ui/textarea"
import { apiGet, apiPost, mensajeDeError } from "@/lib/api"
import type { EstadoSugerencia, SugerenciaLector } from "@/lib/opac"

const ESTADOS: Record<EstadoSugerencia, { texto: string; variante: "secondary" | "outline" | "default" | "destructive" }> = {
  Pendiente: { texto: "En revisión", variante: "outline" },
  Aceptada: { texto: "Aceptada", variante: "secondary" },
  Pedida: { texto: "Pedida al proveedor", variante: "default" },
  Rechazada: { texto: "No se comprará", variante: "destructive" },
}

const VACIA = { titulo: "", autor: "", isbn: "", editorial: "", ano: "", nota: "" }

export function SugerenciasLector() {
  const [sugerencias, setSugerencias] = useState<SugerenciaLector[] | null>(null)
  const [form, setForm] = useState(VACIA)
  const [enviando, setEnviando] = useState(false)

  const cargar = useCallback(async () => {
    try {
      setSugerencias(await apiGet<SugerenciaLector[]>("/opac/account/suggestions"))
    } catch (e) {
      toast.error("No se pudieron cargar tus sugerencias", { description: mensajeDeError(e) })
    }
  }, [])

  useEffect(() => {
    cargar()
  }, [cargar])

  async function enviar(e: React.FormEvent) {
    e.preventDefault()
    setEnviando(true)
    try {
      await apiPost("/opac/account/suggestions", {
        titulo: form.titulo.trim(),
        autor: form.autor.trim() || null,
        isbn: form.isbn.trim() || null,
        editorial: form.editorial.trim() || null,
        ano: form.ano ? Number(form.ano) : null,
        nota: form.nota.trim() || null,
      })
      toast.success("Sugerencia enviada", { description: "La biblioteca la revisará y verás aquí su respuesta." })
      setForm(VACIA)
      await cargar()
    } catch (e) {
      toast.error("No se pudo enviar", { description: mensajeDeError(e) })
    } finally {
      setEnviando(false)
    }
  }

  const campo = (clave: keyof typeof VACIA) => ({
    value: form[clave],
    onChange: (e: React.ChangeEvent<HTMLInputElement | HTMLTextAreaElement>) => setForm({ ...form, [clave]: e.target.value }),
  })

  return (
    <div className="grid gap-8 lg:grid-cols-[22rem_1fr]">
      <form onSubmit={enviar} className="space-y-3 rounded-lg border border-border bg-card shadow-papel p-4">
        <div>
          <h3 className="font-medium text-foreground">Sugerir una compra</h3>
          <p className="text-sm text-muted-foreground">¿Falta un libro? Cuéntanos cuál.</p>
        </div>
        <div className="space-y-1.5">
          <Label htmlFor="sug-titulo">Título</Label>
          <Input id="sug-titulo" required maxLength={500} {...campo("titulo")} />
        </div>
        <div className="space-y-1.5">
          <Label htmlFor="sug-autor">Autor</Label>
          <Input id="sug-autor" maxLength={300} {...campo("autor")} />
        </div>
        <div className="grid grid-cols-2 gap-3">
          <div className="space-y-1.5">
            <Label htmlFor="sug-isbn">ISBN</Label>
            <Input id="sug-isbn" maxLength={20} {...campo("isbn")} />
          </div>
          <div className="space-y-1.5">
            <Label htmlFor="sug-ano">Año</Label>
            <Input id="sug-ano" type="number" min={0} max={9999} {...campo("ano")} />
          </div>
        </div>
        <div className="space-y-1.5">
          <Label htmlFor="sug-editorial">Editorial</Label>
          <Input id="sug-editorial" maxLength={150} {...campo("editorial")} />
        </div>
        <div className="space-y-1.5">
          <Label htmlFor="sug-nota">¿Para qué lo necesitas?</Label>
          <Textarea id="sug-nota" rows={2} maxLength={1000} {...campo("nota")} />
        </div>
        <Button type="submit" className="w-full" disabled={enviando || !form.titulo.trim()}>
          {enviando && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}
          Enviar sugerencia
        </Button>
      </form>

      <section aria-label="Mis sugerencias">
        {!sugerencias ? (
          <Loader2 className="mx-auto my-8 h-5 w-5 animate-spin text-muted-foreground" />
        ) : sugerencias.length === 0 ? (
          <p className="py-8 text-center text-muted-foreground">No has sugerido nada todavía.</p>
        ) : (
          <ul className="space-y-3">
            {sugerencias.map((s) => (
              <li key={s.id} className="rounded-lg border border-border bg-card shadow-papel p-4">
                <div className="flex items-start justify-between gap-3">
                  <div className="min-w-0">
                    <p className="font-medium text-foreground">{s.titulo}</p>
                    <p className="text-sm text-muted-foreground">
                      {[s.autor, s.editorial, s.ano].filter(Boolean).join(" · ")}
                    </p>
                  </div>
                  <Badge variant={ESTADOS[s.estado].variante}>{ESTADOS[s.estado].texto}</Badge>
                </div>
                {s.motivo && <p className="mt-2 text-sm text-foreground">Respuesta: {s.motivo}</p>}
                <p className="mt-1 text-xs text-muted-foreground">Enviada el {s.fecha}</p>
              </li>
            ))}
          </ul>
        )}
      </section>
    </div>
  )
}
