"use client"

import { useState, useEffect } from "react"
import { AppLayout } from "@/components/layout/app-layout"
import { Header } from "@/components/layout/header"
import { UserFilters } from "@/components/usuarios/user-filters"
import { UserTable, User } from "@/components/usuarios/user-table"
import { Button } from "@/components/ui/button"
import { Plus, Download, Upload } from "lucide-react"
import Link from "next/link"

export default function UsuariosPage() {
  const [users, setUsers] = useState<User[]>([])
  const [isLoading, setIsLoading] = useState(true)

  // Carga de usuarios desde el Backend (FastAPI)
  useEffect(() => {
    async function fetchUsers() {
      try {
        const response = await fetch(`${process.env.NEXT_PUBLIC_API_URL}/users`, {
          cache: "no-store",
        })
        if (response.ok) {
          const data = await response.json()
          
          // Mapeamos los datos del backend a la interfaz que espera tu UserTable
          const mappedUsers = data.map((u: any) => {
            // 1. Determinar el estado visual del prototipo
            let calculatedStatus: "active" | "suspended" | "inactive" = "active"
            if (!u.activo) {
              calculatedStatus = "inactive"
            } else if (u.saldo_multas > 0) {
              calculatedStatus = "suspended"
            }

            // 2. Normalizar el tipo de usuario basado en el código de categoría obtenido
            const rawCode = u.categoria?.codigo?.toLowerCase() || ""
            let userType: "student" | "teacher" | "staff" = "student"
            
            if (rawCode === "doc" || rawCode === "docente") {
              userType = "teacher"
            } else if (rawCode === "adm" || rawCode === "staff") {
              userType = "staff"
            }

            return {
              id: u.nro_carnet,
              name: `${u.nombre} ${u.apellido}`,
              email: u.email,
              type: userType,
              department: u.departamento || "Ingeniería Agronómica",
              status: calculatedStatus,
              activeLoans: u.prestamos_activos_count || 0,
              totalLoans: u.total_prestamos_count || 0,
              registeredDate: u.fecha_registro ? new Date(u.fecha_registro).toLocaleDateString() : "2026",
            }
          })
          
          setUsers(mappedUsers)
        }
      } catch (error) {
        console.error("Error al obtener los usuarios:", error)
      } finally {
        setIsLoading(false)
      }
    }
    fetchUsers()
  }, [])

  // Métricas calculadas dinámicamente de la base de datos
  const activeUsers = users.filter(u => u.status === "active").length
  const suspendedUsers = users.filter(u => u.status === "suspended").length
  const usersWithActiveLoans = users.filter(u => u.activeLoans > 0).length

  return (
    <AppLayout>
      <Header 
        title="Usuarios" 
        description="Gestión de usuarios de la biblioteca"
      />
      
      <div className="p-6">
        {/* Stats Summary */}
        <div className="mb-6 grid gap-4 sm:grid-cols-4">
          <div className="rounded-lg border border-border bg-card p-4">
            <p className="text-sm text-muted-foreground">Total Usuarios</p>
            <p className="mt-1 text-2xl font-semibold text-foreground">{users.length}</p>
          </div>
          <div className="rounded-lg border border-border bg-card p-4">
            <p className="text-sm text-muted-foreground">Activos</p>
            <p className="mt-1 text-2xl font-semibold text-primary">{activeUsers}</p>
          </div>
          <div className="rounded-lg border border-destructive/30 bg-card p-4">
            <p className="text-sm text-muted-foreground">Suspendidos</p>
            <p className="mt-1 text-2xl font-semibold text-destructive">{suspendedUsers}</p>
          </div>
          <div className="rounded-lg border border-border bg-card p-4">
            <p className="text-sm text-muted-foreground">Con Préstamos Activos</p>
            <p className="mt-1 text-2xl font-semibold text-foreground">{usersWithActiveLoans}</p>
          </div>
        </div>

        {/* Action Bar */}
        <div className="mb-6 flex flex-col gap-4 sm:flex-row sm:items-start sm:justify-between">
          <div className="flex-1">
            <UserFilters />
          </div>
          <div className="flex gap-2">
            <Button variant="outline">
              <Upload className="mr-2 h-4 w-4" />
              Importar
            </Button>
            <Button variant="outline">
              <Download className="mr-2 h-4 w-4" />
              Exportar
            </Button>
            <Link href="/usuarios/nuevo">
              <Button>
                <Plus className="mr-2 h-4 w-4" />
                Nuevo Usuario
              </Button>
            </Link>
          </div>
        </div>

        {/* Table con manejador de carga */}
        {isLoading ? (
          <div className="text-center py-10 bg-card border rounded-lg text-muted-foreground">
            Cargando el padrón de usuarios...
          </div>
        ) : (
          <UserTable users={users} />
        )}

        {/* Pagination */}
        <div className="mt-6 flex items-center justify-between">
          <p className="text-sm text-muted-foreground">
            Mostrando <span className="font-medium text-foreground">{users.length}</span> de{" "}
            <span className="font-medium text-foreground">{users.length}</span> usuarios reales
          </p>
          <div className="flex gap-2">
            <Button variant="outline" size="sm" disabled>
              Anterior
            </Button>
            <Button variant="outline" size="sm" disabled>
              Siguiente
            </Button>
          </div>
        </div>
      </div>
    </AppLayout>
  )
}