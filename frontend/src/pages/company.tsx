import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { Building2, Save, Upload } from 'lucide-react'
import { useEffect, useRef, useState } from 'react'
import { toast } from 'sonner'

import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { PageHeader } from '@/components/ui/page-header'
import { Skeleton } from '@/components/ui/skeleton'
import { Textarea } from '@/components/ui/textarea'
import { api, ApiError } from '@/lib/api'
import type { CompanySettings } from '@/lib/types'

interface EditForm {
  company_name: string
  company_address: string
  company_phone: string
  company_email: string
  supervisor_signatory: string
  signatory_title: string
  onboarding_message: string
  welcome_message: string
}

const toForm = (s: CompanySettings): EditForm => ({
  company_name: s.company_name,
  company_address: s.company_address ?? '',
  company_phone: s.company_phone ?? '',
  company_email: s.company_email ?? '',
  supervisor_signatory: s.supervisor_signatory ?? '',
  signatory_title: s.signatory_title ?? '',
  onboarding_message: s.onboarding_message ?? '',
  welcome_message: s.welcome_message ?? '',
})

export default function CompanyPage() {
  const qc = useQueryClient()
  const [form, setForm] = useState<EditForm | null>(null)
  const [file, setFile] = useState<File | null>(null)
  const fileRef = useRef<HTMLInputElement>(null)

  const settings = useQuery({
    queryKey: ['company', 'settings'],
    queryFn: () => api.get<CompanySettings>('/api/v1/company/settings'),
  })

  useEffect(() => {
    if (settings.data && !form) setForm(toForm(settings.data))
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [settings.data])

  const save = useMutation({
    mutationFn: (values: EditForm) =>
      api.put<CompanySettings>('/api/v1/company/settings', {
        company_name: values.company_name,
        company_address: values.company_address || null,
        company_phone: values.company_phone || null,
        company_email: values.company_email || null,
        supervisor_signatory: values.supervisor_signatory || null,
        signatory_title: values.signatory_title || null,
        onboarding_message: values.onboarding_message || null,
        welcome_message: values.welcome_message || null,
      }),
    onSuccess: (s) => {
      toast.success('Company settings saved')
      setForm(toForm(s))
      qc.invalidateQueries({ queryKey: ['company', 'settings'] })
    },
    onError: (e) => toast.error(e instanceof ApiError ? e.detail : 'Failed to save settings'),
  })

  const upload = useMutation({
    mutationFn: (f: File) => api.upload<CompanySettings>('/api/v1/company/assets/upload', f),
    onSuccess: (s) => {
      toast.success('Logo uploaded')
      setFile(null)
      setForm(toForm(s))
      qc.invalidateQueries({ queryKey: ['company', 'settings'] })
    },
    onError: (e) => toast.error(e instanceof ApiError ? e.detail : 'Logo upload failed'),
  })

  const set = (k: keyof EditForm) => (e: React.ChangeEvent<HTMLInputElement | HTMLTextAreaElement>) =>
    setForm((f) => (f ? { ...f, [k]: e.target.value } : f))

  if (settings.isLoading) return <Skeleton className="h-64 rounded-xl" />
  if (!settings.data) return null
  if (!form) return null

  return (
    <div>
      <PageHeader title="Company Settings" description="Manage company-wide defaults and branding" />

      <Card>
        <CardHeader>
          <CardTitle>Company Branding</CardTitle>
          <CardDescription>Logo shown on documents and certificates</CardDescription>
        </CardHeader>
        <CardContent>
          <div className="flex items-center gap-4">
            <input
              ref={fileRef}
              type="file"
              accept="image/*"
              className="hidden"
              onChange={(e) => {
                const f = e.target.files?.[0]
                if (f) {
                  setFile(f)
                  upload.mutate(f)
                }
                e.target.value = ''
              }}
            />
            <Button variant="outline" onClick={() => fileRef.current?.click()} loading={upload.isPending}>
              <Upload className="size-4" /> {file ? 'Uploading…' : 'Upload logo'}
            </Button>
            {settings.data.logo_key && (
              <span className="text-xs text-muted-foreground">Current logo: {settings.data.logo_key}</span>
            )}
          </div>
        </CardContent>
      </Card>

      <Card className="mt-6">
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <Building2 className="size-4" /> Company Information
          </CardTitle>
        </CardHeader>
        <CardContent>
          <div className="grid gap-4 md:grid-cols-2">
            <div>
              <Label>Company name</Label>
              <Input value={form.company_name} onChange={set('company_name')} />
            </div>
            <div>
              <Label>Email</Label>
              <Input type="email" value={form.company_email} onChange={set('company_email')} />
            </div>
            <div>
              <Label>Phone</Label>
              <Input value={form.company_phone} onChange={set('company_phone')} />
            </div>
            <div>
              <Label>Address</Label>
              <Input value={form.company_address} onChange={set('company_address')} />
            </div>
            <div>
              <Label>Supervisor signatory</Label>
              <Input value={form.supervisor_signatory} onChange={set('supervisor_signatory')} />
            </div>
            <div>
              <Label>Signatory title</Label>
              <Input value={form.signatory_title} onChange={set('signatory_title')} />
            </div>
            <div className="md:col-span-2">
              <Label>Welcome message</Label>
              <Textarea rows={3} value={form.welcome_message} onChange={set('welcome_message')} />
            </div>
            <div className="md:col-span-2">
              <Label>Onboarding message</Label>
              <Textarea rows={3} value={form.onboarding_message} onChange={set('onboarding_message')} />
            </div>
          </div>
          <div className="mt-4 flex justify-end">
            <Button onClick={() => save.mutate(form)} loading={save.isPending} disabled={!form.company_name}>
              <Save className="size-4" /> Save settings
            </Button>
          </div>
        </CardContent>
      </Card>
    </div>
  )
}
