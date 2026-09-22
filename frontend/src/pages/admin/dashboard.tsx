import { useQuery } from '@tanstack/react-query'
import { Award, Percent, TrendingUp, Users, Layers } from 'lucide-react'
import { Link } from 'react-router-dom'

import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { EmptyState } from '@/components/ui/empty-state'
import { PageHeader } from '@/components/ui/page-header'
import { Skeleton } from '@/components/ui/skeleton'
import { Spinner } from '@/components/ui/spinner'
import { StatCard } from '@/components/ui/stat-card'
import { Table, TBody, TD, TH, THead, TR } from '@/components/ui/table'
import { api } from '@/lib/api'
import type { HrAnalytics } from '@/lib/types'

export default function AdminDashboard() {
  const hr = useQuery({
    queryKey: ['analytics', 'hr'],
    queryFn: () => api.get<HrAnalytics>('/api/v1/analytics/hr'),
  })

  const d = hr.data
  const completion = d?.completion_by_status ?? {}
  const maxStatus = Math.max(1, ...Object.values(completion))

  return (
    <div>
      <PageHeader title="Admin Dashboard" description="High-level HR overview across all batches" />

      {hr.isLoading ? (
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
          {Array.from({ length: 4 }).map((_, i) => (
            <Skeleton key={i} className="h-28 rounded-xl" />
          ))}
        </div>
      ) : (
        <>
          <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
            <StatCard label="Active Batches" value={d?.active_batches ?? 0} icon={<Layers className="size-4" />} />
            <StatCard label="Total Interns" value={d?.total_interns ?? 0} icon={<Users className="size-4" />} hint={`${d?.active_interns ?? 0} active`} />
            <StatCard
              label="Avg Completion Rate"
              value={d?.avg_completion_rate != null ? `${d.avg_completion_rate}%` : '—'}
              icon={<Percent className="size-4" />}
            />
            <StatCard
              label="Avg Score"
              value={d?.avg_score != null ? d.avg_score : '—'}
              icon={<TrendingUp className="size-4" />}
              hint={d?.attendance_rate != null ? `${d.attendance_rate}% attendance` : undefined}
            />
          </div>

          <div className="mt-6 grid gap-6 lg:grid-cols-2">
            <Card>
              <CardHeader>
                <CardTitle>Interns by Batch</CardTitle>
                <CardDescription>Active intern distribution</CardDescription>
              </CardHeader>
              <CardContent className="p-0">
                <Table>
                  <THead>
                    <TR>
                      <TH>Batch</TH>
                      <TH>Interns</TH>
                    </TR>
                  </THead>
                  <TBody>
                    {hr.isLoading ? (
                      <TR>
                        <TD>
                          <Spinner />
                        </TD>
                      </TR>
                    ) : !d || d.interns_by_batch.length === 0 ? (
                      <TR>
                        <TD>No batch data.</TD>
                      </TR>
                    ) : (
                      d.interns_by_batch.map((row) => (
                        <TR key={row.batch_id}>
                          <TD className="font-medium">{row.batch_name}</TD>
                          <TD>{row.count}</TD>
                        </TR>
                      ))
                    )}
                  </TBody>
                </Table>
              </CardContent>
            </Card>

            <Card>
              <CardHeader>
                <CardTitle>Completion by Status</CardTitle>
                <CardDescription>Task completion distribution</CardDescription>
              </CardHeader>
              <CardContent className="space-y-3">
                {hr.isLoading ? (
                  <Spinner />
                ) : Object.keys(completion).length === 0 ? (
                  <p className="text-sm text-muted-foreground">No task data yet.</p>
                ) : (
                  Object.entries(completion).map(([status, count]) => (
                    <div key={status}>
                      <div className="mb-1 flex items-center justify-between text-sm">
                        <span className="capitalize">{status.replace('_', ' ')}</span>
                        <span className="text-muted-foreground">{count}</span>
                      </div>
                      <div className="h-2 rounded-full bg-muted">
                        <div
                          className="h-2 rounded-full bg-primary"
                          style={{ width: `${(count / maxStatus) * 100}%` }}
                        />
                      </div>
                    </div>
                  ))
                )}
              </CardContent>
            </Card>
          </div>

          <Card className="mt-6">
            <CardHeader className="flex-row items-start justify-between gap-2">
              <div>
                <CardTitle>Up for Completion</CardTitle>
                <CardDescription>Interns nearing completion who may be ready for certification</CardDescription>
              </div>
              <Link to="/certificates">
                <Button variant="outline" size="sm">
                  <Award className="size-4" /> Issue certificates
                </Button>
              </Link>
            </CardHeader>
            <CardContent className="p-0">
              <Table>
                <THead>
                  <TR>
                    <TH>Intern</TH>
                    <TH>Batch</TH>
                  </TR>
                </THead>
                <TBody>
                  {hr.isLoading ? (
                    <TR>
                      <TD>
                        <Spinner />
                      </TD>
                    </TR>
                  ) : !d?.up_for_completion || d.up_for_completion.length === 0 ? (
                    <TR>
                      <TD>
                        <EmptyState title="No interns up for completion" description="Nothing to certify right now." />
                      </TD>
                    </TR>
                  ) : (
                    d.up_for_completion.map((u) => (
                      <TR key={u.intern_id}>
                        <TD className="font-medium">{u.intern_name}</TD>
                        <TD>{u.batch_name ?? `Batch #${u.batch_id}`}</TD>
                      </TR>
                    ))
                  )}
                </TBody>
              </Table>
            </CardContent>
          </Card>
        </>
      )}
    </div>
  )
}