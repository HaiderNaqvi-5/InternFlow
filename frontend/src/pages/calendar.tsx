import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { CalendarCheck, CalendarDays, CalendarOff, CalendarPlus, ChevronRight, ListChecks, type LucideIcon } from 'lucide-react'
import { useMemo, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { toast } from 'sonner'

import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Dialog } from '@/components/ui/dialog'
import { EmptyState } from '@/components/ui/empty-state'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { PageHeader } from '@/components/ui/page-header'
import { Select } from '@/components/ui/select'
import { Skeleton } from '@/components/ui/skeleton'
import { Textarea } from '@/components/ui/textarea'
import { useAuth } from '@/context/auth'
import { api, ApiError } from '@/lib/api'
import { fromLocalInputValue } from '@/lib/format'
import type { CalendarEntry, PaginatedBatches } from '@/lib/types'

type BadgeVariant = 'default' | 'success' | 'warning' | 'destructive' | 'muted' | 'outline' | 'info'

const typeVariant: Record<CalendarEntry['type'], BadgeVariant> = {
  task: 'default',
  event: 'info',
  leave: 'warning',
}

const typeIcon: Record<CalendarEntry['type'], LucideIcon> = {
  task: ListChecks,
  event: CalendarCheck,
  leave: CalendarOff,
}

function clock(value: string | null): string {
  if (!value) return '—'
  const d = new Date(value)
  if (Number.isNaN(d.getTime())) return value
  return d.toLocaleTimeString(undefined, { hour: 'numeric', minute: '2-digit' })
}

interface EventForm {
  batch_id: string
  title: string
  description: string
  starts_at: string
  ends_at: string
  location: string
}

const emptyEvent: EventForm = { batch_id: '', title: '', description: '', starts_at: '', ends_at: '', location: '' }

export default function CalendarPage() {
  const { user } = useAuth()
  const canCreate = user?.role === 'supervisor' || user?.role === 'admin'
  const qc = useQueryClient()
  const navigate = useNavigate()
  const [createOpen, setCreateOpen] = useState(false)
  const [form, setForm] = useState<EventForm>(emptyEvent)

  const calendar = useQuery({
    queryKey: ['calendar'],
    queryFn: () => api.get<CalendarEntry[]>('/api/v1/calendar'),
  })

  const batches = useQuery({
    queryKey: ['batches'],
    queryFn: () => api.get<PaginatedBatches>('/api/v1/batches?page_size=100'),
    enabled: canCreate,
  })

  const createEvent = useMutation({
    mutationFn: (v: EventForm) =>
      api.post('/api/v1/events', {
        batch_id: Number(v.batch_id),
        title: v.title,
        details: v.description || null,
        starts_at: fromLocalInputValue(v.starts_at),
        ends_at: v.ends_at ? fromLocalInputValue(v.ends_at) : null,
        location: v.location || null,
        event_type: 'other',
      }),
    onSuccess: () => {
      toast.success('Event created')
      setCreateOpen(false)
      setForm(emptyEvent)
      qc.invalidateQueries({ queryKey: ['calendar'] })
    },
    onError: (e) => toast.error(e instanceof ApiError ? e.detail : 'Failed to create event'),
  })

  const groups = useMemo(() => {
    const entries = calendar.data ?? []
    const sorted = [...entries].sort((a, b) => a.start.localeCompare(b.start))
    const map = new Map<string, CalendarEntry[]>()
    for (const e of sorted) {
      const day = e.start.slice(0, 10)
      const arr = map.get(day)
      if (arr) arr.push(e)
      else map.set(day, [e])
    }
    return [...map.entries()].sort((a, b) => a[0].localeCompare(b[0]))
  }, [calendar.data])

  const openCreate = () => {
    const firstBatch = batches.data?.items?.[0]?.id
    setForm({ ...emptyEvent, batch_id: firstBatch ? String(firstBatch) : '' })
    setCreateOpen(true)
  }

  return (
    <div>
      <PageHeader
        title="Calendar"
        description="Tasks, batch events, and leave across your schedule"
        actions={
          canCreate && (
            <Button size="sm" onClick={openCreate}>
              <CalendarPlus className="size-4" /> New event
            </Button>
          )
        }
      />

      {calendar.isLoading ? (
        <div className="space-y-3">
          <Skeleton className="h-12 w-full rounded-xl" />
          <Skeleton className="h-40 w-full rounded-xl" />
          <Skeleton className="h-12 w-full rounded-xl" />
        </div>
      ) : groups.length === 0 ? (
        <EmptyState title="Nothing scheduled" description="Your calendar is clear." />
      ) : (
        <div className="space-y-6">
          {groups.map(([day, entries]) => (
            <div key={day}>
              <div className="mb-2 flex items-center gap-2">
                <CalendarDays className="size-4 text-primary" />
                <h2 className="text-sm font-semibold capitalize">{new Date(`${day}T00:00:00`).toLocaleDateString(undefined, { weekday: 'long', month: 'short', day: 'numeric' })}</h2>
                <span className="text-xs text-muted-foreground">{entries.length} item{entries.length === 1 ? '' : 's'}</span>
              </div>
              <ul className="divide-y divide-border overflow-hidden rounded-xl border border-border">
                {entries.map((e, i) => {
                  const Icon = typeIcon[e.type]
                  const content = (
                    <>
                      <div className="flex size-9 shrink-0 items-center justify-center rounded-lg bg-muted/60 text-muted-foreground">
                        <Icon className="size-4" />
                      </div>
                      <div className="min-w-0 flex-1">
                        <div className="flex flex-wrap items-center gap-2">
                          <p className="font-medium">{e.title}</p>
                          <Badge variant={typeVariant[e.type]}>{e.type === 'task' ? 'Task' : e.type === 'event' ? 'Event' : 'Leave'}</Badge>
                          {e.status && <Badge variant="muted">{e.status}</Badge>}
                        </div>
                        <p className="mt-0.5 text-xs text-muted-foreground">
                          {clock(e.start)}
                          {e.end ? ` – ${clock(e.end)}` : ''}
                        </p>
                      </div>
                      {e.link && <ChevronRight className="size-4 shrink-0 text-muted-foreground" />}
                    </>
                  )
                  return (
                    <li key={i}>
                      {e.link ? (
                        <button
                          onClick={() => navigate(e.link)}
                          className="flex w-full items-center gap-3 px-4 py-3 text-left transition-colors hover:bg-muted/40"
                        >
                          {content}
                        </button>
                      ) : (
                        <div className="flex items-center gap-3 px-4 py-3">{content}</div>
                      )}
                    </li>
                  )
                })}
              </ul>
            </div>
          ))}
        </div>
      )}

      <Dialog
        open={createOpen}
        onClose={() => setCreateOpen(false)}
        title="New Batch Event"
        description="Schedule an event for your batch"
        footer={
          <>
            <Button variant="outline" onClick={() => setCreateOpen(false)}>
              Cancel
            </Button>
            <Button
              onClick={() => createEvent.mutate(form)}
              loading={createEvent.isPending}
              disabled={!form.title || !form.batch_id || !form.starts_at}
            >
              Create event
            </Button>
          </>
        }
      >
        <div className="grid gap-4">
          <div>
            <Label>Batch</Label>
            <Select value={form.batch_id} onChange={(e) => setForm((f) => ({ ...f, batch_id: e.target.value }))}>
              {batches.isLoading ? (
                <option>Loading…</option>
              ) : (
                (batches.data?.items ?? []).map((b) => (
                  <option key={b.id} value={b.id}>
                    {b.name}
                  </option>
                ))
              )}
            </Select>
          </div>
          <div>
            <Label>Title</Label>
            <Input value={form.title} onChange={(e) => setForm((f) => ({ ...f, title: e.target.value }))} />
          </div>
          <div>
            <Label>Description</Label>
            <Textarea rows={2} value={form.description} onChange={(e) => setForm((f) => ({ ...f, description: e.target.value }))} />
          </div>
          <div className="grid gap-4 sm:grid-cols-2">
            <div>
              <Label>Starts at</Label>
              <Input type="datetime-local" value={form.starts_at} onChange={(e) => setForm((f) => ({ ...f, starts_at: e.target.value }))} />
            </div>
            <div>
              <Label>Ends at</Label>
              <Input type="datetime-local" value={form.ends_at} onChange={(e) => setForm((f) => ({ ...f, ends_at: e.target.value }))} />
            </div>
          </div>
          <div>
            <Label>Location</Label>
            <Input value={form.location} onChange={(e) => setForm((f) => ({ ...f, location: e.target.value }))} placeholder="e.g. Room 2B or Google Meet" />
          </div>
        </div>
      </Dialog>
    </div>
  )
}