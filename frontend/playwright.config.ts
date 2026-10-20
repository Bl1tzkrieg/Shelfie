import { defineConfig } from "@playwright/test"

import { ADMIN, URL_BASE } from "./e2e/entorno"

/**
 * Recorrido de punta a punta contra uvicorn (:8080) sirviendo frontend/out, con una base
 * exclusiva (E2E_DATABASE_URL). Requiere `npm run build` hecho. Ver README, «Desarrollo».
 */
export default defineConfig({
  testDir: "./e2e",
  timeout: 180_000,
  expect: { timeout: 15_000 },
  fullyParallel: false,
  workers: 1,
  retries: 0,
  reporter: [["list"]],
  use: {
    baseURL: URL_BASE,
    locale: "es-VE",
    trace: "retain-on-failure",
    screenshot: "only-on-failure",
  },
  webServer: {
    command: "node e2e/servidor.mjs",
    url: `${URL_BASE}/api/v1/auth/me`,
    ignoreHTTPSErrors: true,
    reuseExistingServer: false,
    timeout: 120_000,
    stdout: "ignore",
    stderr: "pipe",
    gracefulShutdown: { signal: "SIGTERM", timeout: 5_000 },
    env: { E2E_ADMIN_USUARIO: ADMIN.usuario, E2E_ADMIN_CLAVE: ADMIN.claveTemporal },
  },
})
