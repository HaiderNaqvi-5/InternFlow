import { zodResolver } from '@hookform/resolvers/zod'
import { LogIn } from 'lucide-react'
import { useForm } from 'react-hook-form'
import { Link, useLocation, useNavigate } from 'react-router-dom'
import { toast } from 'sonner'
import { z } from 'zod'

import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { useAuth } from '@/context/auth'
import { ApiError } from '@/lib/api'

const schema = z.object({
  email: z.string().email('Enter a valid email'),
  password: z.string().min(1, 'Password is required'),
})
type Form = z.infer<typeof schema>

export default function LoginPage() {
  const { login } = useAuth()
  const navigate = useNavigate()
  const location = useLocation()
  const form = useForm<Form>({ resolver: zodResolver(schema) })
  const from = (location.state as { from?: string } | null)?.from ?? '/'

  const onSubmit = async (values: Form) => {
    try {
      const user = await login(values.email, values.password)
      toast.success(`Welcome back, ${user.full_name.split(' ')[0]}!`)
      if (user.must_reset_password) {
        navigate('/set-password')
      } else {
        navigate(from, { replace: true })
      }
    } catch (e) {
      toast.error(e instanceof ApiError ? e.detail : 'Login failed')
    }
  }

  return (
    <div className="flex min-h-screen items-center justify-center bg-gradient-to-br from-primary/10 via-background to-background px-4">
      <Card className="w-full max-w-sm">
        <CardHeader className="items-center pb-4 text-center">
          <span className="mb-2 flex size-11 items-center justify-center rounded-xl bg-primary text-lg font-bold text-primary-foreground">
            IF
          </span>
          <CardTitle className="text-xl">Welcome to InternFlow</CardTitle>
          <CardDescription>Sign in to continue to your workspace</CardDescription>
        </CardHeader>
        <CardContent>
          <form onSubmit={form.handleSubmit(onSubmit)} className="grid gap-4">
            <div>
              <Label htmlFor="email">Email</Label>
              <Input id="email" type="email" autoComplete="email" placeholder="you@example.com" {...form.register('email')} />
              {form.formState.errors.email && <p className="mt-1 text-xs text-destructive">{form.formState.errors.email.message}</p>}
            </div>
            <div>
              <Label htmlFor="password">Password</Label>
              <Input id="password" type="password" autoComplete="current-password" placeholder="••••••••" {...form.register('password')} />
              {form.formState.errors.password && <p className="mt-1 text-xs text-destructive">{form.formState.errors.password.message}</p>}
            </div>
            <Button type="submit" loading={form.formState.isSubmitting} className="mt-1">
              <LogIn className="size-4" /> Sign in
            </Button>
          </form>
          <p className="mt-5 text-center text-sm text-muted-foreground">
            <Link to="/forgot-password" className="font-medium text-primary hover:underline">
              Forgot your password?
            </Link>
          </p>
        </CardContent>
      </Card>
    </div>
  )
}