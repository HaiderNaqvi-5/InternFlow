import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { Download, FileText } from 'lucide-react'
import { useState } from 'react'
import { toast } from 'sonner'

import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { EmptyState } from '@/components/ui/empty-state'
import { Label } from '@/components/ui/label'
import { PageHeader } from '@/components/ui/page-header'
import { Skeleton } from '@/components/ui/skeleton'
import { Table, TBody, TD, TH, THead, TR } from '@/components/ui/table'
import { api, ApiError } from '@/lib/api'
import { formatDateTime } from '@/lib/format'
import type { PaginatedBatches, PaginatedUsers } from '@/lib/types'

interface ReportMeta {
  report_id: number
  filename: string
  generated_at: string
}

interface ReportRecord {
  id: number
  filename: string
  generated_at: string
}

export default function ReportsPage() {
  const qc = useQueryClient()
  const [attBatch, setAttBatch] = useState('')
  const [evalBatch, setEvalBatch] = useState('')
  const [certIntern, setCertIntern] = useState('')
  const [certBatch, setCertBatch] = useState('')

  const reports = useQuery({
    queryKey: ['reports'],
    queryFn: () => api.get<ReportRecord[]>('/api/v1/reports'),
  })
  const batches = useQuery({
    queryKey: ['batches'],
    queryFn: () => api.get<PaginatedBatches>('/api/v1/batches?page_size=200'),
  })
  const interns = useQuery({
    queryKey: ['users', 'interns'],
    queryFn: () => api.get<PaginatedUsers>('/api/v1/users?role=intern&page_size=300'),
  })

  const download = (id: number) => {
    api.download(`/api/v1/reports/${id}/download`).catch((e) =>
      toast.error(e instanceof ApiError ? e.detail : 'Download failed'),
    )
  }

  const onGenerated = () => {
    qc.invalidateQueries({ queryKey: ['reports'] })
  }

  const attendance = useMutation({
    mutationFn: () => {
      return api.download(`/api/v1/reports/exports/attendance?batch_id=${attBatch}`)
    },
    onSuccess: () => {
      toast.success('Attendance report downloaded')
    },
    onError: (e) => toast.error(e instanceof ApiError ? e.detail : 'Failed to generate report'),
  })
  const evaluation = useMutation({
    mutationFn: () => {
      return api.download(`/api/v1/reports/exports/evaluations?batch_id=${evalBatch}`)
    },
    onSuccess: () => {
      toast.success('Evaluation report downloaded')
    },
    onError: (e) => toast.error(e instanceof ApiError ? e.detail : 'Failed to generate report'),
  })
  const internship = useMutation({
    mutationFn: () => api.post<ReportMeta>(`/api/v1/reports/internship-report/${certIntern}/${certBatch}`),
    onSuccess: (r) => {
      toast.success('Internship report generated')
      onGenerated()
      api.download(`/api/v1/reports/${r.report_id}/download`).catch(() => undefined)
    },
    onError: (e) => toast.error(e instanceof ApiError ? e.detail : 'Failed to generate report'),
  })

  return (
    <div>
      <PageHeader title="Reports" description="Generate and download HR reports" />

      <div className="grid gap-6 md:grid-cols-2 lg:grid-cols-3">
        <Card>
          <CardHeader>
            <CardTitle>Attendance Report</CardTitle>
            <CardDescription>Attendance records for a batch</CardDescription>
          </CardHeader>
          <CardContent className="space-y-4">
            <div>
              <Label>Batch</Label>
              <select
                className="h-9 w-full rounded-lg border border-input bg-transparent px-3 text-sm"
                value={attBatch}
                onChange={(e) => setAttBatch(e.target.value)}
              >
                <option value="">Select batch</option>
                {(batches.data?.items ?? []).map((b) => (
                  <option key={b.id} value={b.id}>
                    {b.name}
                  </option>
                ))}
              </select>
            </div>
            <Button
              className="w-full"
              disabled={!attBatch}
              loading={attendance.isPending}
              onClick={() => attendance.mutate()}
            >
              <FileText className="size-4" /> Generate
            </Button>
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle>Evaluation Report</CardTitle>
            <CardDescription>Evaluations and scores for a batch</CardDescription>
          </CardHeader>
          <CardContent className="space-y-4">
            <div>
              <Label>Batch</Label>
              <select
                className="h-9 w-full rounded-lg border border-input bg-transparent px-3 text-sm"
                value={evalBatch}
                onChange={(e) => setEvalBatch(e.target.value)}
              >
                <option value="">Select batch</option>
                {(batches.data?.items ?? []).map((b) => (
                  <option key={b.id} value={b.id}>
                    {b.name}
                  </option>
                ))}
              </select>
            </div>
            <Button
              className="w-full"
              disabled={!evalBatch}
              loading={evaluation.isPending}
              onClick={() => evaluation.mutate()}
            >
              <FileText className="size-4" /> Generate
            </Button>
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle>Internship Report</CardTitle>
            <CardDescription>Completion PDF for an intern in a batch</CardDescription>
          </CardHeader>
          <CardContent className="space-y-4">
            <div>
              <Label>Intern</Label>
              <select
                className="h-9 w-full rounded-lg border border-input bg-transparent px-3 text-sm"
                value={certIntern}
                onChange={(e) => setCertIntern(e.target.value)}
              >
                <option value="">Select intern</option>
                {(interns.data?.items ?? []).map((u) => (
                  <option key={u.id} value={u.id}>
                    {u.full_name}
                  </option>
                ))}
              </select>
            </div>
            <div>
              <Label>Batch</Label>
              <select
                className="h-9 w-full rounded-lg border border-input bg-transparent px-3 text-sm"
                value={certBatch}
                onChange={(e) => setCertBatch(e.target.value)}
              >
                <option value="">Select batch</option>
                {(batches.data?.items ?? []).map((b) => (
                  <option key={b.id} value={b.id}>
                    {b.name}
                  </option>
                ))}
              </select>
            </div>
            <Button
              className="w-full"
              disabled={!certIntern || !certBatch}
              loading={internship.isPending}
              onClick={() => internship.mutate()}
            >
              <FileText className="size-4" /> Generate
            </Button>
          </CardContent>
        </Card>
      </div>

      <Card className="mt-6">
        <CardHeader>
          <CardTitle>Generated Reports</CardTitle>
          <CardDescription>Previously generated reports</CardDescription>
        </CardHeader>
        <CardContent className="p-0">
          <Table>
            <THead>
              <TR>
                <TH>Filename</TH>
                <TH>Created</TH>
                <TH className="text-right">Download</TH>
              </TR>
            </THead>
            <TBody>
              {reports.isLoading ? (
                <TR>
                  <TD>
                    <Skeleton className="h-8" />
                  </TD>
                </TR>
              ) : !reports.data || reports.data.length === 0 ? (
                <TR>
                  <TD>
                    <EmptyState title="No reports" description="Generated reports will appear here." />
                  </TD>
                </TR>
              ) : (
                reports.data.map((r) => (
                  <TR key={r.id}>
                    <TD className="font-medium">{r.filename}</TD>
                    <TD className="text-muted-foreground">{formatDateTime(r.generated_at)}</TD>
                    <TD className="text-right">
                      <Button variant="outline" size="sm" onClick={() => download(r.id)}>
                        <Download className="size-4" /> Download
                      </Button>
                    </TD>
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
