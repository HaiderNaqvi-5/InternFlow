import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { CalendarCheck, LogIn, LogOut, NotebookPen, Percent, Timer, Users } from 'lucide-react'
import { useEffect, useRef, useState } from 'react'
import { toast } from 'sonner'

import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { EmptyState } from '@/components/ui/empty-state'
import { Label } from '@/components/ui/label'
import { PageHeader } from '@/components/ui/page-header'
import { Select } from '@/components/ui/select'
import { Skeleton } from '@/components/ui/skeleton'
import { Spinner } from '@/components/ui/spinner'
import { StatCard } from '@/components/ui/stat-card'
import { Table, TBody, TD, TH, THead, TR } from '@/components/ui/table'
import { Textarea } from '@/components/ui/textarea'
import { useAuth } from '@/context/auth'
import { api, ApiError } from '@/lib/api'
import { durationLabel, formatDate, titleCase } from '@/lib/format'
import type { AttendanceRecord, AttendanceSummaryRow } from '@/lib/types'

type BadgeVariant = 'default' | 'success' | 'warning' | 'destructive' | 'muted' | 'outline' | 'info'

interface AttendancePage {
  items: AttendanceRecord[]
  total: number
  page: number
  page_size: number
}

const lateVariant: Record<string, BadgeVariant> = {
  on_time: 'success',
  late: 'warning',
  absent: 'destructive',
}

function timeOf(value: string | null | undefined): string {
  if (!value) return '—'
  const d = new Date(value)
  if (Number.isNaN(d.getTime())) return value
  return d.toLocaleTimeString(undefined, { hour: 'numeric', minute: '2-digit' })
}

export default function AttendancePage() {
  const { user } = useAuth()
  const isIntern = user?.role === 'intern'
  const qc = useQueryClient()
  const [internFilter, setInternFilter] = useState('')
  const [log, setLog] = useState({ work_done: '', blockers: '', next_day_plan: '' })
  const hydrated = useRef(false)

  const today = useQuery({
    queryKey: ['attendance', 'today'],
    queryFn: () => api.get<AttendanceRecord | null>('/api/v1/attendance/today'),
    enabled: isIntern,
  })

  const summary = useQuery({
    queryKey: ['attendance', 'summary'],
    queryFn: () => api.get<AttendanceSummaryRow[]>('/api/v1/attendance/summary'),
    enabled: !isIntern,
  })

  const records = useQuery({
    queryKey: ['attendance', 'records', internFilter],
    queryFn: () =>
      api.get<AttendancePage>(
        `/api/v1/attendance/records?page_size=100${internFilter ? `&intern_id=${internFilter}` : ''}`,
      ),
  })

  useEffect(() => {
    if (!hydrated.current && today.data) {
      hydrated.current = true
      if (today.data) {
        setLog({
          work_done: today.data.work_done ?? '',
          blockers: today.data.blockers ?? '',
          next_day_plan: today.data.next_day_plan ?? '',
        })
      }
    }
  }, [today.data])

  const invalidateAttendance = () => {
    qc.invalidateQueries({ queryKey: ['attendance'] })
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

  const saveLog = useMutation({
    mutationFn: () =>
      api.post('/api/v1/attendance/daily-log', {
        work_done: log.work_done || null,
        blockers: log.blockers || null,
        next_day_plan: log.next_day_plan || null,
      }),
    onSuccess: () => {
      toast.success('Daily log saved')
      invalidateAttendance()
    },
    onError: (e) => toast.error(e instanceof ApiError ? e.detail : 'Failed to save daily log'),
  })

  const record = today.data
  const checkedIn = !!record?.check_in
  const checkedOut = !!record?.check_out

  if (isIntern) {
    return (
      <div>
        <PageHeader title="Attendance" description="Check in, manage your daily log, and review your history" />
        <div className="grid gap-4 lg:grid-cols-2">
          <Card>
            <CardHeader>
              <CardTitle className="flex items-center gap-2 text-sm">
                <CalendarCheck className="size-4 text-primary" /> Today
              </CardTitle>
            </CardHeader>
            <CardContent>
              {today.isLoading ? (
                <Skeleton className="h-44 rounded-xl" />
              ) : !record ? (
                <div className="flex flex-col items-center gap-4 py-10 text-center">
                  <p className="text-sm text-muted-foreground">You haven't checked in yet today.</p>
                  <Button size="lg" onClick={() => checkIn.mutate()} loading={checkIn.isPending}>
                    <LogIn className="size-4" /> Check in
                  </Button>
                </div>
              ) : (
                <div className="space-y-5">
                  <div className="grid grid-cols-2 gap-3">
                    <div className="rounded-lg bg-muted/50 p-4 text-center">
                      <p className="text-xs uppercase tracking-wide text-muted-foreground">Check-in</p>
                      <p className="mt-1 text-2xl font-bold">{timeOf(record.check_in)}</p>
                      <p className="mt-0.5 text-xs text-muted-foreground">{record.check_in ? formatDate(record.check_in) : ''}</p>
                    </div>
                    <div className="rounded-lg bg-muted/50 p-4 text-center">
                      <p className="text-xs uppercase tracking-wide text-muted-foreground">Check-out</p>
                      <p className="mt-1 text-2xl font-bold">{timeOf(record.check_out)}</p>
                      <p className="mt-0.5 text-xs text-muted-foreground">{record.check_out ? formatDate(record.check_out) : ''}</p>
                    </div>
                  </div>
                  <div className="flex gap-2">
                    <Button className="flex-1" onClick={() => checkIn.mutate()} loading={checkIn.isPending} disabled={checkedIn}>
                      <LogIn className="size-4" /> Check in
                    </Button>
                    <Button
                      variant="secondary"
                      className="flex-1"
                      onClick={() => checkOut.mutate()}
                      loading={checkOut.isPending}
                      disabled={!checkedIn || checkedOut}
                    >
                      <LogOut className="size-4" /> Check out
                    </Button>
                  </div>
                  {record.worked_hours != null && (
                    <p className="text-center text-xs text-muted-foreground">
                      Worked: <span className="font-medium text-foreground">{durationLabel(record.worked_hours)}</span>
                    </p>
                  )}
                </div>
              )}
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <CardTitle className="flex items-center gap-2 text-sm">
                <NotebookPen className="size-4 text-primary" /> Daily log
              </CardTitle>
            </CardHeader>
            <CardContent>
              <div className="grid gap-4">
                <div>
                  <Label htmlFor="work-done">What did you work on today?</Label>
                  <Textarea
                    id="work-done"
                    rows={2}
                    value={log.work_done}
                    onChange={(e) => setLog((f) => ({ ...f, work_done: e.target.value }))}
                  />
                </div>
                <div>
                  <Label htmlFor="blockers">Blockers</Label>
                  <Textarea
                    id="blockers"
                    rows={2}
                    value={log.blockers}
                    onChange={(e) => setLog((f) => ({ ...f, blockers: e.target.value }))}
                  />
                </div>
                <div>
                  <Label htmlFor="next-plan">Plan for tomorrow</Label>
                  <Textarea
                    id="next-plan"
                    rows={2}
                    value={log.next_day_plan}
                    onChange={(e) => setLog((f) => ({ ...f, next_day_plan: e.target.value }))}
                  />
                </div>
                <div className="flex justify-end">
                  <Button onClick={() => saveLog.mutate()} loading={saveLog.isPending}>
                    Save log
                  </Button>
                </div>
              </div>
            </CardContent>
          </Card>
        </div>

        <Card className="mt-6">
          <CardHeader>
            <CardTitle className="text-sm">History</CardTitle>
          </CardHeader>
          <CardContent className="p-0">
            {records.isLoading ? (
              <div className="p-5">
                <Spinner />
              </div>
            ) : records.data?.items.length === 0 ? (
              <div className="p-5">
                <EmptyState title="No attendance records" />
              </div>
            ) : (
              <Table>
                <THead>
                  <TR>
                    <TH>Date</TH>
                    <TH>Check-in</TH>
                    <TH>Check-out</TH>
                    <TH>Hours</TH>
                    <TH>Status</TH>
                  </TR>
                </THead>
                <TBody>
                  {(records.data?.items ?? []).map((r) => (
                    <TR key={r.id}>
                      <TD className="font-medium">{formatDate(r.date)}</TD>
                      <TD className="text-muted-foreground">{timeOf(r.check_in)}</TD>
                      <TD className="text-muted-foreground">{timeOf(r.check_out)}</TD>
                      <TD className="text-muted-foreground">{durationLabel(r.worked_hours)}</TD>
                      <TD>
                        <Badge variant={lateVariant[r.late_status ?? ''] ?? 'muted'}>
                          {r.late_status ? titleCase(r.late_status) : '—'}
                        </Badge>
                      </TD>
                    </TR>
                  ))}
                </TBody>
              </Table>
            )}
          </CardContent>
        </Card>
      </div>
    )
  }

  const rows = summary.data ?? []

  return (
    <div>
      <PageHeader title="Attendance" description="Monitor attendance across your batch" />
      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <StatCard
          label="Interns Tracked"
          value={rows.length}
          icon={<Users className="size-4" />}
        />
        <StatCard
          label="Avg Attendance"
          value={rows.length ? `${Math.round(rows.reduce((acc, r) => acc + r.attendance_rate, 0) / rows.length)}%` : '—'}
          icon={<Percent className="size-4" />}
        />
        <StatCard
          label="Total Present Days"
          value={rows.reduce((acc, r) => acc + r.present_days, 0)}
          icon={<CalendarCheck className="size-4" />}
        />
        <StatCard
          label="Total Hours"
          value={durationLabel(rows.reduce((acc, r) => acc + r.total_hours, 0))}
          icon={<Timer className="size-4" />}
        />
      </div>

      <Card className="mt-6">
        <CardHeader>
          <CardTitle className="text-sm">Summary</CardTitle>
        </CardHeader>
        <CardContent className="p-0">
          {summary.isLoading ? (
            <div className="p-5">
              <Spinner />
            </div>
          ) : rows.length === 0 ? (
            <div className="p-5">
              <EmptyState title="No attendance data" description="No records exist for this batch yet." />
            </div>
          ) : (
            <Table>
              <THead>
                <TR>
                  <TH>Intern</TH>
                  <TH>Present</TH>
                  <TH>Late</TH>
                  <TH>Attendance Rate</TH>
                  <TH>Total Hours</TH>
                </TR>
              </THead>
              <TBody>
                {rows.map((r) => (
                  <TR key={r.intern_id}>
                    <TD className="font-medium">{r.intern_name}</TD>
                    <TD>{r.present_days}</TD>
                    <TD>{r.late_days}</TD>
                    <TD>
                      <Badge variant={r.attendance_rate >= 90 ? 'success' : r.attendance_rate >= 75 ? 'warning' : 'destructive'}>
                        {r.attendance_rate}%
                      </Badge>
                    </TD>
                    <TD className="text-muted-foreground">{durationLabel(r.total_hours)}</TD>
                  </TR>
                ))}
              </TBody>
            </Table>
          )}
        </CardContent>
      </Card>

      <Card className="mt-6">
        <CardHeader>
          <div className="flex items-center justify-between gap-3">
            <CardTitle className="text-sm">All Records</CardTitle>
            <Select className="w-56" value={internFilter} onChange={(e) => setInternFilter(e.target.value)}>
              <option value="">All interns</option>
              {rows.map((r) => (
                <option key={r.intern_id} value={r.intern_id}>
                  {r.intern_name}
                </option>
              ))}
            </Select>
          </div>
        </CardHeader>
        <CardContent className="p-0">
          {records.isLoading ? (
            <div className="p-5">
              <Spinner />
            </div>
          ) : records.data?.items.length === 0 ? (
            <div className="p-5">
              <EmptyState title="No records" description="No attendance records match this filter." />
            </div>
          ) : (
            <Table>
              <THead>
                <TR>
                  <TH>Intern</TH>
                  <TH>Date</TH>
                  <TH>Check-in</TH>
                  <TH>Check-out</TH>
                  <TH>Hours</TH>
                  <TH>Status</TH>
                </TR>
              </THead>
              <TBody>
                {(records.data?.items ?? []).map((r) => (
                  <TR key={r.id}>
                    <TD className="font-medium">{r.intern_name ?? `Intern #${r.intern_id}`}</TD>
                    <TD>{formatDate(r.date)}</TD>
                    <TD className="text-muted-foreground">{timeOf(r.check_in)}</TD>
                    <TD className="text-muted-foreground">{timeOf(r.check_out)}</TD>
                    <TD className="text-muted-foreground">{durationLabel(r.worked_hours)}</TD>
                    <TD>
                      <Badge variant={lateVariant[r.late_status ?? ''] ?? 'muted'}>
                        {r.late_status ? titleCase(r.late_status) : '—'}
                      </Badge>
                    </TD>
                  </TR>
                ))}
              </TBody>
            </Table>
          )}
        </CardContent>
      </Card>
    </div>
  )
}