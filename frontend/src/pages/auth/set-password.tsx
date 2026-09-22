import { zodResolver } from '@hookform/resolvers/zod'
import { KeyRound } from 'lucide-react'
import { useForm } from 'react-hook-form'
import { useNavigate } from 'react-router-dom'
import { toast } from 'sonner'
import { z } from 'zod'

import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { useAuth } from '@/context/auth'
import { ApiError } from '@/lib/api'

const schema = z
  .object({
    currentPassword: z.string().min(1, 'Current password is required'),
    newPassword: z.string().min(8, 'Password must be at least 8 characters'),
    confirmPassword: z.string(),
  })
  .refine((v) => v.newPassword === v.confirmPassword, { message: 'Passwords do not match', path: ['confirmPassword'] })
type Form = z.infer<typeof schema>

export default function SetPasswordPage() {
  const { user, setFirstPassword } = useAuth()
  const navigate = useNavigate()
  const form = useForm<Form>({ resolver: zodResolver(schema) })

  const onSubmit = async (values: Form) => {
    if (!user) return
    try {
      await setFirstPassword(user.email, values.currentPassword, values.newPassword)
      toast.success('Password set successfully')
      navigate('/', { replace: true })
    } catch (e) {
      toast.error(e instanceof ApiError ? e.detail : 'Could not set password')
    }
  }

  return (
    <div className="flex min-h-screen items-center justify-center px-4">
      <Card className="w-full max-w-sm">
        <CardHeader className="items-center pb-4 text-center">
          <span className="mb-2 flex size-11 items-center justify-center rounded-xl bg-primary text-lg font-bold text-primary-foreground">
            <KeyRound className="size-5" />
          </span>
          <CardTitle className="text-xl">Set your password</CardTitle>
          <CardDescription>
            For security, you must choose your own password before continuing.
          </CardDescription>
        </CardHeader>
        <CardContent>
          <form onSubmit={form.handleSubmit(onSubmit)} className="grid gap-4">
            <div>
              <Label>Email</Label>
              <Input value={user?.email ?? ''} disabled />
            </div>
            <div>
              <Label htmlFor="current">Temporary password</Label>
              <Input id="current" type="password" autoComplete="current-password" {...form.register('currentPassword')} />
              {form.formState.errors.currentPassword && (
                <p className="mt-1 text-xs text-destructive">{form.formState.errors.currentPassword.message}</p>
              )}
            </div>
            <div>
              <Label htmlFor="new">New password</Label>
              <Input id="new" type="password" autoComplete="new-password" {...form.register('newPassword')} />
              {form.formState.errors.newPassword && (
                <p className="mt-1 text-xs text-destructive">{form.formState.errors.newPassword.message}</p>
              )}
            </div>
            <div>
              <Label htmlFor="confirm">Confirm new password</Label>
              <Input id="confirm" type="password" autoComplete="new-password" {...form.register('confirmPassword')} />
              {form.formState.errors.confirmPassword && (
                <p className="mt-1 text-xs text-destructive">{form.formState.errors.confirmPassword.message}</p>
              )}
            </div>
            <Button type="submit" loading={form.formState.isSubmitting} className="mt-1">
              Set password
            </Button>
          </form>
        </CardContent>
      </Card>
    </div>
  )
}