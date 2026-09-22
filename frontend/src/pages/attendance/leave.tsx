import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { CalendarOff, Plus } from 'lucide-react'
import { useState } from 'react'
import { toast } from 'sonner'

import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { EmptyState } from '@/components/ui/empty-state'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { PageHeader } from '@/components/ui/page-header'
import { Select } from '@/components/ui/select'
import { Spinner } from '@/components/ui/spinner'
import { Table, TBody, TD, TH, THead, TR } from '@/components/ui/table'
import { Textarea } from '@/components/ui/textarea'
import { api, ApiError } from '@/lib/api'
import { formatDate, titleCase } from '@/lib/format'
import type { LeaveRequest } from '@/lib/types'

type BadgeVariant = 'default' | 'success' | 'warning' | 'destructive' | 'muted' | 'outline' | 'info'

const statusVariant: Record<LeaveRequest['status'], BadgeVariant> = {
  pending: 'warning',
  approved: 'success',
  rejected: 'destructive',
}

const LEAVE_TYPES = ['annual', 'sick', 'personal', 'emergency', 'other']

interface LeaveForm {
  start_date: string
  end_date: string
  leave_type: string
  reason: string
}

const emptyForm: LeaveForm = { start_date: '', end_date: '', leave_type: 'annual', reason: '' }

export default function LeavePage() {
  const qc = useQueryClient()
  const [form, setForm] = useState<LeaveForm>(emptyForm)

  const requests = useQuery({
    queryKey: ['leave'],
    queryFn: () => api.get<LeaveRequest[]>('/api/v1/leave'),
  })

  const create = useMutation({
    mutationFn: (v: LeaveForm) =>
      api.post('/api/v1/leave', {
        start_date: v.start_date,
        end_date: v.end_date,
        reason: v.reason,
        leave_type: v.leave_type,
      }),
    onSuccess: () => {
      toast.success('Leave request submitted')
      setForm(emptyForm)
      qc.invalidateQueries({ queryKey: ['leave'] })
      qc.invalidateQueries({ queryKey: ['calendar'] })
    },
    onError: (e) => toast.error(e instanceof ApiError ? e.detail : 'Failed to request leave'),
  })

  return (
    <div>
      <PageHeader title="Leave" description="Request time off and track your leave requests" />

      <div className="grid gap-4 lg:grid-cols-2">
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2 text-sm">
              <Plus className="size-4 text-primary" /> Request leave
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="grid gap-4">
              <div className="grid gap-4 sm:grid-cols-2">
                <div>
                  <Label htmlFor="start">Start date</Label>
                  <Input
                    id="start"
                    type="date"
                    value={form.start_date}
                    onChange={(e) => setForm((f) => ({ ...f, start_date: e.target.value }))}
                  />
                </div>
                <div>
                  <Label htmlFor="end">End date</Label>
                  <Input
                    id="end"
                    type="date"
                    min={form.start_date || undefined}
                    value={form.end_date}
                    onChange={(e) => setForm((f) => ({ ...f, end_date: e.target.value }))}
                  />
                </div>
              </div>
              <div>
                <Label htmlFor="type">Leave type</Label>
                <Select id="type" value={form.leave_type} onChange={(e) => setForm((f) => ({ ...f, leave_type: e.target.value }))}>
                  {LEAVE_TYPES.map((t) => (
                    <option key={t} value={t}>
                      {titleCase(t)}
                    </option>
                  ))}
                </Select>
              </div>
              <div>
                <Label htmlFor="reason">Reason</Label>
                <Textarea
                  id="reason"
                  rows={3}
                  value={form.reason}
                  onChange={(e) => setForm((f) => ({ ...f, reason: e.target.value }))}
                  placeholder="Why are you requesting this leave?"
                />
              </div>
              <div className="flex justify-end">
                <Button
                  onClick={() => create.mutate(form)}
                  loading={create.isPending}
                  disabled={!form.start_date || !form.end_date || !form.reason.trim()}
                >
                  <CalendarOff className="size-4" /> Submit request
                </Button>
              </div>
            </div>
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle className="text-sm">My requests</CardTitle>
          </CardHeader>
          <CardContent className="p-0">
            {requests.isLoading ? (
              <div className="p-5">
                <Spinner />
              </div>
            ) : requests.data?.length === 0 ? (
              <div className="p-5">
                <EmptyState title="No leave requests" description="You haven't requested any leave yet." />
              </div>
            ) : (
              <Table>
                <THead>
                  <TR>
                    <TH>Dates</TH>
                    <TH>Type</TH>
                    <TH>Reason</TH>
                    <TH>Status</TH>
                  </TR>
                </THead>
                <TBody>
                  {(requests.data ?? []).map((r) => (
                    <TR key={r.id}>
                      <TD className="font-medium">
                        {formatDate(r.start_date)} → {formatDate(r.end_date)}
                      </TD>
                      <TD className="text-muted-foreground">{r.leave_type ? titleCase(r.leave_type) : '—'}</TD>
                      <TD className="text-muted-foreground">{r.reason ?? '—'}</TD>
                      <TD>
                        <Badge variant={statusVariant[r.status]}>{titleCase(r.status)}</Badge>
                      </TD>
                    </TR>
                  ))}
                </TBody>
              </Table>
            )}
          </CardContent>
        </Card>
      </div>
    </div>
  )
}