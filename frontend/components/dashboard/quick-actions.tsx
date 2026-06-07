import Link from "next/link"
import { LucideIcon, ArrowRight } from "lucide-react"
import { cn } from "@/lib/utils"

interface QuickAction {
  title: string
  description: string
  href: string
  icon: LucideIcon
  color: "primary" | "accent" | "secondary"
}

interface QuickActionsProps {
  actions: QuickAction[]
}

const colorConfig = {
  primary: "bg-primary/10 text-primary",
  accent: "bg-accent/20 text-accent-foreground",
  secondary: "bg-secondary text-secondary-foreground",
}

export function QuickActions({ actions }: QuickActionsProps) {
  return (
    <div className="rounded-xl border border-border bg-card">
      <div className="border-b border-border px-6 py-4">
        <h3 className="font-semibold text-foreground">Acciones Rápidas</h3>
        <p className="text-sm text-muted-foreground">Operaciones frecuentes</p>
      </div>
      <div className="grid gap-2 p-4">
        {actions.map((action) => (
          <Link
            key={action.title}
            href={action.href}
            className="group flex items-center gap-4 rounded-lg p-3 transition-colors hover:bg-muted"
          >
            <div className={cn(
              "flex h-10 w-10 items-center justify-center rounded-lg",
              colorConfig[action.color]
            )}>
              <action.icon className="h-5 w-5" />
            </div>
            <div className="flex-1">
              <p className="font-medium text-foreground">{action.title}</p>
              <p className="text-sm text-muted-foreground">{action.description}</p>
            </div>
            <ArrowRight className="h-5 w-5 text-muted-foreground opacity-0 transition-opacity group-hover:opacity-100" />
          </Link>
        ))}
      </div>
    </div>
  )
}
