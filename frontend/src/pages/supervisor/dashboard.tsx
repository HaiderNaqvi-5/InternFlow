import { useQuery } from '@tanstack/react-query'
import { ArrowRight, ClipboardCheck, Clock3, Percent, Users } from 'lucide-react'
import { Link } from 'react-router-dom'

import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { EmptyState } from '@/components/ui/empty-state'
import { PageHeader } from '@/components/ui/page-header'
import { Skeleton } from '@/components/ui/skeleton'
import { Spinner } from '@/components/ui/spinner'
import { StatCard } from '@/components/ui/stat-card'
import { Table, TBody, TD, TH, THead, TR } from '@/components/ui/table'
import { api } from '@/lib/api'
import { relativeTime } from '@/lib/format'
import type { PaginatedSubmissions, SupervisorAnalytics } from '@/lib/types'

export default function SupervisorDashboard() {
  const analytics = useQuery({
    queryKey: ['analytics', 'supervisor'],
    queryFn: () => api.get<SupervisorAnalytics>('/api/v1/analytics/supervisor'),
  })
  const pending = useQuery({
    queryKey: ['submissions', 'pending', 'dashboard'],
    queryFn: () => api.get<PaginatedSubmissions>('/api/v1/submissions?status=pending&page_size=5'),
  })

  const d = analytics.data
  const categories = d?.tasks_by_category ?? {}
  const maxCat = Math.max(1, ...Object.values(categories))

  return (
    <div>
      <PageHeader
        title="Supervisor Dashboard"
        description="Overview of your batch activity and pending work"
      />

      {analytics.isLoading ? (
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
          {Array.from({ length: 4 }).map((_, i) => (
            <Skeleton key={i} className="h-28 rounded-xl" />
          ))}
        </div>
      ) : (
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
          <StatCard
            label="Pending Reviews"
            value={d?.pending_reviews ?? 0}
            icon={<ClipboardCheck className="size-4" />}
            hint={<Link to="/reviews" className="text-primary hover:underline">Open inbox →</Link>}
            tone={d && d.pending_reviews > 0 ? 'warning' : 'default'}
          />
          <StatCard label="Active Interns" value={d?.interns_active ?? 0} icon={<Users className="size-4" />} />
          <StatCard
            label="Overdue Tasks"
            value={d?.overdue_tasks ?? 0}
            icon={<Clock3 className="size-4" />}
            tone={d && d.overdue_tasks > 0 ? 'destructive' : 'default'}
          />
          <StatCard
            label="Batch Attendance Rate"
            value={d?.batch_attendance_rate != null ? `${d.batch_attendance_rate}%` : '—'}
            icon={<Percent className="size-4" />}
            hint={`${d?.tasks_total ?? 0} total tasks`}
          />
        </div>
      )}

      <div className="mt-6 grid gap-6 lg:grid-cols-2">
        <Card>
          <CardHeader>
            <CardTitle>Tasks by Category</CardTitle>
            <CardDescription>Distribution of this batch's tasks</CardDescription>
          </CardHeader>
          <CardContent className="space-y-3">
            {analytics.isLoading ? (
              <Spinner />
            ) : Object.keys(categories).length === 0 ? (
              <p className="text-sm text-muted-foreground">No task data yet.</p>
            ) : (
              Object.entries(categories).map(([cat, count]) => (
                <div key={cat}>
                  <div className="mb-1 flex items-center justify-between text-sm">
                    <span className="font-medium">{cat}</span>
                    <span className="text-muted-foreground">{count}</span>
                  </div>
                  <div className="h-2 rounded-full bg-muted">
                    <div className="h-2 rounded-full bg-primary" style={{ width: `${(count / maxCat) * 100}%` }} />
                  </div>
                </div>
              ))
            )}
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle>Recent Pending Submissions</CardTitle>
            <CardDescription>Latest submissions awaiting your review</CardDescription>
          </CardHeader>
          <CardContent>
            {pending.isLoading ? (
              <Spinner />
            ) : !pending.data || pending.data.items.length === 0 ? (
              <EmptyState title="Nothing pending" description="All submissions have been reviewed." />
            ) : (
              <ul className="divide-y divide-border">
                {pending.data.items.map((s) => (
                  <li key={s.id} className="flex items-center justify-between gap-3 py-3">
                    <div className="min-w-0">
                      <p className="truncate text-sm font-medium">{s.task_title ?? `Task #${s.task_id}`}</p>
                      <p className="truncate text-xs text-muted-foreground">
                        {s.intern_name ?? `Intern #${s.intern_id}`} · {relativeTime(s.submitted_at)}
                      </p>
                    </div>
                    {s.is_late && <Badge variant="destructive">Late</Badge>}
                  </li>
                ))}
                <li className="pt-3">
                  <Link to="/reviews">
                    <Button variant="outline" size="sm">
                      Review all <ArrowRight className="size-4" />
                    </Button>
                  </Link>
                </li>
              </ul>
            )}
          </CardContent>
        </Card>
      </div>

      <Card className="mt-6">
        <CardHeader>
          <CardTitle>Intern Performance</CardTitle>
          <CardDescription>Completion rate and average score per intern</CardDescription>
        </CardHeader>
        <CardContent className="p-0">
          <Table>
            <THead>
              <TR>
                <TH>Intern</TH>
                <TH>Completion Rate</TH>
                <TH>Average Score</TH>
              </TR>
            </THead>
            <TBody>
              {analytics.isLoading ? (
                <TR>
                  <TD>
                    <Spinner />
                  </TD>
                </TR>
              ) : !d || d.per_intern.length === 0 ? (
                <TR>
                  <TD>No intern data.</TD>
                </TR>
              ) : (
                d.per_intern.map((row) => (
                  <TR key={row.intern_id}>
                    <TD className="font-medium">{row.intern_name}</TD>
                    <TD>{row.completion_rate}%</TD>
                    <TD>{row.average_score != null ? row.average_score : '—'}</TD>
                  </TR>
                ))
              )}
            </TBody>
          </Table>
        </CardContent>
      </Card>
    </div>
  )
}
