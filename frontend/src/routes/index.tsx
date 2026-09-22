import { lazy, Suspense } from 'react'
import { createBrowserRouter, Navigate } from 'react-router-dom'

import { PageSpinner } from '@/components/ui/spinner'
import { AppLayout } from '@/layouts/AppLayout'
import { ProtectedRoute, RoleRoute } from '@/routes/guards'

const Lazy = (mod: Promise<{ default: React.ComponentType }>) => {
  const C = lazy(() => mod)
  return (
    <Suspense fallback={<PageSpinner />}>
      <C />
    </Suspense>
  )
}

const AUTH = {
  Login: Lazy(import('@/pages/auth/login')),
  SetPassword: Lazy(import('@/pages/auth/set-password')),
  ForgotPassword: Lazy(import('@/pages/auth/forgot-password')),
  ResetPassword: Lazy(import('@/pages/auth/reset-password')),
}

const PAGES = {
  DashboardIntern: Lazy(import('@/pages/intern/dashboard')),
  TasksList: Lazy(import('@/pages/tasks/list')),
  TaskDetail: Lazy(import('@/pages/tasks/detail')),
  Attendance: Lazy(import('@/pages/attendance/index')),
  Leave: Lazy(import('@/pages/attendance/leave')),
  Calendar: Lazy(import('@/pages/calendar')),
  Notifications: Lazy(import('@/pages/notifications')),
  Profile: Lazy(import('@/pages/profile')),
  Batches: Lazy(import('@/pages/batches/index')),
  BatchDetail: Lazy(import('@/pages/batches/detail')),
  Reviews: Lazy(import('@/pages/reviews')),
  Users: Lazy(import('@/pages/users')),
  Reports: Lazy(import('@/pages/reports')),
  Certificates: Lazy(import('@/pages/certificates')),
  Company: Lazy(import('@/pages/company')),
  Audit: Lazy(import('@/pages/audit')),
  Analytics: Lazy(import('@/pages/analytics')),
  DashboardSupervisor: Lazy(import('@/pages/supervisor/dashboard')),
  DashboardAdmin: Lazy(import('@/pages/admin/dashboard')),
}

export const router = createBrowserRouter([
  { path: '/login', element: AUTH.Login },
  { path: '/set-password', element: AUTH.SetPassword },
  { path: '/forgot-password', element: AUTH.ForgotPassword },
  { path: '/reset-password', element: AUTH.ResetPassword },
  {
    element: <ProtectedRoute />,
    children: [
      {
        element: <AppLayout />,
        children: [
          // Role home dashboards (resolved by role redirect)
          { path: '/', element: <RoleHome /> },
          { path: '/profile', element: PAGES.Profile },
          { path: '/notifications', element: PAGES.Notifications },
          { path: '/tasks', element: PAGES.TasksList },
          { path: '/tasks/:taskId', element: PAGES.TaskDetail },
          { path: '/attendance', element: PAGES.Attendance },
          { path: '/leave', element: <RoleRoute roles={['intern']}>{PAGES.Leave}</RoleRoute> },
          { path: '/calendar', element: PAGES.Calendar },

          // Intern
          { path: '/intern', element: <RoleRoute roles={['intern']} />, children: [] },

          // Supervisor
          {
            element: <RoleRoute roles={['supervisor', 'admin']} />,
            children: [
              { path: '/batches', element: PAGES.Batches },
              { path: '/batches/:batchId', element: PAGES.BatchDetail },
              { path: '/reviews', element: PAGES.Reviews },
              { path: '/analytics', element: PAGES.Analytics },
            ],
          },

          // Admin
          {
            element: <RoleRoute roles={['admin']} />,
            children: [
              { path: '/users', element: PAGES.Users },
              { path: '/reports', element: PAGES.Reports },
              { path: '/certificates', element: PAGES.Certificates },
              { path: '/company', element: PAGES.Company },
              { path: '/audit', element: PAGES.Audit },
            ],
          },
        ],
      },
    ],
  },
  { path: '*', element: <Navigate to="/" replace /> },
])

/** Redirects / to the role-appropriate dashboard. */
function RoleHome() {
  const { user } = useAuthLite()
  if (!user) return <Navigate to="/login" replace />
  if (user.role === 'admin') return PAGES.DashboardAdmin
  if (user.role === 'supervisor') return PAGES.DashboardSupervisor
  return PAGES.DashboardIntern
}

import { useAuth } from '@/context/auth'
function useAuthLite() {
  return useAuth()
}