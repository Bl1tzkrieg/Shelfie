import { clsx, type ClassValue } from 'clsx'
import { twMerge } from 'tailwind-merge'

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs))
}

/** Tamaño de un archivo en B, KB o MB, con el formato numérico de es-VE (p. ej. "1,5 MB"). */
export function tamanoLegible(bytes: number): string {
  const formato = (n: number) =>
    n.toLocaleString("es-VE", { maximumFractionDigits: 1 })
  if (bytes < 1024) return `${formato(bytes)} B`
  if (bytes < 1024 * 1024) return `${formato(bytes / 1024)} KB`
  return `${formato(bytes / (1024 * 1024))} MB`
}
