import { useMutation, useQueryClient } from '@tanstack/react-query'
import { Mail, Upload } from 'lucide-react'
import { useRef, useState } from 'react'
import { toast } from 'sonner'

import { Avatar } from '@/components/ui/avatar'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { PageHeader } from '@/components/ui/page-header'
import { Textarea } from '@/components/ui/textarea'
import { useAuth } from '@/context/auth'
import { api, ApiError } from '@/lib/api'
import { formatDate, titleCase } from '@/lib/format'
import type { UserMe } from '@/lib/types'

interface ProfileForm {
  full_name: string
  phone: string
  bio: string
  github_url: string
  linkedin_url: string
  skills: string
}

export default function ProfilePage() {
  const { user, updateUser } = useAuth()
  const qc = useQueryClient()
  const avatarRef = useRef<HTMLInputElement>(null)

  const [form, setForm] = useState<ProfileForm>({
    full_name: user?.full_name ?? '',
    phone: user?.phone ?? '',
    bio: user?.bio ?? '',
    github_url: user?.github_url ?? '',
    linkedin_url: user?.linkedin_url ?? '',
    skills: (user?.skills ?? []).join(', '),
  })

  const save = useMutation({
    mutationFn: (v: ProfileForm) =>
      api.patch<UserMe>('/api/v1/users/me/profile', {
        full_name: v.full_name,
        phone: v.phone || null,
        bio: v.bio || null,
        github_url: v.github_url || null,
        linkedin_url: v.linkedin_url || null,
        skills: v.skills
          .split(',')
          .map((s) => s.trim())
          .filter(Boolean),
      }),
    onSuccess: (data) => {
      updateUser(data)
      toast.success('Profile updated')
      qc.invalidateQueries({ queryKey: ['me'] })
    },
    onError: (e) => toast.error(e instanceof ApiError ? e.detail : 'Failed to update profile'),
  })

  const uploadAvatar = useMutation({
    mutationFn: (file: File) => api.upload<{ avatar_key: string }>('/api/v1/users/me/avatar', file),
    onSuccess: (data) => {
      if (user) updateUser({ ...user, avatar_key: data.avatar_key })
      toast.success('Avatar updated')
    },
    onError: (e) => toast.error(e instanceof ApiError ? e.detail : 'Failed to upload avatar'),
  })

  if (!user) return null

  return (
    <div>
      <PageHeader title="Profile" description="Your account details and settings" />

      <div className="grid gap-4 lg:grid-cols-3">
        <Card className="lg:col-span-2">
          <CardHeader>
            <CardTitle className="text-sm">Edit profile</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="flex items-center gap-4">
              <Avatar name={user.full_name} src={user.avatar_key} className="size-16 text-lg" />
              <div>
                <input
                  ref={avatarRef}
                  type="file"
                  accept="image/*"
                  className="hidden"
                  onChange={(e) => {
                    const f = e.target.files?.[0]
                    if (f) uploadAvatar.mutate(f)
                    e.target.value = ''
                  }}
                />
                <Button variant="outline" size="sm" onClick={() => avatarRef.current?.click()} loading={uploadAvatar.isPending}>
                  <Upload className="size-4" /> Change avatar
                </Button>
              </div>
            </div>

            <form
              className="mt-6 grid gap-4"
              onSubmit={(e) => {
                e.preventDefault()
                save.mutate(form)
              }}
            >
              <div>
                <Label htmlFor="full-name">Full name</Label>
                <Input id="full-name" value={form.full_name} onChange={(e) => setForm((f) => ({ ...f, full_name: e.target.value }))} />
              </div>
              <div>
                <Label htmlFor="phone">Phone</Label>
                <Input id="phone" value={form.phone} onChange={(e) => setForm((f) => ({ ...f, phone: e.target.value }))} />
              </div>
              <div>
                <Label htmlFor="bio">Bio</Label>
                <Textarea id="bio" rows={3} value={form.bio} onChange={(e) => setForm((f) => ({ ...f, bio: e.target.value }))} />
              </div>
              <div className="grid gap-4 sm:grid-cols-2">
                <div>
                  <Label htmlFor="github">GitHub URL</Label>
                  <Input id="github" value={form.github_url} onChange={(e) => setForm((f) => ({ ...f, github_url: e.target.value }))} placeholder="https://github.com/…" />
                </div>
                <div>
                  <Label htmlFor="linkedin">LinkedIn URL</Label>
                  <Input id="linkedin" value={form.linkedin_url} onChange={(e) => setForm((f) => ({ ...f, linkedin_url: e.target.value }))} placeholder="https://linkedin.com/in/…" />
                </div>
              </div>
              <div>
                <Label htmlFor="skills">Skills (comma separated)</Label>
                <Input id="skills" value={form.skills} onChange={(e) => setForm((f) => ({ ...f, skills: e.target.value }))} placeholder="Python, React, SQL" />
              </div>
              <div className="flex justify-end">
                <Button type="submit" loading={save.isPending}>
                  Save changes
                </Button>
              </div>
            </form>
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle className="text-sm">Account</CardTitle>
            <CardDescription>Your role and sign-in details</CardDescription>
          </CardHeader>
          <CardContent className="space-y-4 text-sm">
            <div>
              <p className="text-xs uppercase tracking-wide text-muted-foreground">Role</p>
              <Badge className="mt-1" variant={user.role === 'intern' ? 'info' : user.role === 'supervisor' ? 'warning' : 'default'}>
                {titleCase(user.role)}
              </Badge>
            </div>
            <div>
              <p className="flex items-center gap-2 text-xs uppercase tracking-wide text-muted-foreground">
                <Mail className="size-3.5" /> Email
              </p>
              <p className="mt-1 font-medium">{user.email}</p>
            </div>
            {user.active_batch_name && (
              <div>
                <p className="text-xs uppercase tracking-wide text-muted-foreground">Batch</p>
                <p className="mt-1 font-medium">{user.active_batch_name}</p>
              </div>
            )}
            <div>
              <p className="text-xs uppercase tracking-wide text-muted-foreground">Member since</p>
              <p className="mt-1 font-medium">{formatDate(user.created_at)}</p>
            </div>
            {user.skills && user.skills.length > 0 && (
              <div>
                <p className="text-xs uppercase tracking-wide text-muted-foreground">Skills</p>
                <div className="mt-2 flex flex-wrap gap-1.5">
                  {user.skills.map((s) => (
                    <Badge key={s} variant="outline">
                      {s}
                    </Badge>
                  ))}
                </div>
              </div>
            )}
          </CardContent>
        </Card>
      </div>
    </div>
  )
}