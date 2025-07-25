import { defineStore } from 'pinia'
import { ref } from 'vue'
import { loginUser, registerUser } from '../api/auth'
import type { LoginForm, RegisterForm } from '../types/auth'
import { fa } from 'element-plus/es/locales.mjs'
import router from '../router'

export const useAuthStore = defineStore('auth', () => {
  const user = ref(null)
  const isAuthenticated = ref(false)
  const error = ref<string | null>(null)
  const loading = ref(false)

  const login = async (credentials: LoginForm) => {
    try {
      loading.value = true
      error.value = null
      const response = await loginUser(credentials)
      console.log(response)
      user.value = response.user
      if (response.success){
        isAuthenticated.value = true
        localStorage.setItem('token', response.access_token)
        localStorage.setItem('user', response.user)
        return true
      }
      else{
        isAuthenticated.value = false
        return false
      }
    } catch (err) {
      error.value = err.message || '登录失败'
      throw err
    } finally {
      loading.value = false
      
    }
  }

  const register = async (userData: RegisterForm) => {
    try {
      loading.value = true
      error.value = null
      const response = await registerUser(userData)
      user.value = response.user
      isAuthenticated.value = true
      localStorage.setItem('token', response.access_token)
    } catch (err) {
      error.value = err.message || '注册失败'
      throw err
    } finally {
      loading.value = false
    }
  }

  const logout = () => {
    user.value = null
    isAuthenticated.value = false
    localStorage.removeItem('token')
    localStorage.removeItem('user')
    router.push('/login')
  }

  return { user, isAuthenticated, error, loading, login, register, logout }
})