import { dirname } from "node:path"
import { fileURLToPath } from "node:url"

// La carpeta frontend/ es la raíz del proyecto de Next. Sin esto, Turbopack
// la deduce buscando lockfiles hacia arriba y puede terminar vigilando la raíz
// del repo (con el .venv) o hasta la carpeta del usuario: minutos compilando
// y la RAM al tope.
const raiz = dirname(fileURLToPath(import.meta.url))

/** @type {import('next').NextConfig} */
const nextConfig = {
  turbopack: {
    root: raiz,
  },
  outputFileTracingRoot: raiz,
  images: {
    unoptimized: true,
  },
}

export default nextConfig
