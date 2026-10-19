/**
 * Fechas en la zona horaria de la biblioteca, no en la del navegador: el vencimiento es
 * las 23:59:59 de Caracas (03:59:59Z del día siguiente) y un equipo en otra zona mostraría
 * un día de más. Debe coincidir con ZONA_HORARIA del backend.
 */
export const ZONA_BIBLIOTECA = process.env.NEXT_PUBLIC_ZONA_HORARIA || "America/Caracas"

/** Instante ISO (con hora) → "19/10/2026" en la zona de la biblioteca. */
export function fechaDeBiblioteca(iso: string, opciones: Intl.DateTimeFormatOptions = {}) {
  return new Date(iso).toLocaleDateString("es-VE", { timeZone: ZONA_BIBLIOTECA, ...opciones })
}
