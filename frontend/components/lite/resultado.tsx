import Link from "next/link"

import type { ResultadoBusqueda } from "@/lib/types"

/** Marca de sessionStorage: la ficha se abrió desde la búsqueda, así que "volver" usa el historial. */
export const LLEGO_DE_BUSCAR = "shelfie:llego-de-buscar"

export function marcarLlegadaDeBuscar(valor: boolean) {
  try {
    if (valor) sessionStorage.setItem(LLEGO_DE_BUSCAR, "1")
    else sessionStorage.removeItem(LLEGO_DE_BUSCAR)
  } catch {
    // almacenamiento no disponible: "volver" lleva a la búsqueda vacía
  }
}

/** La cota, grande y en monoespaciada: es lo que la bibliotecaria busca en el estante. */
export function Cota({ cota, className = "" }: { cota: string | null; className?: string }) {
  return cota ? (
    <span aria-label="Cota" className={`font-mono text-2xl font-semibold text-foreground ${className}`}>
      {cota}
    </span>
  ) : (
    <span aria-label="Cota" className={`text-base text-muted-foreground ${className}`}>
      Sin cota
    </span>
  )
}

function textoEjemplares(n: number): string {
  return n === 1 ? "1 ejemplar" : `${n} ejemplares`
}

/** Un resultado de la búsqueda; todo él es el enlace a la ficha. */
export function Resultado({ r }: { r: ResultadoBusqueda }) {
  const edicion = [r.edicion, r.editorial, r.ano].filter((x) => x !== null && x !== "").join(" · ")

  return (
    <li>
      <Link
        href={`/libro/?id=${r.id}`}
        onClick={() => marcarLlegadaDeBuscar(true)}
        className="flex flex-col gap-1 rounded-lg border border-border bg-card p-4 transition-colors hover:bg-accent focus-visible:outline-none focus-visible:ring-[3px] focus-visible:ring-ring/50 sm:flex-row sm:items-start sm:gap-6"
      >
        <div className="sm:w-44 sm:shrink-0">
          <Cota cota={r.cota} />
        </div>
        <div className="min-w-0 flex-1">
          <p className="text-lg font-medium leading-snug text-foreground">
            {r.titulo}
            {r.subtitulo && <span className="font-normal text-muted-foreground">: {r.subtitulo}</span>}
          </p>
          {r.autor && <p className="text-sm text-foreground">{r.autor}</p>}
          <p className="mt-1 text-sm text-muted-foreground">
            {edicion && <span>{edicion}</span>}
            {edicion && " — "}
            <span>{textoEjemplares(r.ejemplares)}</span>
          </p>
        </div>
      </Link>
    </li>
  )
}
