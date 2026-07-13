import { defineStore } from 'pinia'
import { ref } from 'vue'
import { testDataApi } from '@/api'
import type { TestDataItem, TestDataResponse } from '@/types'

export const useTestDataStore = defineStore('testData', () => {
  const testData = ref<TestDataItem[]>([])
  const total = ref(0)
  const loading = ref(false)
  const error = ref<string | null>(null)
  const currentTestType = ref<string>('')
  const currentPage = ref(1)
  const pageSize = ref(20)

  const fetchTestData = async () => {
    loading.value = true
    error.value = null
    try {
      const response = await testDataApi.getTestData({
        page: currentPage.value,
        pageSize: pageSize.value,
        testType: currentTestType.value || undefined
      })
      testData.value = response.data.data || []
      total.value = response.data.total || 0
    } catch (e: any) {
      error.value = e.message || 'Failed to fetch test data'
    } finally {
      loading.value = false
    }
  }

  const setTestType = (type: string) => {
    currentTestType.value = type
    currentPage.value = 1
    fetchTestData()
  }

  const setPage = (page: number) => {
    currentPage.value = page
    fetchTestData()
  }

  return {
    testData,
    total,
    loading,
    error,
    currentTestType,
    currentPage,
    pageSize,
    fetchTestData,
    setTestType,
    setPage
  }
})
