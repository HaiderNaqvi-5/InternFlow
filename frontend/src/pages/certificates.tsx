import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { Award, Download } from 'lucide-react'
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
import { formatDate } from '@/lib/format'
import type { CertificatesResponse, PaginatedBatches, PaginatedUsers } from '@/lib/types'

export default function CertificatesPage() {
  const qc = useQueryClient()
  const [issuerType, setIssuerType] = useState<'completion' | 'recommendation'>('completion')
  const [intern, setIntern] = useState('')
  const [batch, setBatch] = useState('')

  const certs = useQuery({
    queryKey: ['certificates'],
    queryFn: () => api.get<CertificatesResponse>('/api/v1/certificates'),
  })
  const batches = useQuery({
    queryKey: ['batches'],
    queryFn: () => api.get<PaginatedBatches>('/api/v1/batches?page_size=200'),
  })
  const interns = useQuery({
    queryKey: ['users', 'interns'],
    queryFn: () => api.get<PaginatedUsers>('/api/v1/users?role=intern&page_size=300'),
  })

  const issue = useMutation({
    mutationFn: () => {
      const base =
        issuerType === 'completion'
          ? `/api/v1/completions?intern_id=${intern}&batch_id=${batch}`
          : `/api/v1/completions/recommendation?intern_id=${intern}&batch_id=${batch}`
      return api.post(base)
    },
    onSuccess: () => {
      toast.success(issuerType === 'completion' ? 'Completion processed' : 'Recommendation submitted')
      setIntern('')
      setBatch('')
      qc.invalidateQueries({ queryKey: ['certificates'] })
      qc.invalidateQueries({ queryKey: ['reports'] })
    },
    onError: (e) => toast.error(e instanceof ApiError ? e.detail : 'Issuance failed'),
  })

  const internName = (id: number) => interns.data?.items.find((u) => u.id === id)?.full_name ?? `Intern #${id}`
  const batchName = (id: number | null) =>
    id == null ? '—' : batches.data?.items.find((b) => b.id === id)?.name ?? `Batch #${id}`

  return (
    <div>
      <PageHeader
        title="Certificates"
        description="Issue internship completion certificates"
      />

      <Card>
        <CardHeader>
          <CardTitle>Issue Certificate</CardTitle>
          <CardDescription>Complete an intern's outcome and generate their certificate</CardDescription>
        </CardHeader>
        <CardContent>
          <div className="grid gap-4 md:grid-cols-2">
            <div>
              <Label>Issue type</Label>
              <select
                className="h-9 w-full rounded-lg border border-input bg-transparent px-3 text-sm"
                value={issuerType}
                onChange={(e) => setIssuerType(e.target.value as typeof issuerType)}
              >
                <option value="completion">Completion</option>
                <option value="recommendation">Supervisor recommendation</option>
              </select>
            </div>
            <div>
              <Label>Batch</Label>
              <select
                className="h-9 w-full rounded-lg border border-input bg-transparent px-3 text-sm"
                value={batch}
                onChange={(e) => setBatch(e.target.value)}
              >
                <option value="">Select batch</option>
                {(batches.data?.items ?? []).map((b) => (
                  <option key={b.id} value={b.id}>
                    {b.name}
                  </option>
                ))}
              </select>
            </div>
            <div className="md:col-span-2">
              <Label>Intern</Label>
              <select
                className="h-9 w-full rounded-lg border border-input bg-transparent px-3 text-sm"
                value={intern}
                onChange={(e) => setIntern(e.target.value)}
              >
                <option value="">Select intern</option>
                {(interns.data?.items ?? []).map((u) => (
                  <option key={u.id} value={u.id}>
                    {u.full_name} — {u.email}
                  </option>
                ))}
              </select>
            </div>
            <div className="md:col-span-2">
              <Button disabled={!intern || !batch} loading={issue.isPending} onClick={() => issue.mutate()}>
                <Award className="size-4" /> {issuerType === 'completion' ? 'Issue certificate' : 'Submit recommendation'}
              </Button>
            </div>
          </div>
        </CardContent>
      </Card>

      <Card className="mt-6">
        <CardHeader>
          <CardTitle>Issued Certificates</CardTitle>
          <CardDescription>All previously issued certificates</CardDescription>
        </CardHeader>
        <CardContent className="p-0">
          <Table>
            <THead>
              <TR>
                <TH>Intern</TH>
                <TH>Batch</TH>
                <TH>Issued</TH>
                <TH className="text-right">Download</TH>
              </TR>
            </THead>
            <TBody>
              {certs.isLoading ? (
                <TR>
                  <TD>
                    <Skeleton className="h-8" />
                  </TD>
                </TR>
              ) : !certs.data || certs.data.items.length === 0 ? (
                <TR>
                  <TD>
                    <EmptyState title="No certificates" description="Issued certificates will appear here." />
                  </TD>
                </TR>
              ) : (
                certs.data.items.map((c) => (
                  <TR key={c.id}>
                    <TD className="font-medium">{internName(c.intern_id)}</TD>
                    <TD className="text-muted-foreground">{batchName(c.batch_id)}</TD>
                    <TD className="text-muted-foreground">{formatDate(c.issued_at)}</TD>
                    <TD className="text-right">
                      <Button variant="outline" size="sm" onClick={() => window.open(`/api/v1/certificates/${c.id}/download`, '_blank')}>
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
