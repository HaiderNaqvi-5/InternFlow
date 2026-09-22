import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { Archive, CalendarDays, Clock3, Plus, Timer } from 'lucide-react'
import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { toast } from 'sonner'

import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Dialog } from '@/components/ui/dialog'
import { EmptyState } from '@/components/ui/empty-state'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { PageHeader } from '@/components/ui/page-header'
import { Skeleton } from '@/components/ui/skeleton'
import { useAuth } from '@/context/auth'
import { api, ApiError } from '@/lib/api'
import { formatClock, formatDate } from '@/lib/format'
import type { Batch, PaginatedBatches, PaginatedUsers } from '@/lib/types'

const statusVariant: Record<NonNullable<Batch['status']>, 'success' | 'muted' | 'outline' | 'info' | 'warning'> = {
  active: 'success',
  archived: 'muted',
}

interface NewBatchForm {
  name: string
  description: string
  start_date: string
  end_date: string
  capacity: string
  start_time: string
  end_time: string
  grace_minutes: string
  supervisor_id: string
}

const empty: NewBatchForm = {
  name: '',
  description: '',
  start_date: '',
  end_date: '',
  capacity: '20',
  start_time: '09:00',
  end_time: '17:00',
  grace_minutes: '15',
  supervisor_id: '',
}

export default function BatchesIndex() {
  const { user } = useAuth()
  const isAdmin = user?.role === 'admin'
  const navigate = useNavigate()
  const qc = useQueryClient()
  const [open, setOpen] = useState(false)
  const [form, setForm] = useState<NewBatchForm>(empty)

  const batches = useQuery({
    queryKey: ['batches'],
    queryFn: () => api.get<PaginatedBatches>('/api/v1/batches?page_size=200'),
  })
  const supervisors = useQuery({
    queryKey: ['users', 'supervisors'],
    queryFn: () => api.get<PaginatedUsers>('/api/v1/users?role=supervisor&page_size=200'),
    enabled: isAdmin,
  })

  const create = useMutation({
    mutationFn: (values: NewBatchForm) =>
      api.post<Batch>('/api/v1/batches', {
        name: values.name,
        description: values.description || null,
        start_date: values.start_date,
        end_date: values.end_date,
        capacity: Number(values.capacity),
        start_time: values.start_time,
        end_time: values.end_time,
        grace_minutes: Number(values.grace_minutes),
        supervisor_id: values.supervisor_id ? Number(values.supervisor_id) : null,
      }),
    onSuccess: () => {
      toast.success('Batch created')
      setOpen(false)
      setForm(empty)
      qc.invalidateQueries({ queryKey: ['batches'] })
    },
    onError: (e) => toast.error(e instanceof ApiError ? e.detail : 'Failed to create batch'),
  })

  const archive = useMutation({
    mutationFn: (id: number) => api.post(`/api/v1/batches/${id}/archive`),
    onSuccess: () => {
      toast.success('Batch archived')
      qc.invalidateQueries({ queryKey: ['batches'] })
    },
    onError: (e) => toast.error(e instanceof ApiError ? e.detail : 'Failed to archive batch'),
  })

  const set = (k: keyof NewBatchForm) => (e: React.ChangeEvent<HTMLInputElement | HTMLTextAreaElement | HTMLSelectElement>) =>
    setForm((f) => ({ ...f, [k]: e.target.value }))

  return (
    <div>
      <PageHeader
        title="Batches"
        description="Manage internship batches and their members"
        actions={
          isAdmin ? (
            <Button onClick={() => setOpen(true)}>
              <Plus className="size-4" /> New batch
            </Button>
          ) : undefined
        }
      />

      {batches.isLoading ? (
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {Array.from({ length: 3 }).map((_, i) => (
            <Skeleton key={i} className="h-40 rounded-xl" />
          ))}
        </div>
      ) : !batches.data || batches.data.items.length === 0 ? (
        <EmptyState title="No batches" description="Create a batch to get started." />
      ) : (
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {batches.data.items.map((b) => (
            <Card key={b.id} className="cursor-pointer transition-colors hover:bg-muted/40" onClick={() => navigate(`/batches/${b.id}`)}>
              <CardHeader className="flex-row items-start justify-between gap-2 pb-3">
                <CardTitle className="truncate">{b.name}</CardTitle>
                <Badge variant={statusVariant[b.status]}>{b.status}</Badge>
              </CardHeader>
              <CardContent className="space-y-2 text-sm">
                <p className="flex items-center gap-2 text-muted-foreground">
                  <CalendarDays className="size-4 shrink-0" />
                  {formatDate(b.start_date)} → {formatDate(b.end_date)}
                </p>
                <p className="flex items-center gap-2 text-muted-foreground">
                  <Clock3 className="size-4 shrink-0" />
                  {formatClock(b.start_time)} – {formatClock(b.end_time)}
                  <span className="inline-flex items-center gap-1 text-xs">
                    <Timer className="size-3" /> {b.grace_minutes}m grace
                  </span>
                </p>
                <div className="flex items-center justify-between pt-1">
                  <span className="text-muted-foreground">{b.supervisor_name ?? 'No supervisor'}</span>
                  <span className="text-xs text-muted-foreground">
                    {b.active_intern_count ?? 0}/{b.capacity} interns
                  </span>
                </div>
                {isAdmin && b.status !== 'archived' && (
                  <Button
                    variant="ghost"
                    size="sm"
                    className="w-full text-muted-foreground"
                    onClick={(e) => {
                      e.stopPropagation()
                      archive.mutate(b.id)
                    }}
                  >
                    <Archive className="size-4" /> Archive
                  </Button>
                )}
              </CardContent>
            </Card>
          ))}
        </div>
      )}

      <Dialog
        open={open}
        onClose={() => setOpen(false)}
        title="New Batch"
        description="Create a new internship batch"
        footer={
          <>
            <Button variant="outline" onClick={() => setOpen(false)}>
              Cancel
            </Button>
            <Button
              onClick={() => create.mutate(form)}
              loading={create.isPending || supervisors.isLoading}
              disabled={!form.name || !form.start_date || !form.end_date}
            >
              Create batch
            </Button>
          </>
        }
      >
        <div className="grid gap-4">
          <div>
            <Label>Name</Label>
            <Input value={form.name} onChange={set('name')} placeholder="Summer Internship 2026" />
          </div>
          <div>
            <Label>Description</Label>
            <Input value={form.description} onChange={set('description')} placeholder="Optional description" />
          </div>
          <div className="grid grid-cols-2 gap-3">
            <div>
              <Label>Start date</Label>
              <Input type="date" value={form.start_date} onChange={set('start_date')} />
            </div>
            <div>
              <Label>End date</Label>
              <Input type="date" value={form.end_date} onChange={set('end_date')} />
            </div>
          </div>
          <div className="grid grid-cols-2 gap-3">
            <div>
              <Label>Capacity</Label>
              <Input type="number" min={1} value={form.capacity} onChange={set('capacity')} />
            </div>
            <div>
              <Label>Grace minutes</Label>
              <Input type="number" min={0} value={form.grace_minutes} onChange={set('grace_minutes')} />
            </div>
          </div>
          <div className="grid grid-cols-2 gap-3">
            <div>
              <Label>Start time</Label>
              <Input type="time" value={form.start_time} onChange={set('start_time')} />
            </div>
            <div>
              <Label>End time</Label>
              <Input type="time" value={form.end_time} onChange={set('end_time')} />
            </div>
          </div>
          <div>
            <Label>Supervisor</Label>
            <select
              className="h-9 w-full rounded-lg border border-input bg-transparent px-3 text-sm"
              value={form.supervisor_id}
              onChange={set('supervisor_id')}
            >
              <option value="">No supervisor</option>
              {(supervisors.data?.items ?? []).map((s) => (
                <option key={s.id} value={s.id}>
                  {s.full_name}
                </option>
              ))}
            </select>
          </div>
        </div>
      </Dialog>
    </div>
  )
}
