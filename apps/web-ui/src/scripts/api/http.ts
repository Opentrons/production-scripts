import axios, {
  AxiosHeaders,
  type AxiosError,
  type AxiosInstance,
  type AxiosRequestConfig,
} from 'axios'
import { currentLocale } from '@/i18n'

export const API_BASE_URL = (import.meta.env.VITE_API_BASE_URL || '/api').replace(/\/$/, '')
export const CSRF_COOKIE_NAME = 'production_csrf_token'
const CSRF_HEADER_NAME = 'X-CSRF-Token'
const SAFE_METHODS = new Set(['get', 'head', 'options'])

interface RetriableRequestConfig extends AxiosRequestConfig {
  _authRetry?: boolean
}

const authTransport = axios.create({
  baseURL: API_BASE_URL,
  timeout: 15000,
  withCredentials: true,
})

authTransport.interceptors.request.use((config) => {
  const headers = AxiosHeaders.from(config.headers)
  headers.set('Accept-Language', currentLocale())
  config.headers = headers
  return config
})

let refreshPromise: Promise<void> | null = null

export function readCookie(name: string): string {
  if (typeof document === 'undefined') return ''
  const prefix = `${encodeURIComponent(name)}=`
  const cookie = document.cookie.split('; ').find(item => item.startsWith(prefix))
  return cookie ? decodeURIComponent(cookie.slice(prefix.length)) : ''
}

export function csrfToken(): string {
  return readCookie(CSRF_COOKIE_NAME)
}

export function csrfHeaders(method = 'POST'): Record<string, string> {
  const token = csrfToken()
  return token && !SAFE_METHODS.has(method.toLowerCase()) ? { [CSRF_HEADER_NAME]: token } : {}
}

export function redirectToLogin(): void {
  if (typeof window === 'undefined' || window.location.pathname === '/login') return
  const redirect = `${window.location.pathname}${window.location.search}${window.location.hash}`
  window.location.assign(`/login?redirect=${encodeURIComponent(redirect)}`)
}

export function refreshSession(): Promise<void> {
  if (!refreshPromise) {
    const performRefresh = async (): Promise<void> => {
      try {
        await authTransport.get('/auth/me')
        return
      } catch {
        // Another tab may not have refreshed yet; continue with the refresh cookie.
      }
      const token = csrfToken()
      if (!token) throw new Error('No refresh session is available')
      await authTransport.post(
        '/auth/refresh',
        {},
        { headers: { [CSRF_HEADER_NAME]: token } },
      )
    }
    const coordinatedRefresh = typeof navigator !== 'undefined' && navigator.locks
      ? navigator.locks.request('production-platform-auth-refresh', performRefresh)
      : performRefresh()
    refreshPromise = coordinatedRefresh.finally(() => {
      refreshPromise = null
    })
  }
  return refreshPromise
}

function installInterceptors(client: AxiosInstance): AxiosInstance {
  client.interceptors.request.use((config) => {
    const method = (config.method || 'get').toLowerCase()
    const token = csrfToken()
    const headers = AxiosHeaders.from(config.headers)
    headers.set('Accept-Language', currentLocale())
    if (token && !SAFE_METHODS.has(method)) {
      headers.set(CSRF_HEADER_NAME, token)
    }
    config.headers = headers
    return config
  })

  client.interceptors.response.use(
    response => response,
    async (error: AxiosError) => {
      const responseStatus = error.response?.status
      const request = error.config as RetriableRequestConfig | undefined
      if (responseStatus !== 401 || !request || request._authRetry || request.url?.startsWith('/auth/')) {
        return Promise.reject(error)
      }
      request._authRetry = true
      try {
        await refreshSession()
        return await client.request(request)
      } catch {
        redirectToLogin()
        return Promise.reject(error)
      }
    },
  )
  return client
}

export function createApiClient(timeout = 15000): AxiosInstance {
  return installInterceptors(axios.create({
    baseURL: API_BASE_URL,
    timeout,
    withCredentials: true,
  }))
}

export async function authenticatedFetch(
  input: RequestInfo | URL,
  init: RequestInit = {},
  allowRetry = true,
): Promise<Response> {
  const method = (init.method || 'GET').toUpperCase()
  const headers = new Headers(init.headers)
  headers.set('Accept-Language', currentLocale())
  const token = csrfToken()
  if (token && !SAFE_METHODS.has(method.toLowerCase())) headers.set(CSRF_HEADER_NAME, token)
  const response = await fetch(input, { ...init, headers, credentials: 'same-origin' })
  if (response.status !== 401 || !allowRetry) return response
  try {
    await refreshSession()
  } catch {
    redirectToLogin()
    return response
  }
  const retryHeaders = new Headers(init.headers)
  retryHeaders.set('Accept-Language', currentLocale())
  const nextToken = csrfToken()
  if (nextToken && !SAFE_METHODS.has(method.toLowerCase())) retryHeaders.set(CSRF_HEADER_NAME, nextToken)
  return fetch(input, { ...init, headers: retryHeaders, credentials: 'same-origin' })
}

export const rawAuthTransport = authTransport
