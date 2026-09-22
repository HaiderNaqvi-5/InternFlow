import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { Bell, CalendarCheck, FileClock, ListChecks, LogIn, LogOut, Percent, Star } from 'lucide-react'
import { useNavigate } from 'react-router-dom'
import { toast } from 'sonner'

import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Skeleton } from '@/components/ui/skeleton'
import { StatCard } from '@/components/ui/stat-card'
import { useAuth } from '@/context/auth'
import { api, ApiError } from '@/lib/api'
import { durationLabel, formatDateTime, relativeTime, titleCase } from '@/lib/format'
import type { AttendanceRecord, InternAnalytics, Notification, PaginatedTasks, Task, TaskStatus } from '@/lib/types'

const statusVariant: Record<TaskStatus, 'default' | 'success' | 'warning' | 'info' | 'muted'> = {
  open: 'default',
  in_progress: 'info',
  submitted: 'warning',
  reviewed: 'info',
  pending_resubmission: 'default',
}

interface NotifPage {
  items: Notification[]
  total: number
  unread: number
}

export default function InternDashboardPage() {
  const { user } = useAuth()
  const qc = useQueryClient()
  const navigate = useNavigate()

  const analytics = useQuery({
    queryKey: ['analytics', 'intern'],
    queryFn: () => api.get<InternAnalytics>('/api/v1/analytics/intern'),
  })

  const today = useQuery({
    queryKey: ['attendance', 'today'],
    queryFn: () => api.get<AttendanceRecord | null>('/api/v1/attendance/today'),
  })

  const tasks = useQuery({
    queryKey: ['tasks', 'recent'],
    queryFn: () => api.get<PaginatedTasks>('/api/v1/tasks?page_size=5'),
  })

  const notifs = useQuery({
    queryKey: ['notifications', 'dashboard'],
    queryFn: () => api.get<NotifPage>('/api/v1/notifications?limit=5'),
  })

  const invalidateAttendance = () => {
    qc.invalidateQueries({ queryKey: ['attendance'] })
    qc.invalidateQueries({ queryKey: ['analytics', 'intern'] })
  }

  const checkIn = useMutation({
    mutationFn: () => api.post<AttendanceRecord>('/api/v1/attendance/check-in'),
    onSuccess: () => {
      toast.success('Checked in')
      invalidateAttendance()
    },
    onError: (e) => toast.error(e instanceof ApiError ? e.detail : 'Check-in failed'),
  })

  const checkOut = useMutation({
    mutationFn: () => api.post<AttendanceRecord>('/api/v1/attendance/check-out', {}),
    onSuccess: () => {
      toast.success('Checked out')
      invalidateAttendance()
    },
    onError: (e) => toast.error(e instanceof ApiError ? e.detail : 'Check-out failed'),
  })

  const a = analytics.data
  const record = today.data
  const checkedIn = !!record?.check_in
  const checkedOut = !!record?.check_out

  return (
    <div>
      <div className="mb-6">
        <h1 className="text-2xl font-bold tracking-tight">Welcome back, {user?.full_name.split(' ')[0] ?? 'there'}</h1>
        <p className="mt-1 text-sm text-muted-foreground">Here's what's happening with your internship today.</p>
      </div>

      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <StatCard
          label="Pending Tasks"
          value={a?.tasks_pending ?? '—'}
          icon={<ListChecks className="size-4" />}
          hint={a ? `${a.tasks_total} total assigned` : undefined}
        />
        <StatCard
          label="Overdue Tasks"
          value={a?.overdue_tasks ?? '—'}
          icon={<FileClock className="size-4" />}
          tone={(a?.overdue_tasks ?? 0) > 0 ? 'destructive' : 'default'}
        />
        <StatCard
          label="Avg Score"
          value={a?.average_score != null ? `${a.average_score}/10` : '—'}
          icon={<Star className="size-4" />}
          hint={a && a.late_days ? `${a.late_days} late day${a.late_days === 1 ? '' : 's'}` : undefined}
        />
        <StatCard
          label="Attendance Rate"
          value={a?.attendance_rate != null ? `${a.attendance_rate}%` : '—'}
          icon={<Percent className="size-4" />}
          hint={a ? `${durationLabel(a.total_hours)} worked` : undefined}
        />
      </div>

      <div className="mt-6 grid gap-4 lg:grid-cols-3">
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <CalendarCheck className="size-4 text-primary" /> Today
            </CardTitle>
          </CardHeader>
          <CardContent>
            {today.isLoading ? (
              <Skeleton className="h-40 rounded-xl" />
            ) : !record ? (
              <div className="flex flex-col items-center gap-3 py-6 text-center">
                <p className="text-sm text-muted-foreground">You haven't checked in today.</p>
                <Button onClick={() => checkIn.mutate()} loading={checkIn.isPending} disabled={checkedIn}>
                  <LogIn className="size-4" /> Check in
                </Button>
              </div>
            ) : (
              <div className="space-y-4">
                <div className="grid grid-cols-2 gap-3 text-sm">
                  <div className="rounded-lg bg-muted/50 p-3">
                    <p className="text-xs uppercase tracking-wide text-muted-foreground">Check-in</p>
                    <p className="mt-1 font-semibold">{record.check_in ? formatDateTime(record.check_in) : '—'}</p>
                  </div>
                  <div className="rounded-lg bg-muted/50 p-3">
                    <p className="text-xs uppercase tracking-wide text-muted-foreground">Check-out</p>
                    <p className="mt-1 font-semibold">{record.check_out ? formatDateTime(record.check_out) : '—'}</p>
                  </div>
                </div>
                {record.worked_hours != null && (
                  <p className="text-xs text-muted-foreground">
                    Worked so far: <span className="font-medium text-foreground">{durationLabel(record.worked_hours)}</span>
                  </p>
                )}
                <div className="flex gap-2">
                  <Button className="flex-1" onClick={() => checkIn.mutate()} loading={checkIn.isPending} disabled={checkedIn}>
                    <LogIn className="size-4" /> Check in
                  </Button>
                  <Button variant="secondary" className="flex-1" onClick={() => checkOut.mutate()} loading={checkOut.isPending} disabled={!checkedIn || checkedOut}>
                    <LogOut className="size-4" /> Check out
                  </Button>
                </div>
              </div>
            )}
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <ListChecks className="size-4 text-primary" /> Recent Tasks
            </CardTitle>
          </CardHeader>
          <CardContent className="p-0">
            {tasks.isLoading ? (
              <div className="space-y-2 p-5">
                <Skeleton className="h-10 w-full" />
                <Skeleton className="h-10 w-full" />
                <Skeleton className="h-10 w-full" />
              </div>
            ) : (tasks.data?.items.length ?? 0) === 0 ? (
              <p className="p-5 text-sm text-muted-foreground">No tasks assigned yet.</p>
            ) : (
              <ul className="divide-y divide-border">
                {(tasks.data?.items ?? []).slice(0, 5).map((t: Task) => (
                  <li key={t.id}>
                    <button
                      onClick={() => navigate(`/tasks/${t.id}`)}
                      className="flex w-full items-center justify-between gap-3 px-5 py-3 text-left transition-colors hover:bg-muted/40"
                    >
                      <div className="min-w-0">
                        <p className="truncate text-sm font-medium">{t.title}</p>
                        <p className="text-xs text-muted-foreground">{relativeTime(t.deadline)}</p>
                      </div>
                      <Badge variant={statusVariant[t.status]}>{titleCase(t.status)}</Badge>
                    </button>
                  </li>
                ))}
              </ul>
            )}
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <Bell className="size-4 text-primary" /> Notifications
            </CardTitle>
          </CardHeader>
          <CardContent className="p-0">
            {notifs.isLoading ? (
              <div className="space-y-2 p-5">
                <Skeleton className="h-10 w-full" />
                <Skeleton className="h-10 w-full" />
                <Skeleton className="h-10 w-full" />
              </div>
            ) : (notifs.data?.items.length ?? 0) === 0 ? (
              <p className="p-5 text-sm text-muted-foreground">You're all caught up.</p>
            ) : (
              <ul className="divide-y divide-border">
                {(notifs.data?.items ?? []).slice(0, 5).map((n) => (
                  <li key={n.id}>
                    <button
                      onClick={() => n.link && navigate(n.link)}
                      className="flex w-full items-start gap-3 px-5 py-3 text-left transition-colors hover:bg-muted/40"
                    >
                      {!n.is_read && <span className="mt-1.5 size-2 shrink-0 rounded-full bg-primary" />}
                      <div className="min-w-0">
                        <p className="truncate text-sm font-medium">{n.title}</p>
                        {n.body && <p className="mt-0.5 line-clamp-2 text-xs text-muted-foreground">{n.body}</p>}
                        <p className="mt-0.5 text-[11px] text-muted-foreground/70">{relativeTime(n.created_at)}</p>
                      </div>
                    </button>
                  </li>
                ))}
              </ul>
            )}
          </CardContent>
        </Card>
      </div>
    </div>
  )
}