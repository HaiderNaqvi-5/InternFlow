import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import {
  CalendarClock,
  Download,
  ExternalLink,
  MoreHorizontal,
  Paperclip,
  Pencil,
  Pin,
  PinOff,
  Send,
  Trash2,
  Upload,
} from 'lucide-react'
import { useRef, useState } from 'react'
import { useParams } from 'react-router-dom'
import { toast } from 'sonner'

import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Dialog } from '@/components/ui/dialog'
import { DropdownItem, DropdownMenu } from '@/components/ui/dropdown'
import { EmptyState } from '@/components/ui/empty-state'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Select } from '@/components/ui/select'
import { Skeleton } from '@/components/ui/skeleton'
import { Spinner } from '@/components/ui/spinner'
import { Table, TBody, TD, TH, THead, TR } from '@/components/ui/table'
import { Textarea } from '@/components/ui/textarea'
import { useAuth } from '@/context/auth'
import { api, apiFetch, ApiError } from '@/lib/api'
import { formatDateTime, fromLocalInputValue, relativeTime, titleCase } from '@/lib/format'
import type {
  Review,
  ReviewDecision,
  Submission,
  SubmissionStatus,
  TaskComment,
  TaskDetail,
  TaskPriority,
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

const submissionVariant: Record<SubmissionStatus, BadgeVariant> = {
  pending: 'warning',
  changes_requested: 'info',
  approved: 'success',
  rejected: 'destructive',
}

const decisionVariant: Record<ReviewDecision, BadgeVariant> = {
  approved: 'success',
  changes_requested: 'info',
  rejected: 'destructive',
}

interface TaskSubmission extends Submission {
  reviews?: Review[]
}

interface SubPage {
  items: TaskSubmission[]
  total: number
  page: number
  page_size: number
}

interface ReviewForm {
  decision: ReviewDecision
  score: string
  feedback: string
}

const emptyReview: ReviewForm = { decision: 'approved', score: '', feedback: '' }

export default function TaskDetailPage() {
  const { taskId } = useParams()
  const id = Number(taskId)
  const { user } = useAuth()
  const isIntern = user?.role === 'intern'
  const isSupervisor = user?.role === 'supervisor' || user?.role === 'admin'
  const qc = useQueryClient()
  const attachRef = useRef<HTMLInputElement>(null)
  const subFileRef = useRef<HTMLInputElement>(null)

  const [commentDraft, setCommentDraft] = useState('')
  const [editingId, setEditingId] = useState<number | null>(null)
  const [editDraft, setEditDraft] = useState('')
  const [deleteId, setDeleteId] = useState<number | null>(null)
  const [subFile, setSubFile] = useState<File | null>(null)
  const [subForm, setSubForm] = useState({ github_url: '', live_url: '', notes: '', actual_effort_hours: '' })
  const [reviewTarget, setReviewTarget] = useState<TaskSubmission | null>(null)
  const [reviewForm, setReviewForm] = useState<ReviewForm>(emptyReview)
  const [extOpen, setExtOpen] = useState(false)
  const [extForm, setExtForm] = useState({ new_deadline: '', reason: '' })

  const base = (import.meta.env.VITE_API_URL as string | undefined) ?? ''

  const task = useQuery({
    queryKey: ['task', id],
    queryFn: () => api.get<TaskDetail>(`/api/v1/tasks/${id}`),
    enabled: !Number.isNaN(id),
  })

  const comments = useQuery({
    queryKey: ['taskComments', id],
    queryFn: () => api.get<TaskComment[]>(`/api/v1/tasks/${id}/comments`),
    enabled: !Number.isNaN(id),
  })

  const subs = useQuery({
    queryKey: ['taskSubmissions', id],
    queryFn: () => api.get<SubPage>(`/api/v1/submissions?task_id=${id}&page_size=50`),
    enabled: !Number.isNaN(id),
  })

  const invalidate = () => {
    qc.invalidateQueries({ queryKey: ['task', id] })
    qc.invalidateQueries({ queryKey: ['taskComments', id] })
    qc.invalidateQueries({ queryKey: ['taskSubmissions', id] })
  }

  const addComment = useMutation({
    mutationFn: (content: string) =>
      api.post(`/api/v1/tasks/${id}/comments`, { content, mentions: [] }),
    onSuccess: () => {
      setCommentDraft('')
      qc.invalidateQueries({ queryKey: ['taskComments', id] })
    },
    onError: (e) => toast.error(e instanceof ApiError ? e.detail : 'Failed to add comment'),
  })

  const editComment = useMutation({
    mutationFn: ({ cid, content }: { cid: number; content: string }) =>
      api.patch(`/api/v1/comments/${cid}`, { content }),
    onSuccess: () => {
      setEditingId(null)
      setEditDraft('')
      qc.invalidateQueries({ queryKey: ['taskComments', id] })
    },
    onError: (e) => toast.error(e instanceof ApiError ? e.detail : 'Failed to edit comment'),
  })

  const deleteComment = useMutation({
    mutationFn: (cid: number) => api.delete(`/api/v1/comments/${cid}`),
    onSuccess: () => {
      setDeleteId(null)
      qc.invalidateQueries({ queryKey: ['taskComments', id] })
    },
    onError: (e) => toast.error(e instanceof ApiError ? e.detail : 'Failed to delete comment'),
  })

  const pinComment = useMutation({
    mutationFn: ({ cid, pin }: { cid: number; pin: boolean }) =>
      api.post(`/api/v1/comments/${cid}/pin?pin=${pin}`),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['taskComments', id] }),
    onError: (e) => toast.error(e instanceof ApiError ? e.detail : 'Failed to update comment'),
  })

  const uploadAttachment = useMutation({
    mutationFn: (file: File) => api.upload(`/api/v1/tasks/${id}/attachments`, file),
    onSuccess: () => {
      toast.success('Attachment uploaded')
      qc.invalidateQueries({ queryKey: ['task', id] })
    },
    onError: (e) => toast.error(e instanceof ApiError ? e.detail : 'Upload failed'),
  })

  const submitWork = useMutation({
    mutationFn: async () => {
      const payload = {
        github_url: subForm.github_url || null,
        live_url: subForm.live_url || null,
        notes: subForm.notes || null,
        actual_effort_hours: subForm.actual_effort_hours ? Number(subForm.actual_effort_hours) : null,
      }
      if (subFile) {
        const fd = new FormData()
        fd.append('file', subFile)
        fd.append('github_url', subForm.github_url || '')
        fd.append('live_url', subForm.live_url || '')
        fd.append('notes', subForm.notes || '')
        if (subForm.actual_effort_hours) fd.append('actual_effort_hours', subForm.actual_effort_hours)
        return apiFetch(`/api/v1/submissions/${id}/file`, { method: 'POST', body: fd })
      }
      return api.post(`/api/v1/submissions/${id}`, payload)
    },
    onSuccess: () => {
      toast.success('Work submitted')
      setSubForm({ github_url: '', live_url: '', notes: '', actual_effort_hours: '' })
      setSubFile(null)
      if (subFileRef.current) subFileRef.current.value = ''
      invalidate()
    },
    onError: (e) => toast.error(e instanceof ApiError ? e.detail : 'Failed to submit work'),
  })

  const review = useMutation({
    mutationFn: () =>
      api.post(`/api/v1/submissions/${reviewTarget!.id}/review`, {
        decision: reviewForm.decision,
        score: Number(reviewForm.score),
        feedback: reviewForm.feedback || null,
      }),
    onSuccess: () => {
      toast.success('Review submitted')
      setReviewTarget(null)
      setReviewForm(emptyReview)
      invalidate()
    },
    onError: (e) => toast.error(e instanceof ApiError ? e.detail : 'Failed to submit review'),
  })

  const grantExtension = useMutation({
    mutationFn: () =>
      api.post(`/api/v1/tasks/${id}/extensions`, {
        task_id: id,
        intern_id: task.data?.assignee_id,
        new_deadline: fromLocalInputValue(extForm.new_deadline),
        reason: extForm.reason || null,
      }),
    onSuccess: () => {
      toast.success('Extension granted')
      setExtOpen(false)
      setExtForm({ new_deadline: '', reason: '' })
      invalidate()
    },
    onError: (e) => toast.error(e instanceof ApiError ? e.detail : 'Failed to grant extension'),
  })

  if (Number.isNaN(id)) return null
  const t = task.data
  const effectiveDiffers = t && t.effective_deadline && t.deadline && t.effective_deadline !== t.deadline

  return (
    <div>
      {task.isLoading ? (
        <Skeleton className="h-40 rounded-xl" />
      ) : !t ? (
        <EmptyState title="Task not found" description="This task doesn't exist or you don't have access to it." />
      ) : (
        <>
          <div className="mb-6">
            <div className="flex flex-wrap items-start justify-between gap-3">
              <div>
                <h1 className="text-2xl font-bold tracking-tight">{t.title}</h1>
                <div className="mt-2 flex flex-wrap items-center gap-2">
                  <Badge variant={statusVariant[t.status]}>{titleCase(t.status)}</Badge>
                  <Badge variant={t.priority ? priorityVariant[t.priority] : 'outline'}>{t.priority ?? '—'}</Badge>
                  {t.category && <Badge variant="muted">{t.category}</Badge>}
                  {t.scope && <Badge variant="outline">{titleCase(t.scope)}</Badge>}
                </div>
              </div>
              {isSupervisor && t.assignee_id && (
                <Button variant="outline" size="sm" onClick={() => setExtOpen(true)}>
                  <CalendarClock className="size-4" /> Request extension
                </Button>
              )}
            </div>
            <div className="mt-3 flex flex-wrap gap-x-6 gap-y-1 text-sm text-muted-foreground">
              <span>
                Deadline: <span className="font-medium text-foreground">{formatDateTime(t.deadline)}</span>
              </span>
              {effectiveDiffers && (
                <span>
                  Effective: <span className="font-medium text-foreground">{formatDateTime(t.effective_deadline)}</span>
                </span>
              )}
              {t.assignee_name && <span>Assignee: {t.assignee_name}</span>}
              {t.author_name && <span>Created by: {t.author_name}</span>}
            </div>
          </div>

          {t.description && (
            <Card className="mb-6">
              <CardContent className="whitespace-pre-wrap text-sm text-foreground/90">{t.description}</CardContent>
            </Card>
          )}

          <div className="mb-6 grid gap-4 lg:grid-cols-2">
            <Card>
              <CardHeader>
                <CardTitle className="flex items-center gap-2 text-sm">
                  <Paperclip className="size-4 text-primary" /> Attachments
                </CardTitle>
              </CardHeader>
              <CardContent>
                {isSupervisor && (
                  <div className="mb-3">
                    <input
                      ref={attachRef}
                      type="file"
                      className="hidden"
                      onChange={(e) => {
                        const f = e.target.files?.[0]
                        if (f) uploadAttachment.mutate(f)
                        e.target.value = ''
                      }}
                    />
                    <Button variant="outline" size="sm" onClick={() => attachRef.current?.click()} loading={uploadAttachment.isPending}>
                      <Upload className="size-4" /> Upload
                    </Button>
                  </div>
                )}
                {t.attachments.length === 0 ? (
                  <p className="text-sm text-muted-foreground">No attachments.</p>
                ) : (
                  <ul className="divide-y divide-border rounded-lg border border-border">
                    {t.attachments.map((a) => (
                      <li key={a.id} className="flex items-center justify-between gap-3 px-3 py-2 text-sm">
                        <span className="truncate font-medium">{a.filename}</span>
                        <a
                          href={`${base}/api/v1/tasks/${id}/attachments/${a.id}/download`}
                          target="_blank"
                          rel="noreferrer"
                          className="flex shrink-0 items-center gap-1 text-xs text-primary hover:underline"
                        >
                          <Download className="size-3.5" /> Download
                        </a>
                      </li>
                    ))}
                  </ul>
                )}
              </CardContent>
            </Card>

            <Card>
              <CardHeader>
                <CardTitle className="text-sm">Comments</CardTitle>
              </CardHeader>
              <CardContent>
                <div className="max-h-96 space-y-3 overflow-y-auto pb-1">
                  {comments.isLoading ? (
                    <Spinner />
                  ) : (comments.data?.length ?? 0) === 0 ? (
                    <p className="text-sm text-muted-foreground">No comments yet. Start the discussion.</p>
                  ) : (
                    comments.data?.map((c) => (
                      <div key={c.id} className="rounded-lg border border-border p-3">
                        <div className="flex items-center justify-between gap-2">
                          <div className="flex items-center gap-2 text-xs text-muted-foreground">
                            <span className="font-medium text-foreground">{c.author_name ?? 'Unknown'}</span>
                            <span>{relativeTime(c.created_at)}</span>
                            {c.is_edited && <span>· edited</span>}
                            {c.is_pinned && (
                              <span className="flex items-center gap-0.5 text-primary">
                                <Pin className="size-3" /> Pinned
                              </span>
                            )}
                          </div>
                          {c.author_id === user?.id && !c.is_deleted && (
                            <DropdownMenu trigger={<MoreHorizontal className="size-4 text-muted-foreground" />}>
                              {isSupervisor && (
                                <DropdownItem onClick={() => pinComment.mutate({ cid: c.id, pin: !c.is_pinned })}>
                                  {c.is_pinned ? <PinOff className="size-4" /> : <Pin className="size-4" />}
                                  {c.is_pinned ? 'Unpin' : 'Pin'}
                                </DropdownItem>
                              )}
                              <DropdownItem onClick={() => { setEditingId(c.id); setEditDraft(c.content) }}>
                                <Pencil className="size-4" /> Edit
                              </DropdownItem>
                              <DropdownItem danger onClick={() => setDeleteId(c.id)}>
                                <Trash2 className="size-4" /> Delete
                              </DropdownItem>
                            </DropdownMenu>
                          )}
                        </div>
                        {editingId === c.id ? (
                          <div className="mt-2 space-y-2">
                            <Textarea rows={2} value={editDraft} onChange={(e) => setEditDraft(e.target.value)} />
                            <div className="flex justify-end gap-2">
                              <Button size="sm" variant="ghost" onClick={() => setEditingId(null)}>
                                Cancel
                              </Button>
                              <Button
                                size="sm"
                                onClick={() => editComment.mutate({ cid: c.id, content: editDraft })}
                                loading={editComment.isPending}
                                disabled={!editDraft.trim()}
                              >
                                Save
                              </Button>
                            </div>
                          </div>
                        ) : (
                          <p className="mt-1 text-sm">{c.content}</p>
                        )}
                      </div>
                    ))
                  )}
                </div>
                <div className="mt-3 flex gap-2">
                  <Input
                    value={commentDraft}
                    onChange={(e) => setCommentDraft(e.target.value)}
                    onKeyDown={(e) => {
                      if (e.key === 'Enter' && !e.shiftKey && commentDraft.trim()) addComment.mutate(commentDraft.trim())
                    }}
                    placeholder="Write a comment…"
                  />
                  <Button
                    size="icon"
                    onClick={() => commentDraft.trim() && addComment.mutate(commentDraft.trim())}
                    loading={addComment.isPending}
                    disabled={!commentDraft.trim()}
                    title="Post comment"
                  >
                    <Send className="size-4" />
                  </Button>
                </div>
              </CardContent>
            </Card>
          </div>

          <Card>
            <CardHeader>
              <CardTitle className="text-sm">
                {isIntern ? 'Your Submissions' : 'Submissions'}
              </CardTitle>
            </CardHeader>
            <CardContent>
              {subs.isLoading ? (
                <Spinner />
              ) : (subs.data?.items.length ?? 0) === 0 ? (
                <EmptyState title="No submissions yet" description="Nothing has been submitted for this task." />
              ) : (
                <div className="overflow-hidden rounded-xl border border-border">
                  <Table>
                    <THead>
                      <TR>
                        {!isIntern && <TH>Intern</TH>}
                        <TH>Version</TH>
                        <TH>Submitted</TH>
                        <TH>Status</TH>
                        <TH>Links</TH>
                        {isSupervisor && <TH className="text-right">Action</TH>}
                      </TR>
                    </THead>
                    <TBody>
                      {subs.data?.items.map((s) => (
                        <TR key={s.id}>
                          {!isIntern && <TD className="font-medium">{s.intern_name ?? `Intern #${s.intern_id}`}</TD>}
                          <TD>
                            v{s.version}
                            {s.is_late && <Badge variant="warning" className="ml-2">late</Badge>}
                          </TD>
                          <TD className="text-muted-foreground">{formatDateTime(s.submitted_at)}</TD>
                          <TD>
                            <Badge variant={submissionVariant[s.status]}>{titleCase(s.status)}</Badge>
                          </TD>
                          <TD>
                            <div className="flex items-center gap-1">
                              {s.github_url && (
                                <a href={s.github_url} target="_blank" rel="noreferrer" className="flex items-center gap-1 text-xs text-primary hover:underline">
                                  <ExternalLink className="size-3" /> GitHub
                                </a>
                              )}
                              {s.live_url && (
                                <a href={s.live_url} target="_blank" rel="noreferrer" className="flex items-center gap-1 text-xs text-primary hover:underline">
                                  <ExternalLink className="size-3" /> Live
                                </a>
                              )}
                              {!s.github_url && !s.live_url && <span className="text-xs text-muted-foreground">—</span>}
                            </div>
                          </TD>
                          {isSupervisor && (
                            <TD className="text-right">
                              <Button size="sm" variant="outline" onClick={() => { setReviewTarget(s); setReviewForm(emptyReview) }}>
                                Review
                              </Button>
                            </TD>
                          )}
                        </TR>
                      ))}
                    </TBody>
                  </Table>
                </div>
              )}

              {(subs.data?.items ?? []).map((s) => (
                <div key={s.id} className={`mt-3 ${(s.reviews ?? []).length === 0 ? 'hidden' : ''}`}>
                  <p className="mb-2 text-xs font-medium uppercase tracking-wide text-muted-foreground">
                    Reviews — v{s.version}
                  </p>
                  <ul className="space-y-2">
                    {(s.reviews ?? []).map((r, i) => (
                      <li key={i} className="rounded-lg bg-muted/50 p-3">
                        <div className="flex flex-wrap items-center gap-2 text-xs text-muted-foreground">
                          <Badge variant={decisionVariant[r.decision]}>{titleCase(r.decision)}</Badge>
                          {r.score != null && <span className="font-semibold text-foreground">{r.score}/10</span>}
                          <span>{r.supervisor_name ?? 'Supervisor'}</span>
                          <span>· {formatDateTime(r.reviewed_at)}</span>
                        </div>
                        {r.feedback && <p className="mt-1 text-sm">{r.feedback}</p>}
                      </li>
                    ))}
                  </ul>
                </div>
              ))}

              {isIntern && (
                <div className="mt-6 border-t border-border pt-5">
                  <p className="mb-3 text-sm font-semibold">Submit work</p>
                  <div className="grid gap-4">
                    <div className="grid gap-4 sm:grid-cols-2">
                      <div>
                        <Label htmlFor="github">GitHub URL</Label>
                        <Input
                          id="github"
                          value={subForm.github_url}
                          onChange={(e) => setSubForm((f) => ({ ...f, github_url: e.target.value }))}
                          placeholder="https://github.com/…"
                        />
                      </div>
                      <div>
                        <Label htmlFor="live">Live URL</Label>
                        <Input
                          id="live"
                          value={subForm.live_url}
                          onChange={(e) => setSubForm((f) => ({ ...f, live_url: e.target.value }))}
                          placeholder="https://…"
                        />
                      </div>
                    </div>
                    <div>
                      <Label htmlFor="notes">Notes</Label>
                      <Textarea
                        id="notes"
                        rows={3}
                        value={subForm.notes}
                        onChange={(e) => setSubForm((f) => ({ ...f, notes: e.target.value }))}
                        placeholder="What did you do? How did you approach it?"
                      />
                    </div>
                    <div className="grid gap-4 sm:grid-cols-2">
                      <div>
                        <Label htmlFor="effort">Actual effort (hours)</Label>
                        <Input
                          id="effort"
                          type="number"
                          min={0}
                          step="0.5"
                          value={subForm.actual_effort_hours}
                          onChange={(e) => setSubForm((f) => ({ ...f, actual_effort_hours: e.target.value }))}
                        />
                      </div>
                      <div className="flex items-end">
                        <Button variant="outline" size="sm" onClick={() => subFileRef.current?.click()} className={subFile ? 'border-primary text-primary' : ''}>
                          <Upload className="size-4" /> {subFile ? subFile.name : 'Attach file'}
                        </Button>
                        <input
                          ref={subFileRef}
                          type="file"
                          className="hidden"
                          onChange={(e) => {
                            setSubFile(e.target.files?.[0] ?? null)
                            e.target.value = ''
                          }}
                        />
                      </div>
                    </div>
                    <div className="flex justify-end">
                      <Button onClick={() => submitWork.mutate()} loading={submitWork.isPending}>
                        <Send className="size-4" /> Submit work
                      </Button>
                    </div>
                  </div>
                </div>
              )}
            </CardContent>
          </Card>
        </>
      )}

      <Dialog
        open={!!reviewTarget}
        onClose={() => setReviewTarget(null)}
        title="Review Submission"
        description={reviewTarget ? `v${reviewTarget.version} by ${reviewTarget.intern_name ?? `Intern #${reviewTarget.intern_id}`}` : undefined}
        footer={
          <>
            <Button variant="outline" onClick={() => setReviewTarget(null)}>
              Cancel
            </Button>
            <Button
              onClick={() => review.mutate()}
              loading={review.isPending}
              disabled={!reviewForm.score || Number(reviewForm.score) < 0 || Number(reviewForm.score) > 10 || !reviewForm.feedback.trim()}
            >
              Submit review
            </Button>
          </>
        }
      >
        <div className="grid gap-4">
          <div>
            <Label>Decision</Label>
            <Select
              value={reviewForm.decision}
              onChange={(e) => setReviewForm((f) => ({ ...f, decision: e.target.value as ReviewDecision }))}
            >
              <option value="approved">Approved</option>
              <option value="changes_requested">Changes requested</option>
              <option value="rejected">Rejected</option>
            </Select>
          </div>
          <div>
            <Label>Score (1–10)</Label>
            <Input
              type="number"
              min={1}
              max={10}
              step="0.5"
              value={reviewForm.score}
              onChange={(e) => setReviewForm((f) => ({ ...f, score: e.target.value }))}
            />
          </div>
          <div>
            <Label>Feedback</Label>
            <Textarea
              rows={3}
              value={reviewForm.feedback}
              onChange={(e) => setReviewForm((f) => ({ ...f, feedback: e.target.value }))}
              placeholder="Detailed feedback for the intern…"
            />
          </div>
        </div>
      </Dialog>

      <Dialog
        open={extOpen}
        onClose={() => setExtOpen(false)}
        title="Request Extension"
        description={`Grant ${t?.assignee_name ?? 'the intern'} more time on this task`}
        footer={
          <>
            <Button variant="outline" onClick={() => setExtOpen(false)}>
              Cancel
            </Button>
            <Button
              onClick={() => grantExtension.mutate()}
              loading={grantExtension.isPending}
              disabled={!extForm.new_deadline}
            >
              Grant extension
            </Button>
          </>
        }
      >
        <div className="grid gap-4">
          <div>
            <Label>New deadline</Label>
            <Input
              type="datetime-local"
              value={extForm.new_deadline}
              onChange={(e) => setExtForm((f) => ({ ...f, new_deadline: e.target.value }))}
            />
          </div>
          <div>
            <Label>Reason</Label>
            <Textarea
              rows={3}
              value={extForm.reason}
              onChange={(e) => setExtForm((f) => ({ ...f, reason: e.target.value }))}
              placeholder="Why is this extension needed?"
            />
          </div>
        </div>
      </Dialog>

      <Dialog
        open={deleteId !== null}
        onClose={() => setDeleteId(null)}
        title="Delete Comment"
        description="Delete this comment? It will be hidden but kept for audit."
        footer={
          <>
            <Button variant="outline" onClick={() => setDeleteId(null)}>
              Cancel
            </Button>
            <Button variant="destructive" onClick={() => deleteId && deleteComment.mutate(deleteId)} loading={deleteComment.isPending}>
              Delete
            </Button>
          </>
        }
      />
    </div>
  )
}