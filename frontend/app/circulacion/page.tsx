"use client"

import { useState } from "react"
import { AppLayout } from "@/components/layout/app-layout"
import { Header } from "@/components/layout/header"
import { LoanFilters } from "@/components/circulacion/loan-filters"
import { LoanTable, Loan } from "@/components/circulacion/loan-table"
import { Button } from "@/components/ui/button"
import { Plus, Download } from "lucide-react"
import Link from "next/link"

const activeLoans: Loan[] = [
  {
    id: "1",
    bookTitle: "Fisiología Vegetal",
    bookCode: "FV-2022-001",
    userName: "Carlos Mendoza López",
    userId: "EST-2024-0145",
    userType: "student",
    loanDate: "20 May 2026",
    dueDate: "28 May 2026",
    status: "active",
    renewals: 0,
  },
  {
    id: "2",
    bookTitle: "Introducción a la Ciencia del Suelo",
    bookCode: "CS-2021-015",
    userName: "Ana García Pérez",
    userId: "EST-2023-0089",
    userType: "student",
    loanDate: "10 May 2026",
    dueDate: "20 May 2026",
    status: "overdue",
    renewals: 2,
  },
  {
    id: "3",
    bookTitle: "Manejo Integrado de Plagas",
    bookCode: "ENT-2020-042",
    userName: "Dr. Roberto Jiménez",
    userId: "DOC-2019-0023",
    userType: "teacher",
    loanDate: "15 May 2026",
    dueDate: "15 Jun 2026",
    status: "active",
    renewals: 0,
  },
  {
    id: "4",
    bookTitle: "Sistemas de Riego",
    bookCode: "AG-2019-078",
    userName: "Laura Sánchez",
    userId: "EST-2024-0201",
    userType: "student",
    loanDate: "18 May 2026",
    dueDate: "26 May 2026",
    status: "active",
    renewals: 1,
  },
  {
    id: "5",
    bookTitle: "Nutrición Animal Aplicada",
    bookCode: "ZOO-2023-012",
    userName: "Miguel Torres Ruiz",
    userId: "EST-2022-0167",
    userType: "student",
    loanDate: "12 May 2026",
    dueDate: "22 May 2026",
    status: "overdue",
    renewals: 1,
  },
]

const historyLoans: Loan[] = [
  {
    id: "6",
    bookTitle: "Genética Vegetal",
    bookCode: "FV-2021-033",
    userName: "Pedro Ruiz García",
    userId: "EST-2023-0145",
    userType: "student",
    loanDate: "01 May 2026",
    dueDate: "09 May 2026",
    returnDate: "08 May 2026",
    status: "returned",
    renewals: 0,
  },
  {
    id: "7",
    bookTitle: "Botánica Sistemática",
    bookCode: "BOT-2018-021",
    userName: "Dra. María Fernández",
    userId: "DOC-2015-0012",
    userType: "teacher",
    loanDate: "25 Abr 2026",
    dueDate: "25 May 2026",
    returnDate: "20 May 2026",
    status: "returned",
    renewals: 0,
  },
]

export default function CirculacionPage() {
  const [activeTab, setActiveTab] = useState<"active" | "history">("active")

  const currentLoans = activeTab === "active" ? activeLoans : historyLoans
  const overdueCount = activeLoans.filter(l => l.status === "overdue").length

  return (
    <AppLayout>
      <Header 
        title="Circulación" 
        description="Gestión de préstamos y devoluciones"
      />
      
      <div className="p-6">
        {/* Stats Summary */}
        <div className="mb-6 grid gap-4 sm:grid-cols-3">
          <div className="rounded-lg border border-border bg-card p-4">
            <p className="text-sm text-muted-foreground">Préstamos Activos</p>
            <p className="mt-1 text-2xl font-semibold text-foreground">
              {activeLoans.filter(l => l.status === "active").length}
            </p>
          </div>
          <div className="rounded-lg border border-destructive/30 bg-card p-4">
            <p className="text-sm text-muted-foreground">Vencidos</p>
            <p className="mt-1 text-2xl font-semibold text-destructive">{overdueCount}</p>
          </div>
          <div className="rounded-lg border border-border bg-card p-4">
            <p className="text-sm text-muted-foreground">Devueltos (este mes)</p>
            <p className="mt-1 text-2xl font-semibold text-foreground">{historyLoans.length}</p>
          </div>
        </div>

        {/* Action Bar */}
        <div className="mb-6 flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
          <LoanFilters activeTab={activeTab} onTabChange={setActiveTab} />
          <div className="flex gap-2">
            <Button variant="outline">
              <Download className="mr-2 h-4 w-4" />
              Exportar
            </Button>
            <Link href="/circulacion/nuevo">
              <Button>
                <Plus className="mr-2 h-4 w-4" />
                Nuevo Préstamo
              </Button>
            </Link>
          </div>
        </div>

        {/* Table */}
        <LoanTable loans={currentLoans} />

        {/* Pagination */}
        <div className="mt-6 flex items-center justify-between">
          <p className="text-sm text-muted-foreground">
            Mostrando {currentLoans.length} registros
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
