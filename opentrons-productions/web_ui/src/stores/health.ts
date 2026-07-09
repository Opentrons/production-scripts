import { defineStore } from 'pinia'
import { ref } from 'vue'
import { healthApi } from '@/api'
import type { HealthCheckResponse } from '@/types'

export const useHealthStore = defineStore('health', () => {
  const healthData = ref<HealthCheckResponse | null>(null)
  const loading = ref(false)
  const error = ref<string | null>(null)
  const lastUpdateTime = ref<Date | null>(null)

  const fetchHealth = async () => {
    loading.value = true
    error.value = null
    try {
      const response = await healthApi.getHealth()
      healthData.value = response.data
      lastUpdateTime.value = new Date()
    } catch (e: any) {
      error.value = e.message || 'Failed to fetch health status'
    } finally {
      loading.value = false
    }
  }

  return {
    healthData,
    loading,
    error,
    lastUpdateTime,
    fetchHealth
  }
})
