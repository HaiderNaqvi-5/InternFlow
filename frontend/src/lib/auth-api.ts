import { apiFetch } from '@/lib/api'
import type { UserMe } from '@/lib/types'

export interface LoginResult {
  access_token: string
  refresh_token: string
  token_type: string
  must_reset_password: boolean
}

export const authApi = {
  login: (email: string, password: string) =>
    apiFetch<LoginResult>('/api/v1/auth/login', {
      method: 'POST',
      body: JSON.stringify({ email, password }),
    }),
  firstPassword: (email: string, currentPassword: string, newPassword: string) =>
    apiFetch<{ message: string }>('/api/v1/auth/first-password', {
      method: 'POST',
      body: JSON.stringify({ email, current_password: currentPassword, new_password: newPassword }),
    }),
  forgotPassword: (email: string) =>
    apiFetch<{ message: string }>('/api/v1/auth/forgot-password', {
      method: 'POST',
      body: JSON.stringify({ email }),
    }),
  resetPassword: (token: string, newPassword: string) =>
    apiFetch<{ message: string }>('/api/v1/auth/reset-password', {
      method: 'POST',
      body: JSON.stringify({ token, new_password: newPassword }),
    }),
  me: () => apiFetch<UserMe>('/api/v1/auth/me'),
  logout: () => apiFetch<{ message: string }>('/api/v1/auth/logout', { method: 'POST' }),
}

export function refreshAccessToken(refreshToken: string): Promise<LoginResult> {
  return apiFetch<LoginResult>('/api/v1/auth/refresh', {
    method: 'POST',
    body: JSON.stringify({ refresh_token: refreshToken }),
  })
}