import { AppLayout } from "@/components/layout/app-layout"
import { Header } from "@/components/layout/header"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select"
import { 
  Building2, 
  Clock, 
  Mail, 
  Bell,
  Shield,
  Database,
  Save
} from "lucide-react"

export default function ConfiguracionPage() {
  return (
    <AppLayout>
      <Header 
        title="Configuración" 
        description="Ajustes del sistema de biblioteca"
      />
      
      <div className="p-6">
        <div className="mx-auto max-w-4xl space-y-8">
          {/* Institution Settings */}
          <div className="rounded-lg border border-border bg-card">
            <div className="border-b border-border px-6 py-4">
              <div className="flex items-center gap-3">
                <Building2 className="h-5 w-5 text-primary" />
                <div>
                  <h3 className="font-semibold text-foreground">Información de la Institución</h3>
                  <p className="text-sm text-muted-foreground">Datos generales de la biblioteca</p>
                </div>
              </div>
            </div>
            <div className="space-y-4 p-6">
              <div className="grid gap-4 sm:grid-cols-2">
                <div className="space-y-2">
                  <label className="text-sm font-medium text-foreground">Nombre de la Biblioteca</label>
                  <Input defaultValue="Biblioteca Central UNAGRO" />
                </div>
                <div className="space-y-2">
                  <label className="text-sm font-medium text-foreground">Código</label>
                  <Input defaultValue="BIB-UNAGRO-001" />
                </div>
              </div>
              <div className="space-y-2">
                <label className="text-sm font-medium text-foreground">Dirección</label>
                <Input defaultValue="Campus Universitario, Edificio A, Piso 1" />
              </div>
              <div className="grid gap-4 sm:grid-cols-2">
                <div className="space-y-2">
                  <label className="text-sm font-medium text-foreground">Teléfono</label>
                  <Input defaultValue="+58 212 555 0123" />
                </div>
                <div className="space-y-2">
                  <label className="text-sm font-medium text-foreground">Email</label>
                  <Input defaultValue="biblioteca@unagro.edu" />
                </div>
              </div>
            </div>
          </div>

          {/* Loan Settings */}
          <div className="rounded-lg border border-border bg-card">
            <div className="border-b border-border px-6 py-4">
              <div className="flex items-center gap-3">
                <Clock className="h-5 w-5 text-primary" />
                <div>
                  <h3 className="font-semibold text-foreground">Políticas de Préstamo</h3>
                  <p className="text-sm text-muted-foreground">Configuración de tiempos y límites</p>
                </div>
              </div>
            </div>
            <div className="space-y-4 p-6">
              <div className="grid gap-4 sm:grid-cols-3">
                <div className="space-y-2">
                  <label className="text-sm font-medium text-foreground">Días préstamo (Estudiantes)</label>
                  <Input type="number" defaultValue="7" />
                </div>
                <div className="space-y-2">
                  <label className="text-sm font-medium text-foreground">Días préstamo (Docentes)</label>
                  <Input type="number" defaultValue="30" />
                </div>
                <div className="space-y-2">
                  <label className="text-sm font-medium text-foreground">Días préstamo (Personal)</label>
                  <Input type="number" defaultValue="14" />
                </div>
              </div>
              <div className="grid gap-4 sm:grid-cols-3">
                <div className="space-y-2">
                  <label className="text-sm font-medium text-foreground">Máx. libros (Estudiantes)</label>
                  <Input type="number" defaultValue="3" />
                </div>
                <div className="space-y-2">
                  <label className="text-sm font-medium text-foreground">Máx. libros (Docentes)</label>
                  <Input type="number" defaultValue="10" />
                </div>
                <div className="space-y-2">
                  <label className="text-sm font-medium text-foreground">Renovaciones permitidas</label>
                  <Input type="number" defaultValue="2" />
                </div>
              </div>
              <div className="space-y-2">
                <label className="text-sm font-medium text-foreground">Multa por día de retraso</label>
                <div className="flex items-center gap-2">
                  <span className="text-sm text-muted-foreground">Bs.</span>
                  <Input type="number" defaultValue="5.00" className="w-32" />
                </div>
              </div>
            </div>
          </div>

          {/* Notifications */}
          <div className="rounded-lg border border-border bg-card">
            <div className="border-b border-border px-6 py-4">
              <div className="flex items-center gap-3">
                <Bell className="h-5 w-5 text-primary" />
                <div>
                  <h3 className="font-semibold text-foreground">Notificaciones</h3>
                  <p className="text-sm text-muted-foreground">Configuración de alertas automáticas</p>
                </div>
              </div>
            </div>
            <div className="space-y-4 p-6">
              <div className="grid gap-4 sm:grid-cols-2">
                <div className="space-y-2">
                  <label className="text-sm font-medium text-foreground">Recordatorio antes de vencimiento</label>
                  <Select defaultValue="3">
                    <SelectTrigger>
                      <SelectValue />
                    </SelectTrigger>
                    <SelectContent>
                      <SelectItem value="1">1 día antes</SelectItem>
                      <SelectItem value="2">2 días antes</SelectItem>
                      <SelectItem value="3">3 días antes</SelectItem>
                      <SelectItem value="5">5 días antes</SelectItem>
                    </SelectContent>
                  </Select>
                </div>
                <div className="space-y-2">
                  <label className="text-sm font-medium text-foreground">Canal de notificación</label>
                  <Select defaultValue="email">
                    <SelectTrigger>
                      <SelectValue />
                    </SelectTrigger>
                    <SelectContent>
                      <SelectItem value="email">Email</SelectItem>
                      <SelectItem value="sms">SMS</SelectItem>
                      <SelectItem value="both">Email + SMS</SelectItem>
                    </SelectContent>
                  </Select>
                </div>
              </div>
            </div>
          </div>

          {/* System */}
          <div className="rounded-lg border border-border bg-card">
            <div className="border-b border-border px-6 py-4">
              <div className="flex items-center gap-3">
                <Database className="h-5 w-5 text-primary" />
                <div>
                  <h3 className="font-semibold text-foreground">Sistema</h3>
                  <p className="text-sm text-muted-foreground">Información técnica del sistema</p>
                </div>
              </div>
            </div>
            <div className="space-y-4 p-6">
              <div className="grid gap-4 sm:grid-cols-2">
                <div className="rounded-lg bg-muted/50 p-4">
                  <p className="text-sm text-muted-foreground">Versión del Sistema</p>
                  <p className="mt-1 font-medium text-foreground">BiblioAgro v1.0.0</p>
                </div>
                <div className="rounded-lg bg-muted/50 p-4">
                  <p className="text-sm text-muted-foreground">Última Sincronización</p>
                  <p className="mt-1 font-medium text-foreground">24 May 2026, 10:30 AM</p>
                </div>
              </div>
            </div>
          </div>

          {/* Save Button */}
          <div className="flex justify-end">
            <Button size="lg">
              <Save className="mr-2 h-4 w-4" />
              Guardar Cambios
            </Button>
          </div>
        </div>
      </div>
    </AppLayout>
  )
}
