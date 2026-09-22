import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { Bell, Moon, Sun } from 'lucide-react'
import { useEffect } from 'react'
import { toast } from 'sonner'

import { Button } from '@/components/ui/button'
import { DropdownItem, DropdownMenu } from '@/components/ui/dropdown'
import { useTheme } from '@/context/theme'
import { api } from '@/lib/api'
import { relativeTime } from '@/lib/format'
import type { Notification, PaginatedNotifications } from '@/lib/types'
import { ws } from '@/lib/ws'

export function NotificationsBell() {
  const { theme, toggle } = useTheme()
  const qc = useQueryClient()
  const { data, isLoading } = useQuery({
    queryKey: ['notifications', 'recent'],
    queryFn: () => api.get<PaginatedNotifications>('/api/v1/notifications?limit=5&unread_only=true'),
  })

  const markAll = useMutation({
    mutationFn: () => api.post('/api/v1/notifications/read', { all: true }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['notifications'] })
      toast.success('All notifications marked as read')
    },
  })

  useEffect(() => {
    const unsub = ws.on((event) => {
      if (event.type === 'notification.created') {
        qc.invalidateQueries({ queryKey: ['notifications'] })
        const n = event.data as unknown as Notification
        if (n?.title) toast.info(n.title, { description: n.body ?? undefined })
      }
    })
    return unsub
  }, [qc])

  const unread = data?.total ?? 0

  return (
    <div className="flex items-center gap-1">
      <DropdownMenu
        trigger={
          <Button variant="ghost" size="icon" className="relative" aria-label="Notifications">
            <Bell className="size-5" />
            {unread > 0 && (
              <span className="absolute right-1 top-1 flex size-4 items-center justify-center rounded-full bg-primary text-[10px] font-bold text-primary-foreground">
                {unread > 9 ? '9+' : unread}
              </span>
            )}
          </Button>
        }
      >
        {(close) => (
          <div className="w-80">
            <div className="flex items-center justify-between px-2.5 py-2">
              <p className="text-sm font-semibold">Notifications</p>
              {unread > 0 && (
                <button className="text-xs text-primary hover:underline" onClick={() => markAll.mutate()}>
                  Mark all read
                </button>
              )}
            </div>
            <div className="max-h-80 overflow-y-auto">
              {isLoading && <div className="p-4 text-center text-xs text-muted-foreground">Loading…</div>}
              {!isLoading && !data?.items.length && (
                <div className="p-4 text-center text-xs text-muted-foreground">You're all caught up</div>
              )}
              {data?.items.map((n) => (
                <div key={n.id} className="border-t border-border px-2.5 py-2.5">
                  <p className="text-sm font-medium">{n.title}</p>
                  {n.body && <p className="mt-0.5 line-clamp-2 text-xs text-muted-foreground">{n.body}</p>}
                  <p className="mt-1 text-[11px] text-muted-foreground/70">{relativeTime(n.created_at)}</p>
                </div>
              ))}
            </div>
            <DropdownItem onClick={() => { close(); window.location.href = '/notifications' }}>
              View all notifications
            </DropdownItem>
          </div>
        )}
      </DropdownMenu>
      <Button variant="ghost" size="icon" onClick={toggle} aria-label="Toggle theme">
        {theme === 'light' ? <Moon className="size-5" /> : <Sun className="size-5" />}
      </Button>
    </div>
  )
}