import { Construction } from "lucide-react"

/** Contenido provisorio de una pantalla de Shelfie-lite que todavía no se hizo. */
export function EnConstruccion({ children }: { children?: React.ReactNode }) {
  return (
    <div className="flex flex-col items-center gap-3 rounded-lg border border-dashed border-border p-10 text-center text-muted-foreground">
      <Construction className="h-8 w-8" aria-hidden />
      <p className="text-sm">En construcción.</p>
      {children}
    </div>
  )
}
