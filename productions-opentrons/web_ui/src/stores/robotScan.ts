import { defineStore } from 'pinia'
import { ref } from 'vue'
import { robotApi, type RobotScanParams, type RobotScanResponse } from '@/api'

const SCAN_CACHE_KEY = 'data-handler:robot-scan'
const REFRESH_POLL_INTERVAL_MS = 1000
const REFRESH_WAIT_TIMEOUT_MS = 150 * 1000

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

  let refreshPromise: Promise<RobotScanResponse | null> | null = null

  function applyScanResult(result: RobotScanResponse) {
    scanResult.value = result
    lastUpdateTime.value = result.cached_at ? new Date(result.cached_at) : null
    persistToCache(result)
  }

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
        const result = parsed.result.cached_at
          ? parsed.result
          : { ...parsed.result, cached_at: parsed.cached_at }
        applyScanResult(result)
        return true
      }

      if ('online_robots' in parsed) {
        applyScanResult(parsed)
        return true
      }
    } catch {
      // ignore cache parse errors
    }
    return false
  }

  async function loadCachedScan(params?: RobotScanParams): Promise<RobotScanResponse | null> {
    if (params) {
      lastScanParams.value = { ...params }
    }
    try {
      const response = await robotApi.getRobots(lastScanParams.value)
      applyScanResult(response.data)
      return response.data
    } catch (error) {
      if (scanResult.value || loadFromCache()) {
        return scanResult.value
      }
      throw error
    }
  }

  function wait(milliseconds: number) {
    return new Promise(resolve => window.setTimeout(resolve, milliseconds))
  }

  async function waitForRefresh(previousCachedAt?: string | null): Promise<RobotScanResponse | null> {
    const deadline = Date.now() + REFRESH_WAIT_TIMEOUT_MS
    while (Date.now() < deadline) {
      await wait(REFRESH_POLL_INTERVAL_MS)
      const response = await robotApi.getRobots(lastScanParams.value)
      applyScanResult(response.data)
      if (!response.data.refreshing) {
        if (response.data.last_error && response.data.cached_at === previousCachedAt) {
          throw new Error(response.data.last_error)
        }
        return response.data
      }
    }
    throw new Error('后台设备扫描仍在运行，请稍后再试')
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
        const previousCachedAt = scanResult.value?.cached_at ?? null
        const response = await robotApi.scanRobots(lastScanParams.value)
        applyScanResult(response.data)
        if (response.data.refreshing) {
          return await waitForRefresh(previousCachedAt)
        }
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

  return {
    scanResult,
    scanning,
    backgroundRefreshing,
    lastUpdateTime,
    lastScanParams,
    loadFromCache,
    loadCachedScan,
    refreshScan,
  }
})
