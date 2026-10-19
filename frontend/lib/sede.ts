/**
 * Sede de trabajo del personal (el "Set library" de Koha): dónde está físicamente
 * quien opera. Se guarda en este navegador y viaja en cada petición en la cabecera
 * `X-Shelfie-Sede`; sin ella, el backend usa la sede del usuario.
 */

const CLAVE = "shelfie:sede"
export const CABECERA_SEDE = "X-Shelfie-Sede"
export const EVENTO_SEDE = "shelfie:sede-cambiada"

export function leerSede(): number | null {
  if (typeof window === "undefined") return null
  try {
    const valor = window.localStorage.getItem(CLAVE)
    return valor && /^\d+$/.test(valor) ? Number(valor) : null
  } catch {
    return null
  }
}

export function guardarSede(id: number | null) {
  try {
    if (id === null) window.localStorage.removeItem(CLAVE)
    else window.localStorage.setItem(CLAVE, String(id))
  } catch {
    // Sin almacenamiento (modo privado estricto): se usa la sede del usuario.
  }
  window.dispatchEvent(new Event(EVENTO_SEDE))
}

/**
 * La sede que resolvió el proveedor (elegida, la del usuario o la primera). Vive en memoria,
 * no en el navegador: así viaja siempre en las peticiones y la intranet y el backend operan
 * con la misma sede, sin que una persona herede la de quien usó antes el equipo.
 */
let sedeEfectiva: number | null = null

export function fijarSedeEfectiva(id: number | null) {
  sedeEfectiva = id
}

export function cabeceraDeSede(): Record<string, string> {
  const sede = leerSede() ?? sedeEfectiva
  return sede === null ? {} : { [CABECERA_SEDE]: String(sede) }
}
