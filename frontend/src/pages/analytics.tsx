import { useQuery } from '@tanstack/react-query'
import { BarChart3, ClipboardCheck, Clock3, Percent, Users } from 'lucide-react'
import { Link } from 'react-router-dom'

import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { PageHeader } from '@/components/ui/page-header'
import { Skeleton } from '@/components/ui/skeleton'
import { Spinner } from '@/components/ui/spinner'
import { StatCard } from '@/components/ui/stat-card'
import { Table, TBody, TD, TH, THead, TR } from '@/components/ui/table'
import { api } from '@/lib/api'
import type { SupervisorAnalytics } from '@/lib/types'

export default function AnalyticsPage() {
  const analytics = useQuery({
    queryKey: ['analytics', 'supervisor'],
    queryFn: () => api.get<SupervisorAnalytics>('/api/v1/analytics/supervisor'),
  })

  const d = analytics.data
  const categories = d?.tasks_by_category ?? {}
  const maxCat = Math.max(1, ...Object.values(categories))

  return (
    <div>
      <PageHeader title="Analytics" description="Detailed performance metrics for your internships" />

      {analytics.isLoading ? (
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
          {Array.from({ length: 4 }).map((_, i) => (
            <Skeleton key={i} className="h-28 rounded-xl" />
          ))}
        </div>
      ) : (
        <>
          <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
            <StatCard label="Total Tasks" value={d?.tasks_total ?? 0} icon={<BarChart3 className="size-4" />} />
            <StatCard label="Active Interns" value={d?.interns_active ?? 0} icon={<Users className="size-4" />} />
            <StatCard
              label="Overdue Tasks"
              value={d?.overdue_tasks ?? 0}
              icon={<Clock3 className="size-4" />}
              tone={d && d.overdue_tasks > 0 ? 'destructive' : 'default'}
            />
            <StatCard
              label="Attendance Rate"
              value={d?.batch_attendance_rate != null ? `${d.batch_attendance_rate}%` : '—'}
              icon={<Percent className="size-4" />}
            />
          </div>

          <Card className="mt-6">
            <CardHeader>
              <CardTitle>Tasks by Category</CardTitle>
              <CardDescription>Distribution of tasks across categories</CardDescription>
            </CardHeader>
            <CardContent className="space-y-3">
              {Object.keys(categories).length === 0 ? (
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

          <Card className="mt-6">
            <CardHeader>
              <CardTitle>Per-Intern Performance</CardTitle>
              <CardDescription>Completion rate and average score for each intern</CardDescription>
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

          {!!d?.pending_reviews && (
            <Card className="mt-6">
              <CardHeader>
                <CardTitle className="flex items-center gap-2">
                  <ClipboardCheck className="size-4 text-warning" />
                  {d.pending_reviews} submission{d.pending_reviews === 1 ? '' : 's'} awaiting review
                </CardTitle>
              </CardHeader>
              <CardContent>
                <Link to="/reviews" className="text-sm text-primary hover:underline">
                  Open review inbox →
                </Link>
              </CardContent>
            </Card>
          )}
        </>
      )}
    </div>
  )
}
