import { zodResolver } from '@hookform/resolvers/zod'
import { ShieldCheck } from 'lucide-react'
import { useForm } from 'react-hook-form'
import { useNavigate, useSearchParams } from 'react-router-dom'
import { toast } from 'sonner'
import { z } from 'zod'

import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { authApi } from '@/lib/auth-api'
import { ApiError } from '@/lib/api'

const schema = z
  .object({
    newPassword: z.string().min(8, 'Password must be at least 8 characters'),
    confirmPassword: z.string(),
  })
  .refine((v) => v.newPassword === v.confirmPassword, { message: 'Passwords do not match', path: ['confirmPassword'] })
type Form = z.infer<typeof schema>

export default function ResetPasswordPage() {
  const navigate = useNavigate()
  const [params] = useSearchParams()
  const token = params.get('token') ?? ''
  const form = useForm<Form>({ resolver: zodResolver(schema) })

  const onSubmit = async (values: Form) => {
    try {
      await authApi.resetPassword(token, values.newPassword)
      toast.success('Password reset. Please sign in.')
      navigate('/login')
    } catch (e) {
      toast.error(e instanceof ApiError ? e.detail : 'Could not reset password')
    }
  }

  if (!token) {
    return (
      <div className="flex min-h-screen items-center justify-center px-4">
        <Card className="w-full max-w-sm text-center">
          <CardContent className="pt-6">
            <p className="text-sm text-muted-foreground">This reset link is missing or invalid.</p>
            <Button className="mt-4" onClick={() => navigate('/login')} variant="outline">
              Back to sign in
            </Button>
          </CardContent>
        </Card>
      </div>
    )
  }

  return (
    <div className="flex min-h-screen items-center justify-center px-4">
      <Card className="w-full max-w-sm">
        <CardHeader className="items-center pb-4 text-center">
          <span className="mb-2 flex size-11 items-center justify-center rounded-xl bg-primary text-primary-foreground">
            <ShieldCheck className="size-5" />
          </span>
          <CardTitle className="text-xl">Choose a new password</CardTitle>
          <CardDescription>Enter a new password for your account.</CardDescription>
        </CardHeader>
        <CardContent>
          <form onSubmit={form.handleSubmit(onSubmit)} className="grid gap-4">
            <div>
              <Label htmlFor="new">New password</Label>
              <Input id="new" type="password" autoComplete="new-password" {...form.register('newPassword')} />
              {form.formState.errors.newPassword && (
                <p className="mt-1 text-xs text-destructive">{form.formState.errors.newPassword.message}</p>
              )}
            </div>
            <div>
              <Label htmlFor="confirm">Confirm password</Label>
              <Input id="confirm" type="password" autoComplete="new-password" {...form.register('confirmPassword')} />
              {form.formState.errors.confirmPassword && (
                <p className="mt-1 text-xs text-destructive">{form.formState.errors.confirmPassword.message}</p>
              )}
            </div>
            <Button type="submit" loading={form.formState.isSubmitting}>
              Reset password
            </Button>
          </form>
        </CardContent>
      </Card>
    </div>
  )
}