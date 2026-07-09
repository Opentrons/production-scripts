import { defineStore } from 'pinia'
import { ref } from 'vue'
import { robotApi, type RobotScanParams, type RobotScanResponse } from '@/api'

const SCAN_CACHE_KEY = 'data-handler:robot-scan'
const AUTO_REFRESH_INTERVAL_MS = 2 * 60 * 1000

interface CachedRobotScan {
  cached_at: string
  result: RobotScanResponse
}

export const useRobotScanStore = defineStore('robotScan', () => {
  const scanResult = ref<RobotScanResponse | null>(null)
  const scanning = ref(false)
  const backgroundRefreshing = ref(false)
  const lastUpdateTime = ref<Date | null>(null)
  const lastScanParams = ref<RobotScanParams>({})

  let autoRefreshTimer: ReturnType<typeof setInterval> | null = null
  let refreshPromise: Promise<RobotScanResponse | null> | null = null

  function persistToCache(result: RobotScanResponse) {
    const payload: CachedRobotScan = {
      cached_at: new Date().toISOString(),
      result
    }
    try {
      sessionStorage.setItem(SCAN_CACHE_KEY, JSON.stringify(payload))
    } catch {
      // ignore storage errors
    }
  }

  function loadFromCache(): boolean {
    try {
      const raw = sessionStorage.getItem(SCAN_CACHE_KEY)
      if (!raw) return false

      const parsed = JSON.parse(raw) as CachedRobotScan | RobotScanResponse
      if ('result' in parsed && parsed.result) {
        scanResult.value = parsed.result
        lastUpdateTime.value = parsed.cached_at ? new Date(parsed.cached_at) : null
        return true
      }

      if ('online_robots' in parsed) {
        scanResult.value = parsed
        lastUpdateTime.value = null
        persistToCache(parsed)
        return true
      }
    } catch {
      // ignore cache parse errors
    }
    return false
  }

  async function refreshScan(options: { silent?: boolean; params?: RobotScanParams } = {}): Promise<RobotScanResponse | null> {
    if (refreshPromise) {
      return refreshPromise
    }

    const silent = options.silent ?? false
    if (options.params) {
      lastScanParams.value = { ...options.params }
    }

    refreshPromise = (async () => {
      if (silent) {
        if (scanning.value) return scanResult.value
        backgroundRefreshing.value = true
      } else {
        scanning.value = true
      }

      try {
        const response = await robotApi.scanRobots(lastScanParams.value)
        scanResult.value = response.data
        lastUpdateTime.value = new Date()
        persistToCache(response.data)
        return response.data
      } catch (error) {
        if (!silent) {
          throw error
        }
        return scanResult.value
      } finally {
        if (silent) {
          backgroundRefreshing.value = false
        } else {
          scanning.value = false
        }
        refreshPromise = null
      }
    })()

    return refreshPromise
  }

  function startAutoRefresh(intervalMs = AUTO_REFRESH_INTERVAL_MS) {
    stopAutoRefresh()
    autoRefreshTimer = setInterval(() => {
      void refreshScan({ silent: true })
    }, intervalMs)
  }

  function stopAutoRefresh() {
    if (autoRefreshTimer) {
      clearInterval(autoRefreshTimer)
      autoRefreshTimer = null
    }
  }

  return {
    scanResult,
    scanning,
    backgroundRefreshing,
    lastUpdateTime,
    lastScanParams,
    loadFromCache,
    refreshScan,
    startAutoRefresh,
    stopAutoRefresh
  }
})
