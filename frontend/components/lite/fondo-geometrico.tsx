import { useId } from "react"

import { cn } from "@/lib/utils"

// Tonos del motivo: navy más claro que el fondo y teal translúcido. Van en el SVG y no en
// clases porque son decorativos: no cambian con el tema ni llevan texto encima.
const NAVY_1 = "oklch(0.30 0.06 248)"
const NAVY_2 = "oklch(0.35 0.065 242)"
const NAVY_3 = "oklch(0.41 0.06 236)"
const TEAL = "oklch(0.70 0.12 185)"
const SOMBRA = "oklch(0.10 0.04 250)"

/** Lomos del estante: [x, alto, ancho, color, opacidad]. Se apoyan en la repisa (y = 318). */
const LOMOS: [number, number, number, string, number][] = [
  [292, 118, 26, NAVY_3, 1],
  [322, 150, 22, NAVY_2, 1],
  [348, 132, 30, TEAL, 0.5],
  [382, 164, 24, NAVY_3, 1],
  [410, 124, 20, NAVY_2, 1],
]
const REPISA = 318

/**
 * Fondo decorativo de Buscar y del login: hojas superpuestas, círculos y un estante
 * abstracto, en SVG en línea (no descarga nada). Ocupa todo su contenedor, que debe ser
 * `relative` y `overflow-hidden`. `compacto` lo vuelve más discreto (franja de resultados);
 * `pantalla` lo ajusta a un fondo de página entera (login), donde el estante no debe crecer
 * con la altura.
 */
export function FondoGeometrico({
  compacto = false,
  pantalla = false,
  className,
}: {
  compacto?: boolean
  pantalla?: boolean
  className?: string
}) {
  // useId da caracteres que url(#…) no acepta sin escapar: se dejan solo letras y números.
  const base = `fg${useId().replace(/[^a-zA-Z0-9]/g, "")}`
  const sombra = `${base}-sombra`
  const puntos = `${base}-puntos`
  const brillo = `${base}-brillo`

  return (
    <div
      aria-hidden
      className={cn("pointer-events-none absolute inset-0 -z-10 overflow-hidden select-none", className)}
    >
      <div className="absolute inset-0 bg-linear-to-br from-hero via-hero to-[oklch(0.29_0.07_232)]" />

      {/* Trama de puntos, muy tenue, para que el navy no se vea plano. */}
      <svg className="absolute inset-0 h-full w-full opacity-[0.14]">
        <defs>
          <pattern id={puntos} width="22" height="22" patternUnits="userSpaceOnUse">
            <circle cx="2" cy="2" r="1.2" fill="oklch(0.92 0.02 215)" />
          </pattern>
        </defs>
        <rect width="100%" height="100%" fill={`url(#${puntos})`} />
      </svg>

      {/* Arco grande a la izquierda. */}
      <svg
        viewBox="0 0 200 200"
        className={cn(
          "absolute -left-24 -top-28 h-72 w-72 transition-opacity duration-500 motion-reduce:transition-none sm:-left-16",
          pantalla && "sm:-left-20 sm:-top-32 sm:h-[26rem] sm:w-[26rem]",
          compacto ? "opacity-40" : "opacity-100",
        )}
      >
        <circle cx="100" cy="100" r="78" fill="none" stroke={TEAL} strokeOpacity="0.35" strokeWidth="1.5" />
        <circle cx="100" cy="100" r="58" fill={NAVY_1} fillOpacity="0.9" />
        <path d="M 22 100 A 78 78 0 0 1 100 22" fill="none" stroke={TEAL} strokeOpacity="0.8"
              strokeWidth="5" strokeLinecap="round" />
      </svg>

      {/* Hojas de papel apiladas, círculo teal y el estante. */}
      <svg
        viewBox="0 0 520 360"
        className={cn(
          // overflow-visible: el círculo sobresale del viewBox y no debe verse cortado.
          "absolute bottom-0 right-0 aspect-[520/360] w-auto max-w-none origin-bottom-right overflow-visible",
          "transition-[opacity,transform] duration-500 ease-out motion-reduce:transition-none",
          pantalla
            ? "h-[58vh] max-h-[34rem] min-h-80 translate-x-[30%] opacity-70 sm:translate-x-[8%] sm:opacity-90"
            : "translate-x-[38%] opacity-60 sm:translate-x-[12%] sm:opacity-100 lg:translate-x-0",
          !pantalla && (compacto ? "h-[180%] scale-90 opacity-35 sm:opacity-45" : "h-[115%]"),
        )}
      >
        <defs>
          <filter id={sombra} x="-30%" y="-30%" width="160%" height="170%">
            <feDropShadow dx="0" dy="10" stdDeviation="12" floodColor={SOMBRA} floodOpacity="0.55" />
          </filter>
          <radialGradient id={brillo} cx="0.35" cy="0.35" r="0.75">
            <stop offset="0" stopColor={TEAL} stopOpacity="0.42" />
            <stop offset="1" stopColor={TEAL} stopOpacity="0.08" />
          </radialGradient>
        </defs>

        <circle cx="390" cy="110" r="128" fill={`url(#${brillo})`} />
        <circle cx="390" cy="110" r="168" fill="none" stroke={TEAL} strokeOpacity="0.22" strokeWidth="1.5"
                strokeDasharray="2 10" strokeLinecap="round" />

        <g filter={`url(#${sombra})`}>
          <rect x="96" y="148" width="250" height="168" rx="24" fill={NAVY_1} transform="rotate(-9 221 232)" />
          <rect x="176" y="92" width="226" height="150" rx="24" fill={NAVY_2} transform="rotate(5 289 167)" />
          <rect x="132" y="70" width="92" height="92" rx="20" fill={TEAL} fillOpacity="0.28"
                transform="rotate(-14 178 116)" />
        </g>

        <g filter={`url(#${sombra})`}>
          {LOMOS.map(([x, alto, ancho, color, opacidad]) => (
            <rect key={x} x={x} y={REPISA - alto} width={ancho} height={alto} rx="5"
                  fill={color} fillOpacity={opacidad} />
          ))}
          {/* Un libro inclinado, apoyado en el último lomo. */}
          <rect x="440" y={REPISA - 140} width="24" height="140" rx="5" fill={NAVY_3}
                transform={`rotate(-14 464 ${REPISA})`} />
          <rect x="270" y={REPISA} width="230" height="8" rx="4" fill={TEAL} fillOpacity="0.7" />
        </g>
      </svg>
    </div>
  )
}
