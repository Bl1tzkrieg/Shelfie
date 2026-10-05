import * as React from 'react'

const MOBILE_BREAKPOINT = 768

const QUERY = `(max-width: ${MOBILE_BREAKPOINT - 1}px)`

export function useIsMobile() {
  // useSyncExternalStore es el mecanismo previsto para leer de una fuente
  // externa como matchMedia: evita el setState dentro del efecto y entrega
  // el valor correcto ya en el primer render del cliente.
  return React.useSyncExternalStore(suscribir, leerCliente, leerServidor)
}

function suscribir(alCambiar: () => void) {
  const mql = window.matchMedia(QUERY)
  mql.addEventListener('change', alCambiar)
  return () => mql.removeEventListener('change', alCambiar)
}

function leerCliente() {
  return window.matchMedia(QUERY).matches
}

function leerServidor() {
  // Durante el render en servidor no hay viewport; se asume escritorio.
  return false
}
