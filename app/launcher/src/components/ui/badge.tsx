import type { ReactNode } from 'react'
import { cn } from '../../lib/utils'

type BadgeProps = {
  children: ReactNode
  tone?: 'default' | 'success' | 'warning' | 'danger' | 'info' | 'muted'
  className?: string
}

export function Badge({ children, tone = 'default', className }: BadgeProps) {
  return <span className={cn('badge', `badge-${tone}`, className)}>{children}</span>
}
