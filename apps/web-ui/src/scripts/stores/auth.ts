import { defineStore } from 'pinia'
import { authApi, type AuthUser } from '@/scripts/api/auth'
import { csrfToken } from '@/scripts/api/http'

interface AuthState {
  user: AuthUser | null
  initialized: boolean
  checking: boolean
}

export const useAuthStore = defineStore('auth', {
  state: (): AuthState => ({
    user: null,
    initialized: false,
    checking: false,
  }),
  getters: {
    authenticated: state => Boolean(state.user),
  },
  actions: {
    async restore(): Promise<boolean> {
      if (this.initialized) return Boolean(this.user)
      if (this.checking) {
        while (this.checking) await new Promise(resolve => window.setTimeout(resolve, 20))
        return Boolean(this.user)
      }
      this.checking = true
      try {
        // The CSRF cookie is intentionally readable and is issued with every
        // authenticated session. Without it there is no session to restore,
        // so avoid blocking navigation on an unnecessary backend request.
        if (!csrfToken()) {
          this.user = null
          return false
        }
        try {
          const { data } = await authApi.me()
          this.user = data.user
        } catch {
          await authApi.refresh()
          const { data } = await authApi.me()
          this.user = data.user
        }
      } catch {
        this.user = null
      } finally {
        this.checking = false
        this.initialized = true
      }
      return Boolean(this.user)
    },
    async login(username: string, password: string): Promise<void> {
      const { data } = await authApi.login(username, password)
      this.user = data.user
      this.initialized = true
    },
    async logout(): Promise<void> {
      try {
        await authApi.logout()
      } finally {
        this.user = null
        this.initialized = true
      }
    },
  },
})
