import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { ExternalLink, RotateCcw } from 'lucide-react'
import { useState } from 'react'
import { toast } from 'sonner'

import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Dialog } from '@/components/ui/dialog'
import { EmptyState } from '@/components/ui/empty-state'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { PageHeader } from '@/components/ui/page-header'
import { Spinner } from '@/components/ui/spinner'
import { Textarea } from '@/components/ui/textarea'
import { Table, TBody, TD, TH, THead, TR } from '@/components/ui/table'
import { api, ApiError } from '@/lib/api'
import { durationLabel, relativeTime, titleCase } from '@/lib/format'
import type { PaginatedSubmissions, Submission, SubmissionDetail, SubmissionStatus } from '@/lib/types'

const statusVariant: Record<SubmissionStatus, 'warning' | 'info' | 'success' | 'destructive'> = {
  pending: 'warning',
  changes_requested: 'info',
  approved: 'success',
  rejected: 'destructive',
}

const emptyForm = { decision: 'approved' as 'approved' | 'changes_requested' | 'rejected', score: '', feedback: '' }

export default function ReviewsPage() {
  const qc = useQueryClient()
  const [status, setStatus] = useState('')
  const [selected, setSelected] = useState<Submission | null>(null)
  const [form, setForm] = useState(emptyForm)

  const submissions = useQuery({
    queryKey: ['submissions', status],
    queryFn: () => api.get<PaginatedSubmissions>(`/api/v1/submissions?page_size=50${status ? `&status=${status}` : ''}`),
  })
  const detail = useQuery({
    queryKey: ['submission', selected?.id],
    queryFn: () => api.get<SubmissionDetail>(`/api/v1/submissions/${selected!.id}`),
    enabled: !!selected,
  })

  const invalidate = () => {
    qc.invalidateQueries({ queryKey: ['submissions'] })
    qc.invalidateQueries({ queryKey: ['submission', selected?.id] })
  }

  const submitReview = useMutation({
    mutationFn: () =>
      api.post(`/api/v1/submissions/${selected!.id}/review`, {
        decision: form.decision,
        score: form.score === '' ? null : Number(form.score),
        feedback: form.feedback || null,
      }),
    onSuccess: () => {
      toast.success('Review submitted')
      setForm(emptyForm)
      invalidate()
    },
    onError: (e) => toast.error(e instanceof ApiError ? e.detail : 'Failed to submit review'),
  })

  const alreadyReviewed = (detail.data?.reviews ?? []).length > 0

  return (
    <div>
      <PageHeader
        title="Submission Reviews"
        description="Review intern submissions and provide feedback"
        actions={
          <div className="flex items-center gap-2">
            <select
              className="h-9 w-44 rounded-lg border border-input bg-transparent px-3 text-sm"
              value={status}
              onChange={(e) => setStatus(e.target.value)}
            >
              <option value="">All statuses</option>
              {(Object.keys(statusVariant) as SubmissionStatus[]).map((s) => (
                <option key={s} value={s}>
                  {titleCase(s)}
                </option>
              ))}
            </select>
            <Button
              variant="outline"
              size="icon"
              onClick={() => qc.invalidateQueries({ queryKey: ['submissions'] })}
              title="Refresh"
            >
              <RotateCcw className="size-4" />
            </Button>
          </div>
        }
      />

      {submissions.isLoading ? (
        <Spinner />
      ) : !submissions.data || submissions.data.items.length === 0 ? (
        <EmptyState title="No submissions" description="No submissions match this filter." />
      ) : (
        <div className="overflow-hidden rounded-xl border border-border">
          <Table>
            <THead>
              <TR>
                <TH>Intern</TH>
                <TH>Task</TH>
                <TH>Version</TH>
                <TH>Submitted</TH>
                <TH>Late</TH>
                <TH>Status</TH>
                <TH className="text-right">Action</TH>
              </TR>
            </THead>
            <TBody>
              {submissions.data.items.map((s) => (
                <TR key={s.id} onClick={() => setSelected(s)}>
                  <TD className="font-medium">{s.intern_name ?? `Intern #${s.intern_id}`}</TD>
                  <TD>{s.task_title ?? `Task #${s.task_id}`}</TD>
                  <TD>v{s.version}</TD>
                  <TD className="text-muted-foreground">{relativeTime(s.submitted_at)}</TD>
                  <TD>{s.is_late ? <Badge variant="destructive">Late</Badge> : <Badge variant="muted">On time</Badge>}</TD>
                  <TD>
                    <Badge variant={statusVariant[s.status]}>{titleCase(s.status)}</Badge>
                  </TD>
                  <TD className="text-right">
                    <Button variant="outline" size="sm" onClick={() => setSelected(s)}>
                      Review
                    </Button>
                  </TD>
                </TR>
              ))}
            </TBody>
          </Table>
        </div>
      )}

      <Dialog
        open={!!selected}
        onClose={() => {
          setSelected(null)
          setForm(emptyForm)
        }}
        title="Review Submission"
        description={selected?.task_title ?? undefined}
        wide
        footer={
          !alreadyReviewed ? (
            <>
              <Button variant="outline" onClick={() => setSelected(null)}>
                Close
              </Button>
              <Button onClick={() => submitReview.mutate()} loading={submitReview.isPending}>
                Submit review
              </Button>
            </>
          ) : undefined
        }
      >
        {detail.isLoading ? (
          <Spinner />
        ) : !detail.data ? (
          <p className="text-sm text-muted-foreground">Loading…</p>
        ) : (
          <div className="space-y-5">
            <dl className="grid gap-3 text-sm sm:grid-cols-2">
              <div>
                <dt className="text-muted-foreground">Intern</dt>
                <dd className="font-medium">{detail.data.intern_name ?? `Intern #${detail.data.intern_id}`}</dd>
              </div>
              <div>
                <dt className="text-muted-foreground">Submitted</dt>
                <dd className="font-medium">{relativeTime(detail.data.submitted_at)}</dd>
              </div>
              <div>
                <dt className="text-muted-foreground">Version</dt>
                <dd className="font-medium">v{detail.data.version}</dd>
              </div>
              <div>
                <dt className="text-muted-foreground">Effort</dt>
                <dd className="font-medium">{durationLabel(detail.data.actual_effort_hours)}</dd>
              </div>
            </dl>

            <div className="space-y-1 text-sm">
              {detail.data.github_url && (
                <a href={detail.data.github_url} target="_blank" rel="noreferrer" className="inline-flex items-center gap-1 text-primary hover:underline">
                  <ExternalLink className="size-3.5" /> GitHub URL
                </a>
              )}
              {detail.data.live_url && (
                <a href={detail.data.live_url} target="_blank" rel="noreferrer" className="inline-flex items-center gap-1 text-primary hover:underline">
                  <ExternalLink className="size-3.5" /> Live URL
                </a>
              )}
              {detail.data.filename && <p className="text-muted-foreground">File: {detail.data.filename}</p>}
              {detail.data.notes && (
                <div className="rounded-lg bg-muted p-3">
                  <p className="mb-1 text-xs font-medium uppercase text-muted-foreground">Intern notes</p>
                  <p className="whitespace-pre-wrap">{detail.data.notes}</p>
                </div>
              )}
            </div>

            {alreadyReviewed ? (
              <div className="space-y-3">
                <h4 className="text-sm font-semibold">Review history</h4>
                {detail.data.reviews.map((r) => (
                  <div key={r.id} className="rounded-lg border border-border p-3 text-sm">
                    <div className="flex items-center justify-between">
                      <Badge variant={statusVariant[r.decision]}>{titleCase(r.decision)}</Badge>
                      <span className="text-xs text-muted-foreground">
                        {r.supervisor_name ?? 'Supervisor'} · {relativeTime(r.reviewed_at)}
                      </span>
                    </div>
                    {r.score != null && <p className="mt-2 text-xs text-muted-foreground">Score: {r.score}</p>}
                    {r.feedback && <p className="mt-1 whitespace-pre-wrap">{r.feedback}</p>}
                  </div>
                ))}
              </div>
            ) : (
              <div className="space-y-4 rounded-lg border border-border p-4">
                <h4 className="text-sm font-semibold">Submit review</h4>
                <div className="grid gap-3 sm:grid-cols-2">
                  <div>
                    <Label>Decision</Label>
                    <select
                      className="h-9 w-full rounded-lg border border-input bg-transparent px-3 text-sm"
                      value={form.decision}
                      onChange={(e) => setForm((f) => ({ ...f, decision: e.target.value as typeof f.decision }))}
                    >
                      <option value="approved">Approved</option>
                      <option value="changes_requested">Changes requested</option>
                      <option value="rejected">Rejected</option>
                    </select>
                  </div>
                  <div>
                    <Label>Score (optional)</Label>
                    <Input
                      type="number"
                      min={0}
                      max={100}
                      value={form.score}
                      onChange={(e) => setForm((f) => ({ ...f, score: e.target.value }))}
                    />
                  </div>
                </div>
                <div>
                  <Label>Feedback</Label>
                  <Textarea
                    rows={4}
                    value={form.feedback}
                    onChange={(e) => setForm((f) => ({ ...f, feedback: e.target.value }))}
                    placeholder="Constructive feedback for the intern…"
                  />
                </div>
              </div>
            )}
          </div>
        )}
      </Dialog>
    </div>
  )
}
