import { AppLayout } from "@/components/layout/app-layout"
import { Header } from "@/components/layout/header"
import { UserFilters } from "@/components/usuarios/user-filters"
import { UserTable, User } from "@/components/usuarios/user-table"
import { Button } from "@/components/ui/button"
import { Plus, Download, Upload } from "lucide-react"
import Link from "next/link"

const users: User[] = [
  {
    id: "EST-2024-0145",
    name: "Carlos Mendoza López",
    email: "carlos.mendoza@unagro.edu",
    type: "student",
    department: "Ingeniería Agronómica",
    status: "active",
    activeLoans: 2,
    totalLoans: 15,
    registeredDate: "15 Ene 2024",
  },
  {
    id: "EST-2023-0089",
    name: "Ana García Pérez",
    email: "ana.garcia@unagro.edu",
    type: "student",
    department: "Zootecnia",
    status: "suspended",
    activeLoans: 1,
    totalLoans: 8,
    registeredDate: "20 Ago 2023",
  },
  {
    id: "DOC-2019-0023",
    name: "Dr. Roberto Jiménez Vargas",
    email: "r.jimenez@unagro.edu",
    type: "teacher",
    department: "Ciencias del Suelo",
    status: "active",
    activeLoans: 5,
    totalLoans: 87,
    registeredDate: "01 Mar 2019",
  },
  {
    id: "EST-2024-0201",
    name: "Laura Sánchez Mora",
    email: "laura.sanchez@unagro.edu",
    type: "student",
    department: "Ingeniería Forestal",
    status: "active",
    activeLoans: 1,
    totalLoans: 4,
    registeredDate: "10 Feb 2024",
  },
  {
    id: "DOC-2015-0012",
    name: "Dra. María Fernández Castro",
    email: "m.fernandez@unagro.edu",
    type: "teacher",
    department: "Botánica",
    status: "active",
    activeLoans: 3,
    totalLoans: 124,
    registeredDate: "15 Jun 2015",
  },
  {
    id: "ADM-2020-0005",
    name: "José Ramírez Torres",
    email: "j.ramirez@unagro.edu",
    type: "staff",
    department: "Biblioteca Central",
    status: "active",
    activeLoans: 0,
    totalLoans: 12,
    registeredDate: "05 Sep 2020",
  },
  {
    id: "EST-2022-0167",
    name: "Miguel Torres Ruiz",
    email: "miguel.torres@unagro.edu",
    type: "student",
    department: "Ciencias Ambientales",
    status: "inactive",
    activeLoans: 0,
    totalLoans: 23,
    registeredDate: "12 Mar 2022",
  },
  {
    id: "EST-2023-0145",
    name: "Pedro Ruiz García",
    email: "pedro.ruiz@unagro.edu",
    type: "student",
    department: "Ingeniería Agronómica",
    status: "active",
    activeLoans: 0,
    totalLoans: 11,
    registeredDate: "28 Jul 2023",
  },
]

export default function UsuariosPage() {
  const activeUsers = users.filter(u => u.status === "active").length
  const suspendedUsers = users.filter(u => u.status === "suspended").length

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
            <p className="mt-1 text-2xl font-semibold text-foreground">
              {users.filter(u => u.activeLoans > 0).length}
            </p>
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

        {/* Table */}
        <UserTable users={users} />

        {/* Pagination */}
        <div className="mt-6 flex items-center justify-between">
          <p className="text-sm text-muted-foreground">
            Mostrando <span className="font-medium text-foreground">{users.length}</span> de{" "}
            <span className="font-medium text-foreground">2,456</span> usuarios
          </p>
          <div className="flex gap-2">
            <Button variant="outline" size="sm" disabled>
              Anterior
            </Button>
            <Button variant="outline" size="sm">
              Siguiente
            </Button>
          </div>
        </div>
      </div>
    </AppLayout>
  )
}
