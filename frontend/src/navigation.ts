import type { Role } from '@/lib/types'

export interface NavItem {
  to: string
  label: string
  icon: string
}

const NAV: Record<Role, NavItem[]> = {
  admin: [
    { to: '/', label: 'Dashboard', icon: 'LayoutDashboard' },
    { to: '/users', label: 'Users', icon: 'Users' },
    { to: '/batches', label: 'Batches', icon: 'Layers' },
    { to: '/reports', label: 'Reports', icon: 'FileText' },
    { to: '/certificates', label: 'Certificates', icon: 'Award' },
    { to: '/company', label: 'Company', icon: 'Building2' },
    { to: '/audit', label: 'Audit Log', icon: 'ScrollText' },
  ],
  supervisor: [
    { to: '/', label: 'Dashboard', icon: 'LayoutDashboard' },
    { to: '/batches', label: 'Batches', icon: 'Layers' },
    { to: '/tasks', label: 'Tasks', icon: 'ListChecks' },
    { to: '/reviews', label: 'Reviews', icon: 'ClipboardCheck' },
    { to: '/attendance', label: 'Attendance', icon: 'Clock3' },
    { to: '/analytics', label: 'Analytics', icon: 'BarChart3' },
    { to: '/calendar', label: 'Calendar', icon: 'CalendarDays' },
  ],
  intern: [
    { to: '/', label: 'Dashboard', icon: 'LayoutDashboard' },
    { to: '/tasks', label: 'My Tasks', icon: 'ListChecks' },
    { to: '/attendance', label: 'Attendance', icon: 'Clock3' },
    { to: '/leave', label: 'Leave', icon: 'CalendarOff' },
    { to: '/calendar', label: 'Calendar', icon: 'CalendarDays' },
  ],
}

export function navFor(role: Role): NavItem[] {
  return NAV[role] ?? NAV.intern
}

export const APP_NAME = 'InternFlow'