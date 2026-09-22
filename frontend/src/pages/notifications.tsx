import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { Bell, CheckCheck, ChevronLeft, ChevronRight } from 'lucide-react'
import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { toast } from 'sonner'

import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { EmptyState } from '@/components/ui/empty-state'
import { PageHeader } from '@/components/ui/page-header'
import { Skeleton } from '@/components/ui/skeleton'
import { api, ApiError } from '@/lib/api'
import { relativeTime, titleCase } from '@/lib/format'
import type { Notification, NotificationType } from '@/lib/types'

type BadgeVariant = 'default' | 'success' | 'warning' | 'destructive' | 'muted' | 'outline' | 'info'

interface NotifPage {
  items: Notification[]
  total: number
  unread: number
}

interface NotificationPreference {
  category: string
  enabled: boolean
}

const typeVariant: Record<NotificationType, BadgeVariant> = {
  task_assigned: 'info',
  deadline_approaching: 'warning',
  review_result: 'success',
  deadline_extension: 'default',
  mention: 'warning',
  announcement: 'info',
  leave_decision: 'warning',
  attendance_update: 'muted',
  comment: 'info',
  submission_submitted: 'default',
  remark: 'default',
  batch_event: 'info',
  internship_completed: 'success',
}

const PAGE_SIZE = 50

export default function NotificationsPage() {
  const qc = useQueryClient()
  const navigate = useNavigate()
  const [skip, setSkip] = useState(0)

  const list = useQuery({
    queryKey: ['notifications', 'list', skip],
    queryFn: () => api.get<NotifPage>(`/api/v1/notifications?limit=${PAGE_SIZE}&skip=${skip}`),
  })

  const unread = useQuery({
    queryKey: ['notifications', 'unread-count'],
    queryFn: () => api.get<{ count: number }>('/api/v1/notifications/unread-count'),
  })

  const prefs = useQuery({
    queryKey: ['notifications', 'preferences'],
    queryFn: () => api.get<NotificationPreference[]>('/api/v1/notifications/preferences'),
  })

  const invalidate = () => {
    qc.invalidateQueries({ queryKey: ['notifications'] })
  }

  const markOne = useMutation({
    mutationFn: (id: number) => api.post(`/api/v1/notifications/read`, { ids: [id] }),
    onSuccess: invalidate,
    onError: (e) => toast.error(e instanceof ApiError ? e.detail : 'Failed to mark notification'),
  })

  const markAll = useMutation({
    mutationFn: () => api.post('/api/v1/notifications/read', { all: true }),
    onSuccess: () => {
      toast.success('All notifications marked as read')
      invalidate()
    },
    onError: (e) => toast.error(e instanceof ApiError ? e.detail : 'Failed to mark notifications'),
  })

  const togglePref = useMutation({
    mutationFn: ({ category, enabled }: NotificationPreference) =>
      api.patch('/api/v1/notifications/preferences', { category, enabled }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['notifications', 'preferences'] })
    },
    onError: (e) => toast.error(e instanceof ApiError ? e.detail : 'Failed to update preference'),
  })

  const handleOpen = (n: Notification) => {
    if (!n.is_read) markOne.mutate(n.id)
    if (n.link) navigate(n.link)
  }

  const unreadCount = unread.data?.count ?? list.data?.unread ?? 0
  const total = list.data?.total ?? 0

  return (
    <div>
      <PageHeader
        title="Notifications"
        description={`${unreadCount} unread`}
        actions={
          unreadCount > 0 && (
            <Button variant="outline" size="sm" onClick={() => markAll.mutate()} loading={markAll.isPending}>
              <CheckCheck className="size-4" /> Mark all read
            </Button>
          )
        }
      />

      <div className="grid gap-4 lg:grid-cols-3">
        <Card className="lg:col-span-2">
          <CardHeader>
            <CardTitle className="flex items-center gap-2 text-sm">
              <Bell className="size-4 text-primary" /> Inbox
            </CardTitle>
          </CardHeader>
          <CardContent className="p-0">
            {list.isLoading ? (
              <div className="space-y-2 p-5">
                <Skeleton className="h-12 w-full" />
                <Skeleton className="h-12 w-full" />
                <Skeleton className="h-12 w-full" />
              </div>
            ) : list.data?.items.length === 0 ? (
              <div className="p-5">
                <EmptyState title="You're all caught up" description="No notifications to show." />
              </div>
            ) : (
              <ul className="divide-y divide-border">
                {(list.data?.items ?? []).map((n) => (
                  <li key={n.id}>
                    <button
                      onClick={() => handleOpen(n)}
                      className={`flex w-full items-start gap-3 px-5 py-3 text-left transition-colors hover:bg-muted/40 ${
                        n.is_read ? 'opacity-70' : ''
                      }`}
                    >
                      {!n.is_read && <span className="mt-2 size-2 shrink-0 rounded-full bg-primary" />}
                      <div className="min-w-0 flex-1">
                        <div className="flex flex-wrap items-center gap-2">
                          <p className="font-medium">{n.title}</p>
                          <Badge variant={typeVariant[n.notification_type] ?? 'muted'}>{titleCase(n.notification_type)}</Badge>
                        </div>
                        {n.body && <p className="mt-0.5 text-sm text-muted-foreground">{n.body}</p>}
                        <p className="mt-1 text-xs text-muted-foreground/70">{relativeTime(n.created_at)}</p>
                      </div>
                      {n.link && <ChevronRight className="mt-1 size-4 shrink-0 text-muted-foreground" />}
                    </button>
                  </li>
                ))}
              </ul>
            )}
            {total > PAGE_SIZE && (
              <div className="flex items-center justify-between border-t border-border px-5 py-3">
                <p className="text-xs text-muted-foreground">
                  Showing {skip + 1}–{Math.min(skip + PAGE_SIZE, total)} of {total}
                </p>
                <div className="flex gap-2">
                  <Button variant="outline" size="sm" disabled={skip === 0} onClick={() => setSkip((s) => Math.max(0, s - PAGE_SIZE))}>
                    <ChevronLeft className="size-4" /> Prev
                  </Button>
                  <Button
                    variant="outline"
                    size="sm"
                    disabled={skip + PAGE_SIZE >= total}
                    onClick={() => setSkip((s) => s + PAGE_SIZE)}
                  >
                    Next <ChevronRight className="size-4" />
                  </Button>
                </div>
              </div>
            )}
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle className="text-sm">Preferences</CardTitle>
          </CardHeader>
          <CardContent>
            {prefs.isLoading ? (
              <Skeleton className="h-48 w-full rounded-xl" />
            ) : (prefs.data?.length ?? 0) === 0 ? (
              <p className="text-sm text-muted-foreground">No preferences configured.</p>
            ) : (
              <ul className="space-y-1">
                {(prefs.data ?? []).map((p) => (
                  <li key={p.category}>
                    <label className="flex cursor-pointer items-center justify-between rounded-lg px-3 py-2 text-sm hover:bg-muted/40">
                      <span className="capitalize">{titleCase(p.category)}</span>
                      <input
                        type="checkbox"
                        checked={p.enabled}
                        disabled={togglePref.isPending}
                        onChange={(e) => togglePref.mutate({ category: p.category, enabled: e.target.checked })}
                      />
                    </label>
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