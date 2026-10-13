import type { Metadata } from "next"

import { LectorProvider } from "@/components/opac/lector-provider"
import { OpacShell } from "@/components/opac/opac-shell"

export const metadata: Metadata = {
  title: "Catálogo en línea",
  description: "Busca en el catálogo de la biblioteca, reserva y consulta tu cuenta.",
}

/** El OPAC: público, con su propia sesión de lector y sin la barra de la intranet. */
export default function OpacLayout({ children }: { children: React.ReactNode }) {
  return (
    <LectorProvider>
      <OpacShell>{children}</OpacShell>
    </LectorProvider>
  )
}
