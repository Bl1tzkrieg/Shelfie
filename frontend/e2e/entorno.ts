import { tmpdir } from "node:os"
import path from "node:path"

/** Lo que comparten la configuración, el servidor de prueba y el recorrido. */
export const PUERTO = 8080
export const URL_BASE = `http://localhost:${PUERTO}`

export const ADMIN = { usuario: "e2e.admin", nombre: "Admin", apellido: "Prueba",
                       claveTemporal: "Temporal-e2e-1", claveNueva: "ClaveNueva-e2e-1" }
export const CATALOGADOR = { usuario: "e2e.cata", nombre: "Cata", apellido: "Logadora",
                             claveTemporal: "Cata-temporal-1", claveNueva: "Cata-nueva-e2e-1" }

/** Carpeta de respaldos de la prueba: la fija E2E_RESPALDO_DIR o una nueva bajo la carpeta temporal. */
export function carpetaRespaldo(): string {
  return process.env.E2E_RESPALDO_DIR || path.join(tmpdir(), "shelfie-e2e-respaldos")
}
