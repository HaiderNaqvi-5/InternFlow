import { ChevronRight, LogOut, Menu, User as UserIcon, X, type LucideIcon } from 'lucide-react'
import { useState } from 'react'
import { Link, NavLink, Outlet, useNavigate } from 'react-router-dom'

import { GlobalSearch } from '@/components/app/global-search'
import { NotificationsBell } from '@/components/app/notifications-bell'
import { Avatar } from '@/components/ui/avatar'
import { DropdownItem, DropdownMenu } from '@/components/ui/dropdown'
import { useAuth } from '@/context/auth'
import { APP_NAME, navFor } from '@/navigation'
import { cn } from '@/lib/utils'

import {
  Award,
  BarChart3,
  Building2,
  CalendarDays,
  CalendarOff,
  ClipboardCheck,
  Clock3,
  FileText,
  Layers,
  LayoutDashboard,
  ListChecks,
  ScrollText,
  Users,
} from 'lucide-react'

const ICONS: Record<string, LucideIcon> = {
  Award,
  BarChart3,
  Building2,
  CalendarDays,
  CalendarOff,
  ClipboardCheck,
  Clock3,
  FileText,
  Layers,
  LayoutDashboard,
  ListChecks,
  ScrollText,
  Users,
}

export function AppLayout() {
  const { user, logout } = useAuth()
  const [mobileOpen, setMobileOpen] = useState(false)
  const navigate = useNavigate()
  if (!user) return null
  const items = navFor(user.role)

  const sidebar = (
    <div className="flex h-full flex-col gap-6 overflow-y-auto px-3 py-5">
      <Link to="/" className="flex items-center gap-2 px-2">
        <span className="flex size-8 items-center justify-center rounded-lg bg-primary text-sm font-bold text-primary-foreground">
          IF
        </span>
        <span className="text-lg font-bold tracking-tight">{APP_NAME}</span>
      </Link>
      <nav className="flex flex-1 flex-col gap-1">
        {items.map((item) => {
          const Icon = ICONS[item.icon] ?? LayoutDashboard
          return (
            <NavLink
              key={item.to}
              to={item.to}
              end={item.to === '/'}
              onClick={() => setMobileOpen(false)}
              className={({ isActive }) =>
                cn(
                  'flex items-center gap-3 rounded-lg px-3 py-2 text-sm font-medium transition-colors',
                  isActive ? 'bg-primary/10 text-primary' : 'text-muted-foreground hover:bg-secondary hover:text-foreground',
                )
              }
            >
              <Icon className="size-4.5" />
              {item.label}
            </NavLink>
          )
        })}
      </nav>
      <div className="border-t border-border pt-3 text-xs text-muted-foreground">
        <p className="px-2">{user.email}</p>
      </div>
    </div>
  )

  return (
    <div className="min-h-screen">
      {/* Desktop sidebar */}
      <aside className="fixed inset-y-0 left-0 z-30 hidden w-60 border-r border-border bg-card lg:block">{sidebar}</aside>

      {/* Mobile drawer */}
      {mobileOpen && (
        <div className="fixed inset-0 z-40 lg:hidden">
          <div className="absolute inset-0 bg-black/50" onClick={() => setMobileOpen(false)} />
          <aside className="absolute inset-y-0 left-0 w-64 bg-card shadow-xl">
            <button className="absolute right-3 top-4 text-muted-foreground" onClick={() => setMobileOpen(false)}>
              <X className="size-5" />
            </button>
            {sidebar}
          </aside>
        </div>
      )}

      {/* Main column */}
      <div className="lg:pl-60">
        <header className="sticky top-0 z-20 border-b border-border bg-background/80 backdrop-blur">
          <div className="flex h-14 items-center gap-3 px-4 lg:px-6">
            <ButtonGhost onClick={() => setMobileOpen(true)} className="lg:hidden">
              <Menu className="size-5" />
            </ButtonGhost>
            <div className="hidden flex-1 sm:block">
              <GlobalSearch />
            </div>
            <div className="ml-auto flex items-center gap-1">
              <div className="sm:hidden">
                <GlobalSearch />
              </div>
              <NotificationsBell />
              <DropdownMenu
                trigger={
                  <button className="ml-1 flex items-center gap-2 rounded-full px-1 py-1 hover:bg-secondary" aria-label="Account menu">
                    <Avatar name={user.full_name} className="size-8" />
                    <ChevronRight className="hidden size-4 -rotate-90 text-muted-foreground sm:block" />
                  </button>
                }
              >
                {(close) => (
                  <>
                    <div className="border-b border-border px-3 py-2">
                      <p className="truncate text-sm font-semibold">{user.full_name}</p>
                      <p className="truncate text-xs capitalize text-muted-foreground">{user.role}</p>
                    </div>
                    <DropdownItem onClick={() => { close(); navigate('/profile') }}>
                      <UserIcon className="size-4" /> My profile
                    </DropdownItem>
                    <DropdownItem danger onClick={async () => { await logout(); navigate('/login') }}>
                      <LogOut className="size-4" /> Log out
                    </DropdownItem>
                  </>
                )}
              </DropdownMenu>
            </div>
          </div>
        </header>
        <main className="mx-auto max-w-7xl px-4 py-6 lg:px-8">
          <Outlet />
        </main>
      </div>
    </div>
  )
}

function ButtonGhost({ children, className, onClick }: { children: React.ReactNode; className?: string; onClick?: () => void }) {
  return (
    <button onClick={onClick} className={cn('rounded-lg p-2 text-muted-foreground hover:bg-secondary', className)}>
      {children}
    </button>
  )
}