// Prepara la base de prueba y deja corriendo uvicorn en :8080 sirviendo ../frontend/out.
// Lo lanza `webServer` de playwright.config.ts. Se hace aquí y no en un globalSetup porque
// Playwright arranca el servidor ANTES que el globalSetup, y la API necesita la base lista.
//
// Entorno:
//   E2E_DATABASE_URL  (obligatoria) base exclusiva de la prueba: su nombre debe contener "e2e".
//                     SE BORRA ENTERA en cada corrida.
//   E2E_PYTHON        el Python con las dependencias del backend (por defecto `python` en
//                     Windows y `python3` en el resto); en el repo, el del .venv de la raíz.
import { spawn, spawnSync } from "node:child_process"
import { existsSync } from "node:fs"
import path from "node:path"
import { fileURLToPath } from "node:url"

const aca = path.dirname(fileURLToPath(import.meta.url))
const backend = path.resolve(aca, "../../backend")
const salida = path.resolve(aca, "../out")

function abortar(mensaje) {
  console.error(`\n[e2e] ${mensaje}\n`)
  process.exit(1)
}

const urlBase = process.env.E2E_DATABASE_URL
if (!urlBase) {
  abortar("Falta E2E_DATABASE_URL, la base EXCLUSIVA de la prueba (se borra entera), p. ej. "
    + "postgresql://shelfie:clave@localhost:5432/shelfie_e2e")
}
const nombreBase = decodeURIComponent(new URL(urlBase).pathname.replace(/^\//, ""))
if (!nombreBase.includes("e2e")) {
  abortar(`La base "${nombreBase}" no parece de prueba: su nombre debe contener "e2e". `
    + "No se toca ninguna otra base.")
}
if (!existsSync(path.join(salida, "index.html"))) {
  abortar("No existe frontend/out. Corre antes `npm run build` (desde frontend/).")
}

if (!process.env.E2E_ADMIN_USUARIO || !process.env.E2E_ADMIN_CLAVE) {
  abortar("Falta E2E_ADMIN_USUARIO / E2E_ADMIN_CLAVE: los define playwright.config.ts; "
    + "lanza este script con `npx playwright test`.")
}

const python = process.env.E2E_PYTHON || (process.platform === "win32" ? "python" : "python3")
const entorno = { ...process.env, DATABASE_URL: urlBase, FRONTEND_DIR: salida, PYTHONUTF8: "1" }

function correr(titulo, argumentos) {
  const r = spawnSync(python, argumentos, { cwd: backend, env: entorno, encoding: "utf8" })
  if (r.error) abortar(`${titulo}: no se pudo ejecutar "${python}" (${r.error.message}). Define E2E_PYTHON.`)
  if (r.status !== 0) abortar(`${titulo} falló:\n${r.stdout ?? ""}${r.stderr ?? ""}`)
}

// 1. Base en blanco.
correr("Reiniciar la base", ["-c", [
  "from sqlalchemy import text",
  "from app.database import engine",
  "with engine.begin() as c:",
  "    c.execute(text('DROP SCHEMA IF EXISTS public CASCADE'))",
  "    c.execute(text('CREATE SCHEMA public'))",
].join("\n")])

// 2. Esquema.
correr("alembic upgrade head", ["-m", "alembic", "upgrade", "head"])

// 3. Primer administrador, con clave temporal (se le pedirá cambiarla). `scripts.crear_admin`
//    es interactivo (getpass no lee de una tubería en Windows), así que se hace lo mismo
//    por código: usuario con permiso superbibliotecario y debe_cambiar_clave.
correr("Crear el administrador", ["-c", [
  "import os",
  "from app import models",
  "from app.core.permisos import Permiso",
  "from app.database import SessionLocal",
  "from app.security import hash_password",
  "db = SessionLocal()",
  "db.add(models.Usuario(username=os.environ['E2E_ADMIN_USUARIO'], nombre='Admin', apellido='Prueba',",
  "    password_hash=hash_password(os.environ['E2E_ADMIN_CLAVE']), debe_cambiar_clave=True,",
  "    permisos=[Permiso.SUPERBIBLIOTECARIO.value]))",
  "db.commit()",
].join("\n")])

// 4. Servidor. Queda en primer plano; Playwright lo cierra al terminar.
const servidor = spawn(python, ["-m", "uvicorn", "app.main:app", "--host", "127.0.0.1", "--port", "8080"],
  { cwd: backend, env: entorno, stdio: "inherit" })
servidor.on("exit", (codigo) => process.exit(codigo ?? 0))
for (const senal of ["SIGINT", "SIGTERM"]) process.on(senal, () => servidor.kill())
