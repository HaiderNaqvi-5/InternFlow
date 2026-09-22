import type { ReactNode } from 'react'
import { Navigate, Outlet, useLocation } from 'react-router-dom'

import { PageSpinner } from '@/components/ui/spinner'
import { useAuth } from '@/context/auth'
import type { Role } from '@/lib/types'

export function ProtectedRoute() {
  const { user, loading } = useAuth()
  const location = useLocation()
  if (loading) return <PageSpinner />
  if (!user) return <Navigate to="/login" state={{ from: location.pathname }} replace />
  if (user.must_reset_password && location.pathname !== '/set-password') return <Navigate to="/set-password" replace />
  return <Outlet />
}

export function RoleRoute({ roles, children }: { roles: Role[]; children?: ReactNode }) {
  const { user, loading } = useAuth()
  if (loading) return <PageSpinner />
  if (!user) return <Navigate to="/login" replace />
  if (!roles.includes(user.role)) return <Navigate to="/" replace />
  return children ?? <Outlet />
}