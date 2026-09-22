import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { Download, Pencil, Plus, Search, Trash2, Upload } from 'lucide-react'
import { useRef, useState } from 'react'
import { toast } from 'sonner'

import { Avatar } from '@/components/ui/avatar'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Dialog } from '@/components/ui/dialog'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { PageHeader } from '@/components/ui/page-header'
import { Skeleton } from '@/components/ui/skeleton'
import { Textarea } from '@/components/ui/textarea'
import { Table, TBody, TD, TH, THead, TR } from '@/components/ui/table'
import { api, ApiError } from '@/lib/api'
import { formatDate, titleCase } from '@/lib/format'
import type { PaginatedBatches, PaginatedUsers, Role, User } from '@/lib/types'

interface ImportPreviewShape {
  filename: string
  valid_count: number
  failed_count: number
  valid_rows: Record<string, unknown>[]
  failed_rows: { row?: number; error?: string; row_data?: unknown }[]
}

const roleVariant: Record<Role, 'default' | 'warning' | 'info'> = {
  admin: 'default',
  supervisor: 'warning',
  intern: 'info',
}

interface NewUserForm {
  email: string
  full_name: string
  role: Role
  batch_id: string
}

const emptyNew: NewUserForm = { email: '', full_name: '', role: 'intern', batch_id: '' }

export default function UsersPage() {
  const qc = useQueryClient()
  const [search, setSearch] = useState('')
  const [role, setRole] = useState('')
  const [activeOnly, setActiveOnly] = useState(false)
  const [newOpen, setNewOpen] = useState(false)
  const [newForm, setNewForm] = useState<NewUserForm>(emptyNew)
  const [editUser, setEditUser] = useState<User | null>(null)
  const [deactivateUser, setDeactivateUser] = useState<number>(0)
  const [selected, setSelected] = useState<Set<number>>(new Set())
  const [importOpen, setImportOpen] = useState(false)
  const [importFile, setImportFile] = useState<File | null>(null)
  const [preview, setPreview] = useState<ImportPreviewShape | null>(null)
  const fileRef = useRef<HTMLInputElement>(null)

  const params = new URLSearchParams({ page_size: '100' })
  if (search) params.set('search', search)
  if (role) params.set('role', role)
  if (activeOnly) params.set('active_only', 'true')

  const users = useQuery({
    queryKey: ['users', search, role, activeOnly],
    queryFn: () => api.get<PaginatedUsers>(`/api/v1/users?${params.toString()}`),
  })
  const batches = useQuery({
    queryKey: ['batches'],
    queryFn: () => api.get<PaginatedBatches>('/api/v1/batches?page_size=200'),
  })

  const create = useMutation({
    mutationFn: (v: NewUserForm) =>
      api.post('/api/v1/users', {
        email: v.email,
        full_name: v.full_name,
        role: v.role,
        batch_id: v.batch_id ? Number(v.batch_id) : null,
      }),
    onSuccess: () => {
      toast.success('User created')
      setNewOpen(false)
      setNewForm(emptyNew)
      qc.invalidateQueries({ queryKey: ['users'] })
    },
    onError: (e) => toast.error(e instanceof ApiError ? e.detail : 'Failed to create user'),
  })

  const [editForm, setEditForm] = useState({ full_name: '', phone: '', bio: '', is_active: true })
  const openEdit = (u: User) => {
    setEditUser(u)
    setEditForm({ full_name: u.full_name, phone: u.phone ?? '', bio: u.bio ?? '', is_active: u.is_active })
  }
  const update = useMutation({
    mutationFn: () =>
      api.patch(`/api/v1/users/${editUser!.id}`, {
        full_name: editForm.full_name,
        phone: editForm.phone || null,
        bio: editForm.bio || null,
        is_active: editForm.is_active,
      }),
    onSuccess: () => {
      toast.success('User updated')
      setEditUser(null)
      qc.invalidateQueries({ queryKey: ['users'] })
    },
    onError: (e) => toast.error(e instanceof ApiError ? e.detail : 'Failed to update user'),
  })

  const deactivate = useMutation({
    mutationFn: (id: number) => api.delete(`/api/v1/users/${id}`),
    onSuccess: () => {
      toast.success('User deactivated')
      setDeactivateUser(0)
      qc.invalidateQueries({ queryKey: ['users'] })
    },
    onError: (e) => toast.error(e instanceof ApiError ? e.detail : 'Failed to deactivate user'),
  })

  const bulkDeactivate = useMutation({
    mutationFn: (ids: number[]) => api.post('/api/v1/users/bulk/deactivate', { user_ids: ids }),
    onSuccess: () => {
      toast.success('Users deactivated')
      setSelected(new Set())
      qc.invalidateQueries({ queryKey: ['users'] })
    },
    onError: (e) => toast.error(e instanceof ApiError ? e.detail : 'Failed to deactivate users'),
  })

  const runPreview = useMutation({
    mutationFn: (file: File) => api.upload<ImportPreviewShape>('/api/v1/users/import/preview', file),
    onSuccess: (data) => {
      setPreview(data)
      setImportOpen(true)
    },
    onError: (e) => toast.error(e instanceof ApiError ? e.detail : 'Preview failed'),
  })

  const applyImport = useMutation({
    mutationFn: (file: File) => api.upload<unknown>('/api/v1/users/import/apply', file),
    onSuccess: () => {
      toast.success('Import applied')
      setImportOpen(false)
      setPreview(null)
      setImportFile(null)
      qc.invalidateQueries({ queryKey: ['users'] })
    },
    onError: (e) => toast.error(e instanceof ApiError ? e.detail : 'Import failed'),
  })

  const onFile = (e: React.ChangeEvent<HTMLInputElement>) => {
    const f = e.target.files?.[0]
    if (f) {
      setImportFile(f)
      runPreview.mutate(f)
    }
    e.target.value = ''
  }

  const toggleSel = (id: number) => {
    setSelected((prev) => {
      const next = new Set(prev)
      if (next.has(id)) next.delete(id)
      else next.add(id)
      return next
    })
  }

  const active = users.data?.items ?? []

  return (
    <div>
      <PageHeader
        title="Users"
        description="Manage interns, supervisors, and admins"
        actions={
          <>
            {selected.size > 0 && (
              <Button
                variant="destructive"
                size="sm"
                onClick={() => bulkDeactivate.mutate([...selected])}
                loading={bulkDeactivate.isPending}
              >
                Deactivate ({selected.size})
              </Button>
            )}
            <Button variant="outline" size="sm" onClick={() => fileRef.current?.click()}>
              <Download className="size-4" /> Import
            </Button>
            <input ref={fileRef} type="file" accept=".csv" className="hidden" onChange={onFile} />
            <Button size="sm" onClick={() => setNewOpen(true)}>
              <Plus className="size-4" /> New user
            </Button>
          </>
        }
      />

      <div className="mb-4 flex flex-wrap items-center gap-3">
        <div className="relative w-full max-w-xs">
          <Search className="absolute left-3 top-1/2 size-4 -translate-y-1/2 text-muted-foreground" />
          <Input
            className="pl-9"
            placeholder="Search name or email…"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
          />
        </div>
        <select
          className="h-9 w-40 rounded-lg border border-input bg-transparent px-3 text-sm"
          value={role}
          onChange={(e) => setRole(e.target.value)}
        >
          <option value="">All roles</option>
          <option value="intern">Intern</option>
          <option value="supervisor">Supervisor</option>
          <option value="admin">Admin</option>
        </select>
        <label className="flex items-center gap-2 text-sm">
          <input type="checkbox" checked={activeOnly} onChange={(e) => setActiveOnly(e.target.checked)} />
          Active only
        </label>
      </div>

      {users.isLoading ? (
        <Skeleton className="h-64 rounded-xl" />
      ) : active.length === 0 ? (
        <div className="rounded-xl border border-dashed border-border p-10 text-center text-sm text-muted-foreground">
          No users found.
        </div>
      ) : (
        <div className="overflow-hidden rounded-xl border border-border">
          <Table>
            <THead>
              <TR>
                <TH className="w-10">
                  <input
                    type="checkbox"
                    checked={active.length > 0 && active.every((u) => selected.has(u.id))}
                    onChange={(e) =>
                      setSelected(e.target.checked ? new Set(active.map((u) => u.id)) : new Set())
                    }
                  />
                </TH>
                <TH>User</TH>
                <TH>Role</TH>
                <TH>Status</TH>
                <TH>Created</TH>
                <TH className="text-right">Actions</TH>
              </TR>
            </THead>
            <TBody>
              {active.map((u) => (
                <TR key={u.id}>
                  <TD>
                    <input type="checkbox" checked={selected.has(u.id)} onChange={() => toggleSel(u.id)} />
                  </TD>
                  <TD>
                    <div className="flex items-center gap-3">
                      <Avatar name={u.full_name} src={u.avatar_key} />
                      <div>
                        <p className="font-medium">{u.full_name}</p>
                        <p className="text-xs text-muted-foreground">{u.email}</p>
                      </div>
                    </div>
                  </TD>
                  <TD>
                    <Badge variant={roleVariant[u.role]}>{titleCase(u.role)}</Badge>
                  </TD>
                  <TD>
                    <Badge variant={u.is_active ? 'success' : 'muted'}>{u.is_active ? 'Active' : 'Inactive'}</Badge>
                  </TD>
                  <TD className="text-muted-foreground">{formatDate(u.created_at)}</TD>
                  <TD>
                    <div className="flex justify-end gap-1">
                      <Button variant="ghost" size="icon" onClick={() => openEdit(u)} title="Edit">
                        <Pencil className="size-4" />
                      </Button>
                      <Button
                        variant="ghost"
                        size="icon"
                        className="text-destructive"
                        disabled={!u.is_active}
                        onClick={() => setDeactivateUser(u.id)}
                        title="Deactivate"
                      >
                        <Trash2 className="size-4" />
                      </Button>
                    </div>
                  </TD>
                </TR>
              ))}
            </TBody>
          </Table>
        </div>
      )}

      <Dialog
        open={newOpen}
        onClose={() => setNewOpen(false)}
        title="New User"
        description="Create a new user account"
        footer={
          <>
            <Button variant="outline" onClick={() => setNewOpen(false)}>
              Cancel
            </Button>
            <Button
              onClick={() => create.mutate(newForm)}
              loading={create.isPending}
              disabled={!newForm.email || !newForm.full_name}
            >
              Create user
            </Button>
          </>
        }
      >
        <div className="grid gap-4">
          <div>
            <Label>Full name</Label>
            <Input value={newForm.full_name} onChange={(e) => setNewForm((f) => ({ ...f, full_name: e.target.value }))} />
          </div>
          <div>
            <Label>Email</Label>
            <Input type="email" value={newForm.email} onChange={(e) => setNewForm((f) => ({ ...f, email: e.target.value }))} />
          </div>
          <div className="grid grid-cols-2 gap-3">
            <div>
              <Label>Role</Label>
              <select
                className="h-9 w-full rounded-lg border border-input bg-transparent px-3 text-sm"
                value={newForm.role}
                onChange={(e) => setNewForm((f) => ({ ...f, role: e.target.value as Role }))}
              >
                <option value="intern">Intern</option>
                <option value="supervisor">Supervisor</option>
                <option value="admin">Admin</option>
              </select>
            </div>
            {newForm.role === 'intern' && (
              <div>
                <Label>Batch (optional)</Label>
                <select
                  className="h-9 w-full rounded-lg border border-input bg-transparent px-3 text-sm"
                  value={newForm.batch_id}
                  onChange={(e) => setNewForm((f) => ({ ...f, batch_id: e.target.value }))}
                >
                  <option value="">None</option>
                  {(batches.data?.items ?? []).map((b) => (
                    <option key={b.id} value={b.id}>
                      {b.name}
                    </option>
                  ))}
                </select>
              </div>
            )}
          </div>
        </div>
      </Dialog>

      <Dialog
        open={!!editUser}
        onClose={() => setEditUser(null)}
        title="Edit User"
        description={editUser?.email}
        footer={
          <>
            <Button variant="outline" onClick={() => setEditUser(null)}>
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
            <Label>Full name</Label>
            <Input value={editForm.full_name} onChange={(e) => setEditForm((f) => ({ ...f, full_name: e.target.value }))} />
          </div>
          <div>
            <Label>Phone</Label>
            <Input value={editForm.phone} onChange={(e) => setEditForm((f) => ({ ...f, phone: e.target.value }))} />
          </div>
          <div>
            <Label>Bio</Label>
            <Textarea value={editForm.bio} onChange={(e) => setEditForm((f) => ({ ...f, bio: e.target.value }))} />
          </div>
          <label className="flex items-center gap-2 text-sm">
            <input type="checkbox" checked={editForm.is_active} onChange={(e) => setEditForm((f) => ({ ...f, is_active: e.target.checked }))} />
            Active
          </label>
        </div>
      </Dialog>

      <Dialog
        open={deactivateUser !== 0}
        onClose={() => setDeactivateUser(0)}
        title="Deactivate User"
        description="Deactivate this user? They will no longer be able to sign in."
        footer={
          <>
            <Button variant="outline" onClick={() => setDeactivateUser(0)}>
              Cancel
            </Button>
            <Button
              variant="destructive"
              onClick={() => deactivate.mutate(deactivateUser)}
              loading={deactivate.isPending}
            >
              Deactivate
            </Button>
          </>
        }
      />

      <Dialog
        open={importOpen}
        onClose={() => {
          setImportOpen(false)
          setPreview(null)
        }}
        title="Import Preview"
        description={preview?.filename ?? undefined}
        footer={
          <>
            <Button
              variant="outline"
              onClick={() => {
                setImportOpen(false)
                setPreview(null)
              }}
            >
              Cancel
            </Button>
            <Button
              onClick={() => importFile && applyImport.mutate(importFile)}
              loading={applyImport.isPending}
              disabled={!importFile || (preview ? preview.valid_count === 0 : false)}
            >
              <Upload className="size-4" /> Apply import
            </Button>
          </>
        }
      >
        {preview ? (
          <div className="space-y-4">
            <div className="flex gap-4 text-sm">
              <span className="text-success">{preview.valid_count} valid</span>
              <span className={preview.failed_count > 0 ? 'text-destructive' : 'text-muted-foreground'}>
                {preview.failed_count} failed
              </span>
            </div>
            {preview.valid_rows.length > 0 && (
              <div className="space-y-2">
                <p className="text-xs font-medium uppercase text-muted-foreground">Valid rows</p>
                <div className="max-h-48 overflow-y-auto space-y-1">
                  {preview.valid_rows.map((row, i) => (
                    <pre key={i} className="rounded-md bg-muted p-2 text-xs">
                      {JSON.stringify(row)}
                    </pre>
                  ))}
                </div>
              </div>
            )}
            {preview.failed_rows.length > 0 && (
              <div className="space-y-2">
                <p className="text-xs font-medium uppercase text-destructive">Failed rows</p>
                <div className="max-h-48 overflow-y-auto space-y-1">
                  {preview.failed_rows.map((row, i) => (
                    <pre key={i} className="rounded-md bg-destructive/10 p-2 text-xs">
                      {JSON.stringify(row)}
                    </pre>
                  ))}
                </div>
              </div>
            )}
          </div>
        ) : (
          <p className="text-sm text-muted-foreground">Loading preview…</p>
        )}
      </Dialog>
    </div>
  )
}
