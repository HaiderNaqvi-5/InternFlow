import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { CalendarDays, Clock3, Plus, Trash2, UserPlus, Users } from 'lucide-react'
import { useMemo, useState } from 'react'
import { useNavigate, useParams } from 'react-router-dom'
import { toast } from 'sonner'

import { Avatar } from '@/components/ui/avatar'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Dialog } from '@/components/ui/dialog'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { PageHeader } from '@/components/ui/page-header'
import { Skeleton } from '@/components/ui/skeleton'
import { Spinner } from '@/components/ui/spinner'
import { StatCard } from '@/components/ui/stat-card'
import { Table, TBody, TD, TH, THead, TR } from '@/components/ui/table'
import { useAuth } from '@/context/auth'
import { api, ApiError } from '@/lib/api'
import { formatClock, formatDate } from '@/lib/format'
import type { BatchDetail, PaginatedUsers } from '@/lib/types'

export default function BatchDetailPage() {
  const { batchId } = useParams()
  const id = Number(batchId)
  const { user } = useAuth()
  const isAdmin = user?.role === 'admin'
  const qc = useQueryClient()
  const navigate = useNavigate()

  const [editOpen, setEditOpen] = useState(false)
  const [memberIds, setMemberIds] = useState<number[]>([])
  const [addOpen, setAddOpen] = useState(false)
  const [removeOpen, setRemoveOpen] = useState(0)

  const detail = useQuery({
    queryKey: ['batch', id],
    queryFn: () => api.get<BatchDetail>(`/api/v1/batches/${id}`),
    enabled: !Number.isNaN(id),
  })
  const interns = useQuery({
    queryKey: ['users', 'interns'],
    queryFn: () => api.get<PaginatedUsers>('/api/v1/users?role=intern&page_size=300'),
    enabled: isAdmin,
  })

  const batch = detail.data
  const memberIdsSet = useMemo(
    () => new Set((batch?.members ?? []).map((m) => m.intern_id)),
    [batch],
  )
  const availableInterns = (interns.data?.items ?? []).filter((u) => !memberIdsSet.has(u.id))

  const invalidate = () => {
    qc.invalidateQueries({ queryKey: ['batch', id] })
    qc.invalidateQueries({ queryKey: ['batches'] })
  }

  const addInterns = useMutation({
    mutationFn: async (ids: number[]) => {
      if (ids.length === 1) await api.post(`/api/v1/batches/${id}/interns`, { user_id: ids[0] })
      else await api.post(`/api/v1/batches/${id}/interns/bulk`, { user_ids: ids })
    },
    onSuccess: () => {
      toast.success('Intern(s) added')
      setAddOpen(false)
      setMemberIds([])
      invalidate()
    },
    onError: (e) => toast.error(e instanceof ApiError ? e.detail : 'Failed to add intern'),
  })

  const removeIntern = useMutation({
    mutationFn: (internId: number) => api.delete(`/api/v1/batches/${id}/interns/${internId}`),
    onSuccess: () => {
      toast.success('Intern removed')
      setRemoveOpen(0)
      invalidate()
    },
    onError: (e) => toast.error(e instanceof ApiError ? e.detail : 'Failed to remove intern'),
  })

  const [editForm, setEditForm] = useState({
    name: '',
    description: '',
    capacity: '',
    start_time: '',
    end_time: '',
    grace_minutes: '',
  })

  const openEdit = () => {
    if (!batch) return
    setEditForm({
      name: batch.name,
      description: batch.description ?? '',
      capacity: String(batch.capacity),
      start_time: batch.start_time,
      end_time: batch.end_time,
      grace_minutes: String(batch.grace_minutes),
    })
    setEditOpen(true)
  }

  const update = useMutation({
    mutationFn: () =>
      api.patch(`/api/v1/batches/${id}`, {
        name: editForm.name,
        description: editForm.description || null,
        capacity: Number(editForm.capacity),
        start_time: editForm.start_time,
        end_time: editForm.end_time,
        grace_minutes: Number(editForm.grace_minutes),
      }),
    onSuccess: () => {
      toast.success('Batch updated')
      setEditOpen(false)
      invalidate()
    },
    onError: (e) => toast.error(e instanceof ApiError ? e.detail : 'Failed to update batch'),
  })

  if (Number.isNaN(id)) return null

  return (
    <div>
      <PageHeader
        title={batch?.name ?? 'Batch'}
        description={batch?.description ?? undefined}
        actions={
          <>
            {isAdmin && (
              <Button variant="outline" onClick={openEdit}>
                Edit
              </Button>
            )}
            <Button variant="outline" onClick={() => navigate('/batches')}>
              All batches
            </Button>
          </>
        }
      />

      {detail.isLoading ? (
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
          {Array.from({ length: 4 }).map((_, i) => (
            <Skeleton key={i} className="h-28 rounded-xl" />
          ))}
        </div>
      ) : !batch ? (
        <p className="text-sm text-muted-foreground">Batch not found.</p>
      ) : (
        <>
          <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
            <StatCard label="Active Interns" value={`${batch.active_intern_count ?? 0}/${batch.capacity}`} icon={<Users className="size-4" />} />
            <StatCard label="Supervisor" value={batch.supervisor_name ?? 'None'} icon={<UserPlus className="size-4" />} />
            <StatCard
              label="Working Hours"
              value={`${formatClock(batch.start_time)} – ${formatClock(batch.end_time)}`}
              icon={<Clock3 className="size-4" />}
              hint={`${batch.grace_minutes}m grace`}
            />
            <StatCard
              label="Dates"
              value={formatDate(batch.start_date)}
              icon={<CalendarDays className="size-4" />}
              hint={`→ ${formatDate(batch.end_date)}`}
            />
          </div>

          <Card className="mt-6">
            <CardHeader className="flex-row items-start justify-between gap-2">
              <div>
                <CardTitle>Members</CardTitle>
                <CardDescription>
                  {batch.members.length} intern{batch.members.length === 1 ? '' : 's'} in this batch
                </CardDescription>
              </div>
              {isAdmin && (
                <Button size="sm" onClick={() => setAddOpen(true)}>
                  <Plus className="size-4" /> Add intern
                </Button>
              )}
            </CardHeader>
            <CardContent className="p-0">
              <Table>
                <THead>
                  <TR>
                    <TH>Intern</TH>
                    <TH>Email</TH>
                    <TH>Joined</TH>
                    <TH>Status</TH>
                    {isAdmin && <TH className="text-right">Actions</TH>}
                  </TR>
                </THead>
                <TBody>
                  {batch.members.length === 0 ? (
                    <TR>
                      <TD>No members yet.</TD>
                    </TR>
                  ) : (
                    batch.members.map((m) => (
                      <TR key={m.id}>
                        <TD>
                          <div className="flex items-center gap-3">
                            <Avatar name={m.intern_name ?? '?'} />
                            <span className="font-medium">{m.intern_name ?? `Intern #${m.intern_id}`}</span>
                          </div>
                        </TD>
                        <TD className="text-muted-foreground">{m.email ?? '—'}</TD>
                        <TD className="text-muted-foreground">{formatDate(m.joined_at)}</TD>
                        <TD>
                          <Badge variant={m.is_active ? 'success' : 'muted'}>{m.is_active ? 'Active' : 'Inactive'}</Badge>
                        </TD>
                        {isAdmin && (
                          <TD className="text-right">
                            <Button
                              variant="ghost"
                              size="sm"
                              className="text-destructive"
                              onClick={() => setRemoveOpen(m.intern_id)}
                            >
                              <Trash2 className="size-4" />
                            </Button>
                          </TD>
                        )}
                      </TR>
                    ))
                  )}
                </TBody>
              </Table>
            </CardContent>
          </Card>
        </>
      )}

      {isAdmin && (
        <>
          <Dialog
            open={editOpen}
            onClose={() => setEditOpen(false)}
            title="Edit Batch"
            footer={
              <>
                <Button variant="outline" onClick={() => setEditOpen(false)}>
                  Cancel
                </Button>
                <Button onClick={() => update.mutate()} loading={update.isPending}>
                  Save changes
                </Button>
              </>
            }
          >
            <div className="grid gap-4">
              <div>
                <Label>Name</Label>
                <Input value={editForm.name} onChange={(e) => setEditForm((f) => ({ ...f, name: e.target.value }))} />
              </div>
              <div>
                <Label>Description</Label>
                <Input value={editForm.description} onChange={(e) => setEditForm((f) => ({ ...f, description: e.target.value }))} />
              </div>
              <div className="grid grid-cols-2 gap-3">
                <div>
                  <Label>Capacity</Label>
                  <Input type="number" value={editForm.capacity} onChange={(e) => setEditForm((f) => ({ ...f, capacity: e.target.value }))} />
                </div>
                <div>
                  <Label>Grace minutes</Label>
                  <Input type="number" value={editForm.grace_minutes} onChange={(e) => setEditForm((f) => ({ ...f, grace_minutes: e.target.value }))} />
                </div>
              </div>
              <div className="grid grid-cols-2 gap-3">
                <div>
                  <Label>Start time</Label>
                  <Input type="time" value={editForm.start_time} onChange={(e) => setEditForm((f) => ({ ...f, start_time: e.target.value }))} />
                </div>
                <div>
                  <Label>End time</Label>
                  <Input type="time" value={editForm.end_time} onChange={(e) => setEditForm((f) => ({ ...f, end_time: e.target.value }))} />
                </div>
              </div>
            </div>
          </Dialog>

          <Dialog
            open={addOpen}
            onClose={() => {
              setAddOpen(false)
              setMemberIds([])
            }}
            title="Add Interns"
            description="Select interns to add. Capacity is enforced automatically."
            footer={
              <>
                <Button
                  variant="outline"
                  onClick={() => {
                    setAddOpen(false)
                    setMemberIds([])
                  }}
                >
                  Cancel
                </Button>
                <Button
                  onClick={() => addInterns.mutate(memberIds)}
                  loading={addInterns.isPending}
                  disabled={memberIds.length === 0}
                >
                  Add {memberIds.length || ''}
                </Button>
              </>
            }
          >
            <div className="max-h-[50vh] space-y-1 overflow-y-auto">
              {interns.isLoading ? (
                <Spinner />
              ) : availableInterns.length === 0 ? (
                <p className="text-sm text-muted-foreground">No available interns to add.</p>
              ) : (
                availableInterns.map((u) => {
                  const checked = memberIds.includes(u.id)
                  return (
                    <label
                      key={u.id}
                      className="flex cursor-pointer items-center gap-3 rounded-lg p-2 hover:bg-muted/50"
                    >
                      <input
                        type="checkbox"
                        checked={checked}
                        onChange={() =>
                          setMemberIds((prev) => (checked ? prev.filter((x) => x !== u.id) : [...prev, u.id]))
                        }
                      />
                      <Avatar name={u.full_name} />
                      <span className="text-sm font-medium">{u.full_name}</span>
                      <span className="truncate text-sm text-muted-foreground">{u.email}</span>
                    </label>
                  )
                })
              )}
            </div>
          </Dialog>

          <Dialog
            open={removeOpen !== 0}
            onClose={() => setRemoveOpen(0)}
            title="Remove Intern"
            description="Remove this intern from the batch? This does not delete their account."
            footer={
              <>
                <Button variant="outline" onClick={() => setRemoveOpen(0)}>
                  Cancel
                </Button>
                <Button
                  variant="destructive"
                  onClick={() => removeIntern.mutate(removeOpen)}
                  loading={removeIntern.isPending}
                >
                  Remove
                </Button>
              </>
            }
          />
        </>
      )}
    </div>
  )
}
