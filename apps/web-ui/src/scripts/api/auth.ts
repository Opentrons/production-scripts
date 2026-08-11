import { csrfHeaders, rawAuthTransport, refreshSession } from '@/scripts/api/http'

export type AuthRole = 'admin' | 'operator' | 'viewer'

export interface AuthUser {
  id: string
  username: string
  display_name: string
  role: AuthRole
}

export interface AuthSession {
  user: AuthUser
  access_expires_at: string
  session_expires_at: string
}

export interface AuthStatus {
  authenticated: boolean
  user: AuthUser
}

export const authApi = {
  login: (username: string, password: string) =>
    rawAuthTransport.post<AuthSession>('/auth/login', { username, password }),
  me: () => rawAuthTransport.get<AuthStatus>('/auth/me'),
  refresh: refreshSession,
  logout: () => rawAuthTransport.post<{ success: boolean }>(
    '/auth/logout',
    {},
    { headers: csrfHeaders('POST') },
  ),
}
