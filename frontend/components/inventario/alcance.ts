import type { InventarioResumen, ResultadoLectura } from "@/lib/types"

/** «Norte · 600 a 699 · Libro»: qué abarca un inventario. */
export function alcance(i: InventarioResumen) {
  const partes = [i.sede ?? "Todas las sedes"]
  if (i.signatura_desde || i.signatura_hasta) partes.push(`${i.signatura_desde ?? "…"} a ${i.signatura_hasta ?? "…"}`)
  if (i.tipo_item) partes.push(i.tipo_item)
  return partes.join(" · ")
}

/** Color de cada resultado: bien, a revisar o problema. */
export const TONO_RESULTADO: Record<ResultadoLectura, "bien" | "revisar" | "problema"> = {
  ok: "bien",
  devuelto: "bien",
  repetido: "revisar",
  fuera_de_lugar: "revisar",
  reservado: "revisar",
  en_transito: "revisar",
  prestado: "problema",
  perdido: "problema",
  retirado: "problema",
  desconocido: "problema",
}
