import { existsSync, mkdirSync, readdirSync, rmSync } from "node:fs"
import path from "node:path"

import { expect, test, type Browser, type Page } from "@playwright/test"

import { ADMIN, CATALOGADOR, carpetaRespaldo } from "./entorno"

const HARPER = { titulo: "Bioquímica de Harper", cota: "612.015 H37", autor: "Murray, Robert K.", ejemplares: 2 }
const ANATOMIA = { titulo: "Anatomía humana descriptiva", cota: "611 L38", autor: "Latarjet, Michel", ejemplares: 1 }

if (!process.env.E2E_DATABASE_URL?.includes("e2e")) {
  throw new Error("Falta E2E_DATABASE_URL (base exclusiva de la prueba, con «e2e» en el nombre). Ver README.")
}

async function iniciarSesion(page: Page, usuario: string, clave: string) {
  await page.goto("/login/")
  await page.getByLabel("Usuario", { exact: true }).fill(usuario)
  await page.getByLabel("Contraseña", { exact: true }).fill(clave)
  await page.getByRole("button", { name: "Entrar" }).click()
  // Con la sesión abierta el formulario redirige; ir a otra página antes cortaría el inicio.
  await expect(page).not.toHaveURL(/\/login/)
}

/** La pantalla de clave provisional: aparece en cualquier página que no sea pública. */
async function elegirClave(page: Page, actual: string, nueva: string) {
  await expect(page.getByText(/Elige tu contraseña/)).toBeVisible()
  await page.getByLabel("Contraseña actual", { exact: true }).fill(actual)
  await page.getByLabel("Contraseña nueva", { exact: true }).fill(nueva)
  await page.getByLabel("Repite la nueva", { exact: true }).fill(nueva)
  await page.getByRole("button", { name: "Guardar y seguir" }).click()
  await expect(page.getByText(/Elige tu contraseña/)).toBeHidden()
}

async function nuevaSesion(browser: Browser) {
  const contexto = await browser.newContext()
  return { contexto, page: await contexto.newPage() }
}

async function ingresarLibro(page: Page, libro: typeof HARPER, boton: string) {
  await page.getByLabel(/^Cota/).fill(libro.cota)
  await page.getByLabel(/^Título/).fill(libro.titulo)
  await page.getByLabel("Autor principal", { exact: true }).fill(libro.autor)
  await page.getByLabel("N.º de ejemplares", { exact: true }).fill(String(libro.ejemplares))
  await page.getByRole("button", { name: boton }).click()
  await expect(page.getByText(`Guardado: ${libro.titulo} (${libro.cota})`)).toBeVisible()
  // El formulario queda limpio y con el cursor en Cota, listo para el siguiente.
  await expect(page.getByLabel(/^Cota/)).toHaveValue("")
  await expect(page.getByLabel(/^Cota/)).toBeFocused()
}

test("recorrido de Shelfie lite: ingreso, búsqueda pública y respaldo", async ({ browser, baseURL }) => {
  const carpeta = carpetaRespaldo()
  rmSync(carpeta, { recursive: true, force: true })
  mkdirSync(carpeta, { recursive: true })

  const admin = await nuevaSesion(browser)
  const cata = await nuevaSesion(browser)
  const publico = await nuevaSesion(browser)
  let id = ""

  await test.step("El administrador inicia sesión, cambia la clave provisional y crea un catalogador", async () => {
    await iniciarSesion(admin.page, ADMIN.usuario, ADMIN.claveTemporal)
    await admin.page.goto("/usuarios/")
    await elegirClave(admin.page, ADMIN.claveTemporal, ADMIN.claveNueva)

    await admin.page.getByRole("button", { name: "Nuevo", exact: true }).click()
    const dialogo = admin.page.getByRole("dialog", { name: "Nuevo usuario" })
    await dialogo.getByLabel("Usuario", { exact: true }).fill(CATALOGADOR.usuario)
    await dialogo.getByLabel("Nombre", { exact: true }).fill(CATALOGADOR.nombre)
    await dialogo.getByLabel("Apellido", { exact: true }).fill(CATALOGADOR.apellido)
    await dialogo.getByLabel("Clave temporal", { exact: true }).fill(CATALOGADOR.claveTemporal)
    await dialogo.getByRole("button", { name: "Crear usuario" }).click()
    await expect(admin.page.getByText(`Se creó el usuario ${CATALOGADOR.usuario}`)).toBeVisible()
    await expect(dialogo).toBeHidden()
  })

  await test.step("El catalogador elige su clave e ingresa dos libros con «Guardar y nuevo»", async () => {
    await iniciarSesion(cata.page, CATALOGADOR.usuario, CATALOGADOR.claveTemporal)
    await cata.page.goto("/ingreso/")
    await elegirClave(cata.page, CATALOGADOR.claveTemporal, CATALOGADOR.claveNueva)
    await expect(cata.page.getByLabel(/^Cota/)).toBeVisible()

    await ingresarLibro(cata.page, HARPER, "Guardar y nuevo")
    await ingresarLibro(cata.page, ANATOMIA, "Guardar y nuevo")
  })

  await test.step("Sin sesión, «bioquimica harper» da un resultado con la cota a la vista", async () => {
    const { page } = publico
    await page.goto("/")
    await page.getByRole("searchbox", { name: "Buscar en el catálogo" }).fill("bioquimica harper")
    const resultados = page.getByRole("region", { name: "Resultados" })
    await expect(resultados.getByRole("link")).toHaveCount(1)
    await expect(resultados.getByLabel("Cota")).toHaveText(HARPER.cota)
    await expect(resultados.getByText("2 ejemplares")).toBeVisible()
  })

  await test.step("Buscar por cota «612.015» lo encuentra", async () => {
    const { page } = publico
    await page.getByRole("searchbox", { name: "Buscar en el catálogo" }).fill("612.015")
    const resultados = page.getByRole("region", { name: "Resultados" })
    await expect(resultados.getByRole("link")).toHaveCount(1)
    await expect(resultados.getByText(HARPER.titulo)).toBeVisible()
    await expect(resultados.getByLabel("Cota")).toHaveText(HARPER.cota)
  })

  await test.step("La ficha pública muestra los 2 ejemplares", async () => {
    const { page } = publico
    await page.getByRole("region", { name: "Resultados" }).getByRole("link").click()
    await expect(page).toHaveURL(/\/libro\/\?id=\d+/)
    id = new URL(page.url()).searchParams.get("id") ?? ""
    expect(id).not.toBe("")
    await expect(page.getByRole("heading", { level: 1, name: HARPER.titulo })).toBeVisible()
    await expect(page.getByRole("heading", { level: 2, name: "Ejemplares (2)" })).toBeVisible()
  })

  await test.step("Editar sin cambiar nada y guardar deja el MARC idéntico, byte a byte", async () => {
    const { page } = cata
    // El MARC crudo solo lo ve el administrador (§8: /marc); el catalogador edita la ficha.
    const url = `${baseURL}/api/v1/catalog/items/${id}/marc`
    expect((await page.request.get(url)).status()).toBe(403)
    const antes = await admin.page.request.get(url)
    expect(antes.ok()).toBeTruthy()
    const marcAntes = await antes.text()

    await page.goto(`/ingreso/?id=${id}`)
    await expect(page.getByLabel(/^Título/)).toHaveValue(HARPER.titulo)
    await page.getByRole("button", { name: "Guardar", exact: true }).click()
    await expect(page).toHaveURL(new RegExp(`/libro/\\?id=${id}`))
    await expect(page.getByRole("heading", { level: 1, name: HARPER.titulo })).toBeVisible()

    const despues = await admin.page.request.get(url)
    expect(await despues.text()).toBe(marcAntes)
  })

  await test.step("El administrador hace «Respaldar ahora» y ve el resultado correcto", async () => {
    const { page } = admin
    await page.goto("/configuracion/")
    await page.getByLabel("Carpeta del respaldo", { exact: true }).fill(carpeta)
    if (process.env.E2E_PG_DUMP) {
      await page.getByLabel("Ruta de pg_dump", { exact: true }).fill(process.env.E2E_PG_DUMP)
    }
    await page.getByRole("button", { name: "Respaldar ahora" }).click()
    await expect(page.getByText(/Respaldo creado en/)).toBeVisible({ timeout: 60_000 })
    await expect(page.getByText(/^Correcto ·/)).toBeVisible()

    const creados = readdirSync(carpeta).filter((n) => /^shelfie-\d{8}-\d{4}$/.test(n))
    expect(creados).toHaveLength(1)
    for (const archivo of ["base.dump", "catalogo.mrc", "catalogo.xml", "catalogo.csv", "LEEME.txt"]) {
      expect(existsSync(path.join(carpeta, creados[0], archivo)), archivo).toBeTruthy()
    }
  })

  await Promise.all([admin.contexto.close(), cata.contexto.close(), publico.contexto.close()])
  rmSync(carpeta, { recursive: true, force: true })
})
