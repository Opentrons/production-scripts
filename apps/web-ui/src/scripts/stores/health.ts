import { defineStore } from 'pinia'
import { ref } from 'vue'
import { healthApi } from '@/scripts/api'
import type { HealthCheckResponse } from '@/scripts/types'

export const useHealthStore = defineStore('health', () => {
  const healthData = ref<HealthCheckResponse | null>(null)
  const loading = ref(false)
  const error = ref<string | null>(null)
  const lastUpdateTime = ref<Date | null>(null)
  let cachedRequest: Promise<void> | null = null
  let refreshRequest: Promise<void> | null = null

  const requestHealth = async (refresh: boolean) => {
    loading.value = true
    error.value = null
    try {
      const response = refresh
        ? await healthApi.refreshHealth()
        : await healthApi.getHealth()
      healthData.value = response.data
      const checkedAt = response.data.checked_at
      const parsed = checkedAt ? new Date(checkedAt) : null
      lastUpdateTime.value = parsed && !Number.isNaN(parsed.getTime()) ? parsed : null
    } catch (e: any) {
      error.value = e.message || 'Failed to fetch health status'
    } finally {
      loading.value = false
    }
  }

  const fetchHealth = () => {
    if (refreshRequest) return refreshRequest
    if (cachedRequest) return cachedRequest
    cachedRequest = requestHealth(false).finally(() => {
      cachedRequest = null
    })
    return cachedRequest
  }

  const refreshHealth = () => {
    if (refreshRequest) return refreshRequest
    refreshRequest = (async () => {
      if (cachedRequest) await cachedRequest
      await requestHealth(true)
    })().finally(() => {
      refreshRequest = null
    })
    return refreshRequest
  }

  return {
    healthData,
    loading,
    error,
    lastUpdateTime,
    fetchHealth,
    refreshHealth
  }
})
