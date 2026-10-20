"use client"

import { createContext, useCallback, useContext, useEffect, useMemo, useRef, useState } from "react"
import { usePathname, useRouter } from "next/navigation"
import { Loader2 } from "lucide-react"

import { apiGet, apiPost, ApiError, EVENTO_SESION_EXPIRADA } from "@/lib/api"
import type { Permiso, Sesion } from "@/lib/types"
import { ClaveObligatoria } from "@/components/auth/clave-obligatoria"

type EstadoSesion = {
  usuario: Sesion | null
  cargando: boolean
  tienePermiso: (permiso: Permiso) => boolean
  iniciarSesion: (username: string, password: string) => Promise<void>
  cerrarSesion: () => Promise<void>
  /** Vuelve a leer /auth/me (p. ej. tras un respaldo, que cambia `alerta_respaldo`). */
  recargarSesion: () => Promise<void>
}

const SesionContext = createContext<EstadoSesion | null>(null)

/** Rutas que se ven sin sesión: la búsqueda, la ficha de un libro y el login. */
const RUTAS_PUBLICAS = ["/", "/libro", "/login"]

function esRutaPublica(pathname: string) {
  // Con `trailingSlash` la ruta puede llegar como "/libro/".
  const ruta = pathname.length > 1 && pathname.endsWith("/") ? pathname.slice(0, -1) : pathname
  return RUTAS_PUBLICAS.includes(ruta)
}

/** La página actual con su query string, si `pathname` es la que se está viendo. */
function conBusqueda(pathname: string) {
  return typeof window !== "undefined" && window.location.pathname === pathname
    ? pathname + window.location.search
    : pathname
}

/** Ruta de login con la página actual como destino de regreso. */
export function rutaDeLogin(destino: string) {
  return destino && destino !== "/" ? `/login?next=${encodeURIComponent(destino)}` : "/login"
}

export function SesionProvider({ children }: { children: React.ReactNode }) {
  const router = useRouter()
  const pathname = usePathname()
  const [usuario, setUsuario] = useState<Sesion | null>(null)
  const [cargando, setCargando] = useState(true)
  // Al cerrar sesión a propósito no se recuerda la página: la próxima persona
  // que entre no debe aterrizar donde estaba la anterior.
  const saliendo = useRef(false)

  useEffect(() => {
    // La cookie es httpOnly: la única forma de saber si hay sesión es preguntarle al backend.
    apiGet<Sesion>("/auth/me")
      .then(setUsuario)
      .catch(() => setUsuario(null))
      .finally(() => setCargando(false))
  }, [])

  useEffect(() => {
    function alExpirar() {
      setUsuario(null)
      if (!esRutaPublica(pathname)) router.replace(rutaDeLogin(conBusqueda(pathname)))
    }
    window.addEventListener(EVENTO_SESION_EXPIRADA, alExpirar)
    return () => window.removeEventListener(EVENTO_SESION_EXPIRADA, alExpirar)
  }, [pathname, router])

  const iniciarSesion = useCallback(async (username: string, password: string) => {
    const r = await apiPost<{ usuario: Sesion }>("/auth/login", { username, password })
    setUsuario(r.usuario)
  }, [])

  const cerrarSesion = useCallback(async () => {
    saliendo.current = true
    try {
      await apiPost("/auth/logout")
    } catch (error) {
      // Aunque el backend no responda, la sesión local se descarta igual.
      if (!(error instanceof ApiError)) throw error
    } finally {
      setUsuario(null)
      router.replace("/login")
    }
  }, [router])

  const recargarSesion = useCallback(async () => {
    try {
      setUsuario(await apiGet<Sesion>("/auth/me"))
    } catch {
      // Si falla, queda la sesión que ya había: un 401 lo atiende el evento de sesión expirada.
    }
  }, [])

  const tienePermiso = useCallback(
    (permiso: Permiso) =>
      !!usuario &&
      (usuario.permisos.includes("superbibliotecario") || usuario.permisos.includes(permiso)),
    [usuario],
  )

  const valor = useMemo(
    () => ({ usuario, cargando, tienePermiso, iniciarSesion, cerrarSesion, recargarSesion }),
    [usuario, cargando, tienePermiso, iniciarSesion, cerrarSesion, recargarSesion],
  )

  const esPublica = esRutaPublica(pathname)

  useEffect(() => {
    if (esPublica) {
      saliendo.current = false
      return
    }
    if (!cargando && !usuario) {
      router.replace(saliendo.current ? "/login" : rutaDeLogin(conBusqueda(pathname)))
    }
  }, [cargando, usuario, esPublica, pathname, router])

  // Las páginas privadas no se montan sin sesión: así no disparan peticiones
  // que terminarían en 401 antes de redirigir al login.
  const puedeMostrar = esPublica || (!cargando && usuario !== null)

  // Con la contraseña provisional el backend rechaza todo lo demás (403):
  // antes de montar la intranet se pide la nueva.
  if (puedeMostrar && !esPublica && usuario?.debe_cambiar_clave) {
    return (
      <SesionContext.Provider value={valor}>
        <ClaveObligatoria
          nombre={usuario.nombre}
          ruta="/auth/password"
          onListo={() => setUsuario({ ...usuario, debe_cambiar_clave: false })}
          onSalir={cerrarSesion}
        />
      </SesionContext.Provider>
    )
  }

  return (
    <SesionContext.Provider value={valor}>
      {puedeMostrar ? (
        children
      ) : (
        <div className="flex min-h-screen items-center justify-center bg-background text-muted-foreground">
          <Loader2 className="mr-2 h-5 w-5 animate-spin" />
          Verificando sesión…
        </div>
      )}
    </SesionContext.Provider>
  )
}

export function useSesion(): EstadoSesion {
  const contexto = useContext(SesionContext)
  if (!contexto) throw new Error("useSesion debe usarse dentro de <SesionProvider>")
  return contexto
}
