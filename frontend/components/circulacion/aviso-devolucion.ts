import { toast } from "sonner"

import type { ResultadoDevolucion } from "@/lib/types"

export type TonoInstruccion = "reserva" | "traslado" | "estante"

/** Qué hacer físicamente con el ejemplar, como la boleta de devolución de Koha. */
export function instruccionDevolucion(res: ResultadoDevolucion): {
  titulo: string
  detalle: string
  tono: TonoInstruccion
} {
  const r = res.reserva
  if (res.accion === "espera" && r) {
    return {
      titulo: "Al estante de reservas",
      detalle: `Apártalo para ${r.lector} (${r.carnet})${r.retirar_hasta ? `: tiene hasta el ${r.retirar_hasta} para retirarlo` : ""}.`,
      tono: "reserva",
    }
  }
  if (res.traslado) {
    const destino = res.traslado.hacia ?? "otra sede"
    const accion = res.traslado.enviado ? "Envíalo a" : "Por enviar a"
    return {
      titulo: `${accion} ${destino}`,
      detalle:
        res.traslado.motivo === "reserva" && r
          ? `Reserva de ${r.lector} (${r.carnet}), que lo retira en ${destino}.`
          : res.traslado.motivo === "retorno"
            ? "Vuelve a su sede propia."
            : "Traslado entre sedes.",
      tono: "traslado",
    }
  }
  return {
    titulo: "Al estante",
    detalle: `El ejemplar quedó ${res.nuevo_estado_item === "Disponible" ? "disponible" : res.nuevo_estado_item}.`,
    tono: "estante",
  }
}

/** Toast tras una devolución: multa o reintegro, y qué hacer con el ejemplar. */
export function avisarDevolucion(res: ResultadoDevolucion) {
  const partes: string[] = []
  const multa = Number(res.multa_aplicada || 0)
  const reintegro = Number(res.reintegro || 0)

  if (res.recuperado) {
    partes.push(
      reintegro > 0
        ? `Se acreditaron Bs. ${reintegro.toFixed(2)} de la reposición a ${res.lector_reintegro}.`
        : "No había cargo de reposición que reintegrar."
    )
  } else if (multa > 0) {
    partes.push(`Multa aplicada: Bs. ${multa.toFixed(2)}.`)
  }
  const instruccion = instruccionDevolucion(res)
  partes.push(`${instruccion.titulo}. ${instruccion.detalle}`)

  toast.success(res.recuperado ? "Ejemplar recuperado" : res.mensaje, {
    description: partes.join(" "),
    duration: instruccion.tono !== "estante" || reintegro > 0 ? 10000 : undefined,
  })
}
