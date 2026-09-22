import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { Plus, Search } from 'lucide-react'
import { useState } from 'react'
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
import { Table, TBody, TD, TH, THead, TR } from '@/components/ui/table'
import { Textarea } from '@/components/ui/textarea'
import { useAuth } from '@/context/auth'
import { api, ApiError } from '@/lib/api'
import { fromLocalInputValue, relativeTime, titleCase } from '@/lib/format'
import type {
  PaginatedBatches,
  PaginatedTasks,
  PaginatedUsers,
  Task,
  TaskCategory,
  TaskPriority,
  TaskScope,
  TaskStatus,
} from '@/lib/types'

type BadgeVariant = 'default' | 'success' | 'warning' | 'destructive' | 'muted' | 'outline' | 'info'

const statusVariant: Record<TaskStatus, BadgeVariant> = {
  open: 'default',
  in_progress: 'info',
  submitted: 'warning',
  reviewed: 'info',
  pending_resubmission: 'destructive',
}

const priorityVariant: Record<TaskPriority, BadgeVariant> = {
  Low: 'outline',
  Medium: 'default',
  High: 'warning',
}

const scopeVariant: Record<TaskScope, BadgeVariant> = {
  batch: 'info',
  individual: 'muted',
}

const ALL_STATUSES: TaskStatus[] = ['open', 'in_progress', 'submitted', 'reviewed', 'pending_resubmission']
const ALL_SCOPES: TaskScope[] = ['batch', 'individual']
const CATEGORIES: TaskCategory[] = ['Development', 'Design', 'Research', 'Documentation', 'Testing', 'Presentation', 'Other']
const PRIORITIES: TaskPriority[] = ['Low', 'Medium', 'High']

interface TaskForm {
  title: string
  description: string
  scope: TaskScope
  batch_id: string
  assignee_id: string
  category: TaskCategory
  priority: TaskPriority
  deadline: string
  estimated_effort_hours: string
}

const emptyForm = (batchId = ''): TaskForm => ({
  title: '',
  description: '',
  scope: 'batch',
  batch_id: batchId,
  assignee_id: '',
  category: 'Development',
  priority: 'Medium',
  deadline: '',
  estimated_effort_hours: '',
})

export default function TasksListPage() {
  const { user } = useAuth()
  const isIntern = user?.role === 'intern'
  const qc = useQueryClient()
  const navigate = useNavigate()

  const [status, setStatus] = useState('')
  const [scope, setScope] = useState('')
  const [search, setSearch] = useState('')
  const [newOpen, setNewOpen] = useState(false)
  const [form, setForm] = useState<TaskForm>(emptyForm())

  const params = new URLSearchParams({ page_size: '50' })
  if (status) params.set('status', status)
  if (scope) params.set('scope', scope)
  if (search.trim()) params.set('search', search.trim())

  const tasks = useQuery({
    queryKey: ['tasks', status, scope, search],
    queryFn: () => api.get<PaginatedTasks>(`/api/v1/tasks?${params.toString()}`),
  })

  const batches = useQuery({
    queryKey: ['batches'],
    queryFn: () => api.get<PaginatedBatches>('/api/v1/batches?page_size=100'),
    enabled: !isIntern,
  })

  const interns = useQuery({
    queryKey: ['users', 'interns'],
    queryFn: () => api.get<PaginatedUsers>('/api/v1/users?role=intern&page_size=300'),
    enabled: !isIntern,
  })

  const openNew = () => {
    const firstBatch = batches.data?.items?.[0]?.id
    setForm(emptyForm(firstBatch ? String(firstBatch) : ''))
    setNewOpen(true)
  }

  const create = useMutation({
    mutationFn: (v: TaskForm) =>
      api.post<Task>('/api/v1/tasks', {
        title: v.title,
        description: v.description || null,
        scope: v.scope,
        batch_id: Number(v.batch_id),
        assignee_id: v.assignee_id ? Number(v.assignee_id) : null,
        category: v.category,
        priority: v.priority,
        deadline: fromLocalInputValue(v.deadline),
        estimated_effort_hours: v.estimated_effort_hours ? Number(v.estimated_effort_hours) : null,
      }),
    onSuccess: () => {
      toast.success('Task created')
      setNewOpen(false)
      qc.invalidateQueries({ queryKey: ['tasks'] })
    },
    onError: (e) => toast.error(e instanceof ApiError ? e.detail : 'Failed to create task'),
  })

  const items = tasks.data?.items ?? []

  return (
    <div>
      <PageHeader
        title="Tasks"
        description={isIntern ? 'Your assigned tasks' : 'Manage tasks for your batches'}
        actions={
          !isIntern && (
            <Button size="sm" onClick={openNew}>
              <Plus className="size-4" /> New Task
            </Button>
          )
        }
      />

      <div className="mb-4 flex flex-wrap items-center gap-3">
        <div className="relative w-full max-w-xs">
          <Search className="absolute left-3 top-1/2 size-4 -translate-y-1/2 text-muted-foreground" />
          <Input
            className="pl-9"
            placeholder="Search tasks…"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
          />
        </div>
        <Select className="w-44" value={status} onChange={(e) => setStatus(e.target.value)}>
          <option value="">All statuses</option>
          {ALL_STATUSES.map((s) => (
            <option key={s} value={s}>
              {titleCase(s)}
            </option>
          ))}
        </Select>
        <Select className="w-40" value={scope} onChange={(e) => setScope(e.target.value)}>
          <option value="">All scopes</option>
          {ALL_SCOPES.map((s) => (
            <option key={s} value={s}>
              {titleCase(s)}
            </option>
          ))}
        </Select>
      </div>

      {tasks.isLoading ? (
        <Skeleton className="h-64 rounded-xl" />
      ) : items.length === 0 ? (
        <EmptyState title="No tasks found" description="No tasks match this filter." />
      ) : (
        <div className="overflow-hidden rounded-xl border border-border">
          <Table>
            <THead>
              <TR>
                <TH>Title</TH>
                <TH>Scope</TH>
                <TH>Category</TH>
                <TH>Priority</TH>
                <TH>Status</TH>
                <TH>Deadline</TH>
              </TR>
            </THead>
            <TBody>
              {items.map((t) => (
                <TR key={t.id} onClick={() => navigate(`/tasks/${t.id}`)}>
                  <TD className="font-medium">{t.title}</TD>
                  <TD>
                    <Badge variant={scopeVariant[t.scope]}>{titleCase(t.scope)}</Badge>
                  </TD>
                  <TD className="text-muted-foreground">{t.category ?? '—'}</TD>
                  <TD>
                    <Badge variant={t.priority ? priorityVariant[t.priority] : 'outline'}>{t.priority ?? '—'}</Badge>
                  </TD>
                  <TD>
                    <Badge variant={statusVariant[t.status]}>{titleCase(t.status)}</Badge>
                  </TD>
                  <TD className="text-muted-foreground">{relativeTime(t.deadline)}</TD>
                </TR>
              ))}
            </TBody>
          </Table>
        </div>
      )}

      <Dialog
        open={newOpen}
        onClose={() => setNewOpen(false)}
        title="New Task"
        description="Create a task for your batch"
        wide
        footer={
          <>
            <Button variant="outline" onClick={() => setNewOpen(false)}>
              Cancel
            </Button>
            <Button
              onClick={() => create.mutate(form)}
              loading={create.isPending}
              disabled={!form.title || !form.batch_id || !form.deadline || (form.scope === 'individual' && !form.assignee_id)}
            >
              Create task
            </Button>
          </>
        }
      >
        <div className="grid gap-4">
          <div>
            <Label>Title</Label>
            <Input value={form.title} onChange={(e) => setForm((f) => ({ ...f, title: e.target.value }))} />
          </div>
          <div>
            <Label>Description</Label>
            <Textarea
              rows={3}
              value={form.description}
              onChange={(e) => setForm((f) => ({ ...f, description: e.target.value }))}
            />
          </div>
          <div className="grid gap-4 sm:grid-cols-2">
            <div>
              <Label>Scope</Label>
              <Select value={form.scope} onChange={(e) => setForm((f) => ({ ...f, scope: e.target.value as TaskScope }))}>
                {ALL_SCOPES.map((s) => (
                  <option key={s} value={s}>
                    {titleCase(s)}
                  </option>
                ))}
              </Select>
            </div>
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
          </div>
          {form.scope === 'individual' && (
            <div>
              <Label>Assignee</Label>
              <Select value={form.assignee_id} onChange={(e) => setForm((f) => ({ ...f, assignee_id: e.target.value }))}>
                <option value="">Select intern…</option>
                {(interns.data?.items ?? []).map((u) => (
                  <option key={u.id} value={u.id}>
                    {u.full_name}
                  </option>
                ))}
              </Select>
            </div>
          )}
          <div className="grid gap-4 sm:grid-cols-2">
            <div>
              <Label>Category</Label>
              <Select value={form.category} onChange={(e) => setForm((f) => ({ ...f, category: e.target.value as TaskCategory }))}>
                {CATEGORIES.map((c) => (
                  <option key={c} value={c}>
                    {c}
                  </option>
                ))}
              </Select>
            </div>
            <div>
              <Label>Priority</Label>
              <Select value={form.priority} onChange={(e) => setForm((f) => ({ ...f, priority: e.target.value as TaskPriority }))}>
                {PRIORITIES.map((p) => (
                  <option key={p} value={p}>
                    {p}
                  </option>
                ))}
              </Select>
            </div>
          </div>
          <div className="grid gap-4 sm:grid-cols-2">
            <div>
              <Label>Deadline</Label>
              <Input
                type="datetime-local"
                value={form.deadline}
                onChange={(e) => setForm((f) => ({ ...f, deadline: e.target.value }))}
              />
            </div>
            <div>
              <Label>Estimated effort (hours)</Label>
              <Input
                type="number"
                min={0}
                step="0.5"
                value={form.estimated_effort_hours}
                onChange={(e) => setForm((f) => ({ ...f, estimated_effort_hours: e.target.value }))}
              />
            </div>
          </div>
        </div>
      </Dialog>
    </div>
  )
}