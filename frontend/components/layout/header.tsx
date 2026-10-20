import { AvisoRespaldo } from "@/components/lite/aviso-respaldo"

interface HeaderProps {
  title: string
  description?: string
  /** Acciones de la pantalla, a la derecha del título. */
  children?: React.ReactNode
}

/** Título de una pantalla de la intranet. */
export function Header({ title, description, children }: HeaderProps) {
  return (
    <>
    <AvisoRespaldo />
    <header className="sticky top-14 z-30 flex h-16 items-center justify-between gap-3 border-b border-border bg-card px-4 sm:px-6 lg:top-0">
      <div className="min-w-0">
        <h1 className="truncate text-lg font-semibold text-foreground">{title}</h1>
        {description && <p className="hidden truncate text-sm text-muted-foreground sm:block">{description}</p>}
      </div>
      {children && <div className="flex items-center gap-2">{children}</div>}
    </header>
    </>
  )
}
