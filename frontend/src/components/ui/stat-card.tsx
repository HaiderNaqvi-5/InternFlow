import type { ReactNode } from 'react'
import { cn } from '@/lib/utils'

export function StatCard({
  label,
  value,
  icon,
  hint,
  tone = 'default',
}: {
  label: string
  value: ReactNode
  icon?: ReactNode
  hint?: ReactNode
  tone?: 'default' | 'success' | 'warning' | 'destructive'
}) {
  const tones = {
    default: 'text-primary',
    success: 'text-success',
    warning: 'text-warning',
    destructive: 'text-destructive',
  }
  return (
    <div className="flex items-center gap-4 rounded-xl border border-border bg-card p-5">
      {icon && (
        <div className={cn('flex size-10 shrink-0 items-center justify-center rounded-lg bg-muted/60', tones[tone])}>
          {icon}
        </div>
      )}
      <div className="min-w-0">
        <p className="text-xs font-medium uppercase tracking-wide text-muted-foreground">{label}</p>
        <p className="mt-0.5 text-2xl font-bold">{value}</p>
        {hint && <p className="mt-0.5 truncate text-xs text-muted-foreground">{hint}</p>}
      </div>
    </div>
  )
}