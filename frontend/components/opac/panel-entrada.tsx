import { FondoGeometrico } from "@/components/layout/fondo-geometrico"

/** Marco de las pantallas de entrada del lector (entrar, recuperar la contraseña): la tarjeta
 *  flota sobre el mismo fondo navy del login de la intranet. */
export function PanelEntrada({ children }: { children: React.ReactNode }) {
  return (
    <div className="relative isolate flex items-center justify-center overflow-hidden rounded-2xl px-3 py-10 shadow-papel-flotante sm:px-4 sm:py-16">
      <FondoGeometrico pantalla />
      <div className="w-full max-w-sm rounded-2xl border border-white/10 bg-card p-8 shadow-papel-flotante">
        {children}
      </div>
    </div>
  )
}
