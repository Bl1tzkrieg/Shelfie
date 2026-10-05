"use client"

import { useCallback, useEffect, useMemo, useRef, useState } from "react"
import { Plus, Download, Upload, Loader2 } from "lucide-react"
import { toast } from "sonner"

import { AppLayout } from "@/components/layout/app-layout"
import { Header } from "@/components/layout/header"
import {
  UserFilters,
  UserFilterState,
  FILTROS_USUARIO_VACIOS,
} from "@/components/usuarios/user-filters"
import { UserTable } from "@/components/usuarios/user-table"
import { UsuarioDialog } from "@/components/usuarios/usuario-dialog"
import { Button } from "@/components/ui/button"
import { apiDownload, apiGet, apiPost, mensajeDeError } from "@/lib/api"
import { mapUsuario, type ApiUser } from "@/lib/types"

const POR_PAGINA = 10

export default function UsuariosPage() {
  const [usuarios, setUsuarios] = useState<ApiUser[]>([])
  const [isLoading, setIsLoading] = useState(true)
  const [searchQuery, setSearchQuery] = useState("")
  const [filtros, setFiltros] = useState<UserFilterState>(FILTROS_USUARIO_VACIOS)
  const [pagina, setPagina] = useState(1)

  const [dialogAbierto, setDialogAbierto] = useState(false)
  const [enEdicion, setEnEdicion] = useState<ApiUser | null>(null)
  const [exportando, setExportando] = useState(false)
  const [importando, setImportando] = useState(false)
  const inputArchivo = useRef<HTMLInputElement>(null)

  const cargarUsuarios = useCallback(async () => {
    try {
      const data = await apiGet<ApiUser[]>("/users")
      setUsuarios(data)
    } catch (error) {
      toast.error("No se pudo cargar el padrón", { description: mensajeDeError(error) })
    } finally {
      setIsLoading(false)
    }
  }, [])

  useEffect(() => {
    cargarUsuarios()
  }, [cargarUsuarios])

  const mapeados = useMemo(() => usuarios.map(mapUsuario), [usuarios])

  const departamentos = useMemo(
    () => Array.from(new Set(mapeados.map((u) => u.department).filter(Boolean))).sort(),
    [mapeados]
  )

  const filtrados = useMemo(() => {
    const query = searchQuery.trim().toLowerCase()
    return mapeados.filter((u) => {
      if (query) {
        const coincide = [u.name, u.id, u.email].some((c) => c?.toLowerCase().includes(query))
        if (!coincide) return false
      }
      if (filtros.tipo !== "all" && u.type !== filtros.tipo) return false
      if (filtros.estado !== "all" && u.status !== filtros.estado) return false
      if (filtros.departamento !== "all" && u.department !== filtros.departamento) return false
      return true
    })
  }, [mapeados, searchQuery, filtros])

  // Al cambiar la búsqueda o los filtros se vuelve a la primera página.
  function cambiarBusqueda(q: string) {
    setSearchQuery(q)
    setPagina(1)
  }

  function cambiarFiltros(f: UserFilterState) {
    setFiltros(f)
    setPagina(1)
  }

  const totalPaginas = Math.max(1, Math.ceil(filtrados.length / POR_PAGINA))
  const paginaSegura = Math.min(pagina, totalPaginas)
  const visibles = filtrados.slice(
    (paginaSegura - 1) * POR_PAGINA,
    paginaSegura * POR_PAGINA
  )

  const activos = mapeados.filter((u) => u.status === "active").length
  const conMultas = mapeados.filter((u) => u.status === "suspended").length
  const conPrestamos = mapeados.filter((u) => u.activeLoans > 0).length

  function abrirNuevo() {
    setEnEdicion(null)
    setDialogAbierto(true)
  }

  function abrirEdicion(carnet: string) {
    const u = usuarios.find((x) => x.nro_carnet === carnet) || null
    setEnEdicion(u)
    setDialogAbierto(true)
  }

  async function exportar() {
    setExportando(true)
    try {
      await apiDownload("/users-export", "usuarios.csv")
      toast.success("Exportación lista", { description: "Se descargó el CSV del padrón." })
    } catch (error) {
      toast.error("No se pudo exportar", { description: mensajeDeError(error) })
    } finally {
      setExportando(false)
    }
  }

  async function importar(archivo: File) {
    setImportando(true)
    try {
      const texto = await archivo.text()
      const filas = parsearCSV(texto)
      if (filas.length === 0) {
        toast.error("El archivo no tiene filas válidas", {
          description: "Se esperan las columnas: nro_carnet, nombre, apellido, email.",
        })
        return
      }

      const res = await apiPost<{
        creados: number
        omitidos: { fila: number; carnet: string; motivo: string }[]
      }>("/users-import", filas)

      if (res.omitidos.length === 0) {
        toast.success(`${res.creados} usuario(s) importado(s)`)
      } else {
        toast.warning(`${res.creados} importado(s), ${res.omitidos.length} omitido(s)`, {
          description: res.omitidos
            .slice(0, 3)
            .map((o) => `Fila ${o.fila} (${o.carnet}): ${o.motivo}`)
            .join(" · "),
        })
      }
      cargarUsuarios()
    } catch (error) {
      toast.error("No se pudo importar", { description: mensajeDeError(error) })
    } finally {
      setImportando(false)
      if (inputArchivo.current) inputArchivo.current.value = ""
    }
  }

  return (
    <AppLayout>
      <Header title="Usuarios" description="Gestión de usuarios de la biblioteca" />

      <div className="p-6">
        <div className="mb-6 grid gap-4 sm:grid-cols-4">
          <div className="rounded-lg border border-border bg-card p-4">
            <p className="text-sm text-muted-foreground">Total Usuarios</p>
            <p className="mt-1 text-2xl font-semibold text-foreground">{mapeados.length}</p>
          </div>
          <div className="rounded-lg border border-border bg-card p-4">
            <p className="text-sm text-muted-foreground">Activos</p>
            <p className="mt-1 text-2xl font-semibold text-primary">{activos}</p>
          </div>
          <div className="rounded-lg border border-destructive/30 bg-card p-4">
            <p className="text-sm text-muted-foreground">Con multas</p>
            <p className="mt-1 text-2xl font-semibold text-destructive">{conMultas}</p>
          </div>
          <div className="rounded-lg border border-border bg-card p-4">
            <p className="text-sm text-muted-foreground">Con Préstamos Activos</p>
            <p className="mt-1 text-2xl font-semibold text-foreground">{conPrestamos}</p>
          </div>
        </div>

        <div className="mb-6 flex flex-col gap-4 lg:flex-row lg:items-start lg:justify-between">
          <div className="flex-1">
            <UserFilters
              searchQuery={searchQuery}
              onSearchChange={cambiarBusqueda}
              filtros={filtros}
              onFiltrosChange={cambiarFiltros}
              departamentos={departamentos}
            />
          </div>
          <div className="flex shrink-0 gap-2">
            <input
              ref={inputArchivo}
              type="file"
              accept=".csv,text/csv"
              className="hidden"
              onChange={(e) => {
                const f = e.target.files?.[0]
                if (f) importar(f)
              }}
            />
            <Button
              variant="outline"
              onClick={() => inputArchivo.current?.click()}
              disabled={importando}
            >
              {importando ? (
                <Loader2 className="mr-2 h-4 w-4 animate-spin" />
              ) : (
                <Upload className="mr-2 h-4 w-4" />
              )}
              Importar
            </Button>
            <Button variant="outline" onClick={exportar} disabled={exportando}>
              {exportando ? (
                <Loader2 className="mr-2 h-4 w-4 animate-spin" />
              ) : (
                <Download className="mr-2 h-4 w-4" />
              )}
              Exportar
            </Button>
            <Button onClick={abrirNuevo}>
              <Plus className="mr-2 h-4 w-4" />
              Nuevo Usuario
            </Button>
          </div>
        </div>

        {isLoading ? (
          <div className="rounded-lg border bg-card py-10 text-center text-muted-foreground">
            Cargando el padrón de usuarios...
          </div>
        ) : (
          <UserTable users={visibles} onEditar={abrirEdicion} onChange={cargarUsuarios} />
        )}

        <div className="mt-6 flex items-center justify-between">
          <p className="text-sm text-muted-foreground">
            Mostrando{" "}
            <span className="font-medium text-foreground">{visibles.length}</span> de{" "}
            <span className="font-medium text-foreground">{filtrados.length}</span> usuarios
            {filtrados.length !== mapeados.length && ` (${mapeados.length} en total)`}
          </p>
          <div className="flex items-center gap-2">
            <span className="text-sm text-muted-foreground">
              Página {paginaSegura} de {totalPaginas}
            </span>
            <Button
              variant="outline"
              size="sm"
              disabled={paginaSegura <= 1}
              onClick={() => setPagina((p) => Math.max(1, p - 1))}
            >
              Anterior
            </Button>
            <Button
              variant="outline"
              size="sm"
              disabled={paginaSegura >= totalPaginas}
              onClick={() => setPagina((p) => Math.min(totalPaginas, p + 1))}
            >
              Siguiente
            </Button>
          </div>
        </div>
      </div>

      <UsuarioDialog
        open={dialogAbierto}
        onOpenChange={setDialogAbierto}
        usuario={enEdicion}
        onSuccess={cargarUsuarios}
      />
    </AppLayout>
  )
}

/**
 * Parser CSV mínimo para la carga masiva: cabecera obligatoria y soporte de
 * comillas dobles. Suficiente para los archivos que exporta el propio sistema.
 */
function parsearCSV(texto: string) {
  const lineas = texto
    .replace(/^﻿/, "")
    .split(/\r?\n/)
    .filter((l) => l.trim() !== "")
  if (lineas.length < 2) return []

  const cabecera = dividirLinea(lineas[0]).map((h) => h.trim().toLowerCase())
  const filas = []

  for (const linea of lineas.slice(1)) {
    const celdas = dividirLinea(linea)
    const registro: Record<string, string> = {}
    cabecera.forEach((col, i) => {
      registro[col] = (celdas[i] ?? "").trim()
    })

    if (!registro.nro_carnet || !registro.nombre || !registro.apellido || !registro.email) {
      continue
    }

    filas.push({
      nro_carnet: registro.nro_carnet,
      nombre: registro.nombre,
      apellido: registro.apellido,
      email: registro.email,
      departamento: registro.departamento || null,
      categoria_codigo: registro.categoria_codigo || "EST",
    })
  }

  return filas
}

function dividirLinea(linea: string): string[] {
  const celdas: string[] = []
  let actual = ""
  let entreComillas = false

  for (let i = 0; i < linea.length; i++) {
    const c = linea[i]
    if (c === '"') {
      if (entreComillas && linea[i + 1] === '"') {
        actual += '"'
        i++
      } else {
        entreComillas = !entreComillas
      }
    } else if (c === "," && !entreComillas) {
      celdas.push(actual)
      actual = ""
    } else {
      actual += c
    }
  }
  celdas.push(actual)
  return celdas
}
