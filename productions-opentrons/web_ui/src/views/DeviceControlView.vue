<template>
  <div class="device-control-view">
    <section class="device-context" :class="{ 'is-batch': isBatchMode }">
      <template v-if="isBatchMode">
        <div class="device-identity">
          <div class="device-copy">
            <span class="device-name">批量处理</span>
            <span class="device-ip">{{ selectedIps.length }} / {{ availableRobots.length }} 台设备已选择</span>
          </div>
        </div>

        <div class="device-meta">
          <span class="status-pill">多选模式</span>
          <span class="meta-item">{{ availableRobots.length }} 台可选设备</span>
        </div>
      </template>

      <template v-else>
        <div class="device-identity">
          <div class="device-copy">
            <span class="device-name">{{ currentDeviceName }}</span>
            <span class="device-address">
              <span class="inline-status" :class="currentServiceStatus">
                {{ formatServiceStatus(currentServiceStatus) }}
              </span>
              <span class="device-ip">{{ selectedIp || '未选择设备' }}</span>
            </span>
          </div>
        </div>

        <div class="device-meta">
          <el-tooltip content="设备信息" placement="left">
            <el-button
              :icon="Tickets"
              circle
              :disabled="!selectedIp"
              @click="openInfoDrawer"
            />
          </el-tooltip>
          <el-tooltip content="刷新状态" placement="left">
            <el-button
              :icon="Refresh"
              :loading="refreshing"
              circle
              @click="refreshRobots"
            />
          </el-tooltip>
        </div>
      </template>
    </section>

    <section class="workbench">
      <el-tabs v-model="activeTab" class="workbench-tabs" @tab-change="handleTabChange">
        <el-tab-pane label="设备控制" name="control">
          <DeviceControlPanel :ip="selectedIp" />
        </el-tab-pane>

        <el-tab-pane label="Protocol" name="protocol">
          <DeviceProtocolsPanel :ip="selectedIp" standalone />
        </el-tab-pane>

        <el-tab-pane label="文件管理" name="files">
          <DeviceFilesPanel :ip="selectedIp" />
        </el-tab-pane>

        <el-tab-pane label="执行命令" name="command">
          <section class="command-console">
            <div v-if="!selectedIp" class="panel-empty">
              <el-empty description="请先选择一台设备" />
            </div>

            <template v-else>
              <div class="command-form-grid">
                <label class="command-field">
                  <span>方法</span>
                  <el-select v-model="singleCommandMethod">
                    <el-option label="GET" value="GET" />
                    <el-option label="POST" value="POST" />
                    <el-option label="PUT" value="PUT" />
                    <el-option label="DELETE" value="DELETE" />
                  </el-select>
                </label>
                <label class="command-field">
                  <span>OpenAPI Path</span>
                  <el-input v-model="singleCommandPath" placeholder="/health" />
                </label>
              </div>

              <label class="command-field">
                <span>Body JSON</span>
                <el-input
                  v-model="singleCommandBody"
                  type="textarea"
                  :rows="8"
                  placeholder='{"data": {}}'
                />
              </label>

              <div class="command-actions-row">
                <el-button
                  type="primary"
                  :loading="singleCommandRunning"
                  :disabled="!canRunSingleCommand"
                  @click="runSingleCommand"
                >
                  执行
                </el-button>
                <el-button
                  v-if="singleCommandResult"
                  :disabled="singleCommandRunning"
                  @click="singleCommandResult = null"
                >
                  清空结果
                </el-button>
              </div>

              <div
                v-if="singleCommandResult"
                class="command-result"
                :class="{ 'is-error': !singleCommandResult.success }"
              >
                <div class="command-result-header">
                  <span>{{ singleCommandResult.method }} {{ singleCommandResult.path }}</span>
                  <el-tag size="small" :type="singleCommandResult.success ? 'success' : 'danger'">
                    {{ singleCommandResult.success ? '成功' : '失败' }}
                  </el-tag>
                </div>
                <pre class="command-result-body">{{ singleCommandResultText }}</pre>
              </div>
            </template>
          </section>
        </el-tab-pane>

        <el-tab-pane label="批量处理" name="batch">
          <div class="batch-workspace">
            <aside class="batch-device-panel">
              <div class="batch-panel-header">
                <span class="panel-title">目标设备</span>
                <span class="device-count">{{ availableRobots.length }}</span>
                <el-button
                  type="primary"
                  size="small"
                  link
                  @click="toggleSelectAll"
                >
                  {{ isAllSelected ? '取消全选' : '全选' }}
                </el-button>
              </div>

              <div class="manual-ip">
                <el-input
                  v-model="manualIpInput"
                  placeholder="输入 IP 后回车"
                  size="small"
                  @keyup.enter="addManualIp"
                />
                <el-button size="small" type="primary" @click="addManualIp">添加</el-button>
              </div>

              <el-checkbox-group
                v-if="availableRobots.length"
                v-model="selectedIps"
                class="batch-device-list"
              >
                <el-checkbox
                  v-for="robot in availableRobots"
                  :key="robot.ip"
                  :value="robot.ip"
                  class="batch-device-option"
                >
                  <span class="batch-device-name">{{ robot.name || '未命名设备' }}</span>
                  <span class="batch-device-ip">{{ robot.ip }}</span>
                  <span class="batch-device-status" :class="robot.service_status">
                    {{ formatServiceStatus(robot.service_status) }}
                  </span>
                </el-checkbox>
              </el-checkbox-group>

              <el-empty v-else description="暂无设备" :image-size="72" />
            </aside>

            <section class="batch-command-panel">
              <div class="batch-topbar">
                <div class="batch-summary">
                  <span class="summary-value">{{ selectedIps.length }}</span>
                  <span class="summary-label">台设备已选择</span>
                </div>
                <el-button
                  v-if="batchResults.length"
                  size="small"
                  text
                  @click="batchResults = []"
                >
                  清空结果
                </el-button>
              </div>

              <el-tabs v-model="batchActionTab" class="batch-action-tabs">
                <el-tab-pane label="改文件" name="edit">
                  <div class="batch-form-grid">
                    <label class="batch-field">
                      <span>参考设备</span>
                      <el-select v-model="batchReferenceIp" placeholder="选择要读取的设备">
                        <el-option
                          v-for="robot in selectedRobots"
                          :key="`ref-${robot.ip}`"
                          :label="`${robot.name || robot.ip} · ${robot.ip}`"
                          :value="robot.ip"
                        />
                      </el-select>
                    </label>
                    <label class="batch-field">
                      <span>文件路径</span>
                      <el-input v-model="batchEditPath" placeholder="/data/file.json" />
                    </label>
                  </div>
                  <div class="batch-actions-row">
                    <el-button :loading="batchReading" :disabled="!canReadBatchFile" @click="readBatchFile">
                      打开文件
                    </el-button>
                    <el-button
                      type="primary"
                      :loading="batchRunning"
                      :disabled="!canWriteBatchFile"
                      @click="runBatchEditReplace"
                    >
                      保存并批量替换
                    </el-button>
                  </div>
                  <el-input
                    v-model="batchEditContent"
                    class="batch-editor"
                    type="textarea"
                    :rows="14"
                    placeholder="先从参考设备打开文件，编辑后保存到选中的设备"
                  />
                </el-tab-pane>

                <el-tab-pane label="传文件" name="upload">
                  <div class="batch-form-grid">
                    <label class="batch-field">
                      <span>目标路径</span>
                      <el-input v-model="batchUploadPath" placeholder="/data/config.json" />
                    </label>
                    <label class="batch-field">
                      <span>本地文件</span>
                      <input class="native-file-input" type="file" @change="handleBatchUploadFileChange" />
                    </label>
                  </div>
                  <div class="batch-actions-row">
                    <el-button
                      type="primary"
                      :loading="batchRunning"
                      :disabled="!canBatchUpload"
                      @click="runBatchUpload"
                    >
                      批量上传
                    </el-button>
                  </div>
                </el-tab-pane>

                <el-tab-pane label="下载文件" name="download">
                  <div class="batch-form-grid">
                    <label class="batch-field">
                      <span>远程路径</span>
                      <el-input v-model="batchDownloadPath" placeholder="/data 或 /data/file.csv" />
                    </label>
                  </div>
                  <div class="batch-actions-row">
                    <el-button
                      type="primary"
                      :loading="batchRunning"
                      :disabled="!canBatchDownload"
                      @click="runBatchDownload"
                    >
                      批量下载
                    </el-button>
                  </div>
                </el-tab-pane>

                <el-tab-pane label="执行命令" name="command">
                  <div class="batch-form-grid">
                    <label class="batch-field">
                      <span>方法</span>
                      <el-select v-model="batchCommandMethod">
                        <el-option label="GET" value="GET" />
                        <el-option label="POST" value="POST" />
                        <el-option label="PUT" value="PUT" />
                        <el-option label="DELETE" value="DELETE" />
                      </el-select>
                    </label>
                    <label class="batch-field">
                      <span>OpenAPI Path</span>
                      <el-input v-model="batchCommandPath" placeholder="/health" />
                    </label>
                  </div>
                  <label class="batch-field">
                    <span>Body JSON</span>
                    <el-input
                      v-model="batchCommandBody"
                      type="textarea"
                      :rows="8"
                      placeholder='{"data": {}}'
                    />
                  </label>
                  <div class="batch-actions-row">
                    <el-button
                      type="primary"
                      :loading="batchRunning"
                      :disabled="!canBatchCommand"
                      @click="runBatchCommand"
                    >
                      批量执行
                    </el-button>
                  </div>
                </el-tab-pane>
              </el-tabs>

              <div v-if="batchResults.length" class="batch-result-list">
                <article
                  v-for="result in batchResults"
                  :key="`${result.startedAt}-${result.ip}-${result.action}`"
                  class="batch-result-item"
                  :class="result.status"
                >
                  <div>
                    <div class="result-title">{{ result.ip }} · {{ result.action }}</div>
                    <div class="result-message">{{ result.message }}</div>
                  </div>
                  <el-tag size="small" :type="getBatchResultTagType(result.status)">
                    {{ getBatchResultStatusLabel(result.status) }}
                  </el-tag>
                </article>
              </div>
            </section>
          </div>
        </el-tab-pane>
      </el-tabs>
    </section>

    <el-drawer
      v-model="infoDrawerVisible"
      :title="infoDrawerTitle"
      direction="rtl"
      size="420px"
    >
      <DeviceInfoPanel
        v-if="infoDrawerVisible"
        ref="infoPanelRef"
        :ip="selectedIp"
        in-drawer
        :show-header="false"
      />
      <template #footer>
        <el-button @click="infoDrawerVisible = false">关闭</el-button>
        <el-button type="primary" @click="refreshDeviceInfo">刷新</el-button>
      </template>
    </el-drawer>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { Refresh, Tickets } from '@element-plus/icons-vue'
import { ElMessage } from 'element-plus'
import { robotApi, type RobotInfo } from '@/api'
import { useRobotScanStore } from '@/stores/robotScan'
import DeviceControlPanel from '@/components/device/DeviceControlPanel.vue'
import DeviceProtocolsPanel from '@/components/device/DeviceProtocolsPanel.vue'
import DeviceFilesPanel from '@/components/device/DeviceFilesPanel.vue'
import DeviceInfoPanel from '@/components/device/DeviceInfoPanel.vue'

const route = useRoute()
const router = useRouter()
const robotScanStore = useRobotScanStore()

const activeTab = ref('control')
const manualIpInput = ref('')
const selectedIp = ref<string | null>(null)
const selectedIps = ref<string[]>([])
const availableRobots = ref<RobotInfo[]>([])
const refreshing = ref(false)
const infoDrawerVisible = ref(false)
const infoPanelRef = ref<InstanceType<typeof DeviceInfoPanel> | null>(null)
const batchActionTab = ref('edit')
const batchReferenceIp = ref('')
const batchEditPath = ref('')
const batchEditContent = ref('')
const batchReading = ref(false)
const batchRunning = ref(false)
const batchUploadPath = ref('')
const batchUploadFile = ref<File | null>(null)
const batchDownloadPath = ref('')
const batchCommandMethod = ref('GET')
const batchCommandPath = ref('/health')
const batchCommandBody = ref('')
const batchResults = ref<BatchOperationResult[]>([])
const singleCommandMethod = ref('GET')
const singleCommandPath = ref('/health')
const singleCommandBody = ref('')
const singleCommandRunning = ref(false)
const singleCommandResult = ref<SingleCommandResult | null>(null)

interface BatchOperationResult {
  ip: string
  action: string
  status: 'success' | 'failed' | 'skipped'
  message: string
  startedAt: number
}

type BatchOperationStatus = BatchOperationResult['status']

interface SingleCommandResult {
  method: string
  path: string
  success: boolean
  statusCode?: number
  response?: unknown
  error?: string
}

const isBatchMode = computed(() => activeTab.value === 'batch')

const isAllSelected = computed(() => {
  if (availableRobots.value.length === 0) return false
  return availableRobots.value.every(robot => selectedIps.value.includes(robot.ip))
})

const initialIp = computed(() => {
  const ip = route.query.ip
  return typeof ip === 'string' ? ip : ''
})

const initialMode = computed(() => {
  const mode = route.query.mode
  return typeof mode === 'string' ? mode : ''
})

const currentDevice = computed(() => {
  if (!selectedIp.value) return null
  return availableRobots.value.find(robot => robot.ip === selectedIp.value) ?? null
})

const currentDeviceName = computed(() => {
  return currentDevice.value?.name?.trim() || '未命名设备'
})

const currentServiceStatus = computed<RobotInfo['service_status']>(() => {
  return currentDevice.value?.service_status ?? 'unknown'
})

const selectedRobots = computed(() => {
  return selectedIps.value.map(ip => availableRobots.value.find(robot => robot.ip === ip) ?? {
    ip,
    port: 31950,
    online: true,
    service_status: 'unknown' as const
  })
})

const canReadBatchFile = computed(() => Boolean(batchReferenceIp.value && batchEditPath.value.trim()))
const canWriteBatchFile = computed(() => selectedIps.value.length > 0 && Boolean(batchEditPath.value.trim()))
const canBatchUpload = computed(() => selectedIps.value.length > 0 && Boolean(batchUploadPath.value.trim() && batchUploadFile.value))
const canBatchDownload = computed(() => selectedIps.value.length > 0 && Boolean(batchDownloadPath.value.trim()))
const canBatchCommand = computed(() => selectedIps.value.length > 0 && Boolean(batchCommandMethod.value && batchCommandPath.value.trim()))
const canRunSingleCommand = computed(() => Boolean(selectedIp.value && singleCommandMethod.value && singleCommandPath.value.trim()))

const singleCommandResultText = computed(() => {
  if (!singleCommandResult.value) return ''
  return JSON.stringify({
    status_code: singleCommandResult.value.statusCode,
    error: singleCommandResult.value.error,
    response: singleCommandResult.value.response
  }, null, 2)
})

const infoDrawerTitle = computed(() => {
  return selectedIp.value ? `设备信息 - ${selectedIp.value}` : '设备信息'
})

function syncRobotsFromStore() {
  const robots = robotScanStore.scanResult?.online_robots ?? []
  if (robots.length) {
    const manualOnly = availableRobots.value.filter(robot => {
      return !robots.some(scannedRobot => scannedRobot.ip === robot.ip)
    })
    availableRobots.value = [...robots, ...manualOnly]
  }
}

async function loadScanCache() {
  if (!robotScanStore.scanResult) {
    try {
      await robotScanStore.loadCachedScan()
    } catch {
      robotScanStore.loadFromCache()
    }
  }
  syncRobotsFromStore()
}

function ensureRobotInList(ip: string) {
  if (!availableRobots.value.some(robot => robot.ip === ip)) {
    availableRobots.value.push({
      ip,
      port: 31950,
      online: true,
      service_status: 'unknown'
    })
  }
}

function selectFallbackDevice() {
  if (selectedIp.value && availableRobots.value.some(robot => robot.ip === selectedIp.value)) return
  selectedIp.value = availableRobots.value[0]?.ip ?? null
}

function addManualIp() {
  const ip = manualIpInput.value.trim()
  if (!ip) return
  ensureRobotInList(ip)
  if (isBatchMode.value && !selectedIps.value.includes(ip)) {
    selectedIps.value.push(ip)
  }
  selectedIp.value = ip
  manualIpInput.value = ''
}

function toggleSelectAll() {
  if (isAllSelected.value) {
    selectedIps.value = []
    return
  }
  selectedIps.value = availableRobots.value.map(robot => robot.ip)
}

function recordBatchResult(result: Omit<BatchOperationResult, 'startedAt'>) {
  batchResults.value.unshift({
    ...result,
    startedAt: Date.now()
  })
}

function getBatchResultTagType(status: BatchOperationStatus) {
  if (status === 'success') return 'success'
  if (status === 'skipped') return 'info'
  return 'danger'
}

function getBatchResultStatusLabel(status: BatchOperationStatus) {
  if (status === 'success') return '成功'
  if (status === 'skipped') return '跳过'
  return '失败'
}

function normalizeError(error: any): string {
  return error?.response?.data?.detail?.message
    || error?.response?.data?.detail?.error
    || error?.response?.data?.message
    || error?.message
    || '未知错误'
}

async function runForSelectedDevices(action: string, runner: (ip: string) => Promise<string>) {
  if (selectedIps.value.length === 0) {
    ElMessage.warning('请先选择设备')
    return
  }
  batchRunning.value = true
  let success = 0
  let failed = 0
  let skipped = 0
  try {
    for (const ip of selectedIps.value) {
      try {
        const message = await runner(ip)
        success += 1
        recordBatchResult({ ip, action, status: 'success', message })
      } catch (error: any) {
        if (error?.skipped) {
          skipped += 1
          recordBatchResult({ ip, action, status: 'skipped', message: error.message })
          continue
        }
        failed += 1
        recordBatchResult({ ip, action, status: 'failed', message: normalizeError(error) })
      }
    }
    if (failed > 0) {
      ElMessage.warning(`${action} 完成：成功 ${success}，跳过 ${skipped}，失败 ${failed}`)
    } else if (skipped > 0) {
      ElMessage.warning(`${action} 完成：成功 ${success}，跳过 ${skipped}`)
    } else {
      ElMessage.success(`${action} 完成：成功 ${success}`)
    }
  } finally {
    batchRunning.value = false
  }
}

function buildSkippedBatchOperation(message: string) {
  const error = new Error(message) as Error & { skipped: true }
  error.skipped = true
  return error
}

async function readBatchFile() {
  if (!canReadBatchFile.value) return
  batchReading.value = true
  try {
    const response = await robotApi.readFile(batchReferenceIp.value, batchEditPath.value.trim())
    batchEditContent.value = response.data.content
    ElMessage.success('文件已打开')
  } catch (error: any) {
    ElMessage.error('打开文件失败: ' + normalizeError(error))
  } finally {
    batchReading.value = false
  }
}

async function runBatchEditReplace() {
  const path = batchEditPath.value.trim()
  if (!path) return
  await runForSelectedDevices('批量替换文件', async (ip) => {
    const response = await robotApi.writeFile(ip, path, batchEditContent.value, { createIfMissing: false })
    if (response.data.data?.skipped) {
      throw buildSkippedBatchOperation(`目标文件不存在，已跳过 ${path}`)
    }
    return `已写入 ${path}`
  })
}

function handleBatchUploadFileChange(event: Event) {
  const input = event.target as HTMLInputElement
  batchUploadFile.value = input.files?.[0] ?? null
}

async function runBatchUpload() {
  const file = batchUploadFile.value
  const path = batchUploadPath.value.trim()
  if (!file || !path) return
  await runForSelectedDevices('批量上传文件', async (ip) => {
    await robotApi.uploadFile(ip, path, file)
    return `已上传到 ${path}`
  })
}

function parseDownloadFilename(contentDisposition: string | undefined, fallbackName: string): string {
  if (!contentDisposition) return fallbackName
  const match = contentDisposition.match(/filename="([^"]+)"/i)
  return match?.[1] ?? fallbackName
}

function saveBlob(blob: Blob, filename: string) {
  const url = URL.createObjectURL(blob)
  const anchor = document.createElement('a')
  anchor.href = url
  anchor.download = filename
  anchor.click()
  URL.revokeObjectURL(url)
}

function basename(path: string): string {
  return path.replace(/\/+$/, '').split('/').filter(Boolean).pop() || 'download'
}

async function runBatchDownload() {
  const path = batchDownloadPath.value.trim()
  if (!path) return
  await runForSelectedDevices('批量下载文件', async (ip) => {
    const response = await robotApi.downloadFile(ip, path)
    const fallbackName = `${ip.replace(/\./g, '-')}-${basename(path)}`
    const filename = parseDownloadFilename(response.headers['content-disposition'], fallbackName)
    saveBlob(response.data, filename)
    return `已下载 ${path}`
  })
}

function parseCommandBody(text: string): Record<string, unknown> | undefined {
  const trimmed = text.trim()
  if (!trimmed) return undefined
  const parsed = JSON.parse(trimmed)
  if (!parsed || typeof parsed !== 'object' || Array.isArray(parsed)) {
    throw new Error('Body JSON 必须是对象')
  }
  return parsed as Record<string, unknown>
}

async function runSingleCommand() {
  if (!selectedIp.value) return
  let body: Record<string, unknown> | undefined
  try {
    body = parseCommandBody(singleCommandBody.value)
  } catch (error: any) {
    ElMessage.error(error.message || 'Body JSON 格式错误')
    return
  }

  const method = singleCommandMethod.value
  const path = singleCommandPath.value.trim()
  singleCommandRunning.value = true
  singleCommandResult.value = null
  try {
    const response = await robotApi.executeCommands({
      ips: [selectedIp.value],
      method,
      path,
      body,
      timeout: 30
    })
    const result = response.data.results?.[0]
    singleCommandResult.value = {
      method,
      path,
      success: Boolean(result?.success),
      statusCode: result?.status_code,
      response: result?.response,
      error: result?.error
    }
    if (result?.success) {
      ElMessage.success('命令执行成功')
    } else {
      ElMessage.error(result?.error || '命令执行失败')
    }
  } catch (error: any) {
    singleCommandResult.value = {
      method,
      path,
      success: false,
      error: normalizeError(error)
    }
    ElMessage.error('命令执行失败: ' + normalizeError(error))
  } finally {
    singleCommandRunning.value = false
  }
}

async function runBatchCommand() {
  let body: Record<string, unknown> | undefined
  try {
    body = parseCommandBody(batchCommandBody.value)
  } catch (error: any) {
    ElMessage.error(error.message || 'Body JSON 格式错误')
    return
  }

  const path = batchCommandPath.value.trim()
  await runForSelectedDevices('批量执行命令', async (ip) => {
    const response = await robotApi.executeCommands({
      ips: [ip],
      method: batchCommandMethod.value,
      path,
      body,
      timeout: 30
    })
    const result = response.data.results?.[0]
    if (!result?.success) {
      throw new Error(result?.error || `HTTP ${result?.status_code || '失败'}`)
    }
    return `命令已执行 ${batchCommandMethod.value} ${path}`
  })
}

async function refreshRobots() {
  refreshing.value = true
  try {
    await robotScanStore.refreshScan({ silent: false })
    syncRobotsFromStore()
    selectFallbackDevice()
  } catch (error: any) {
    ElMessage.error('刷新设备失败: ' + (error.message || '未知错误'))
  } finally {
    refreshing.value = false
  }
}

function openInfoDrawer() {
  if (!selectedIp.value) return
  infoDrawerVisible.value = true
}

function refreshDeviceInfo() {
  infoPanelRef.value?.refresh()
}

function handleTabChange(tabName: string | number) {
  if (tabName === 'batch') {
    if (selectedIp.value && !selectedIps.value.includes(selectedIp.value)) {
      selectedIps.value = [selectedIp.value]
    }
    if (!batchReferenceIp.value) {
      batchReferenceIp.value = selectedIps.value[0] ?? ''
    }
    return
  }

  if (!selectedIp.value) {
    selectedIp.value = selectedIps.value[0] ?? availableRobots.value[0]?.ip ?? null
  }
}

function formatServiceStatus(status: RobotInfo['service_status']) {
  const statusMap: Record<RobotInfo['service_status'], string> = {
    normal: '正常',
    error: '异常',
    unknown: '未知'
  }
  return statusMap[status] || '未知'
}

watch(selectedIp, (ip) => {
  if (ip && selectedIps.value.length === 0) {
    selectedIps.value = [ip]
  }
})

watch(selectedIps, (ips) => {
  if (!ips.includes(batchReferenceIp.value)) {
    batchReferenceIp.value = ips[0] ?? ''
  }
})

onMounted(async () => {
  await loadScanCache()
  if (initialMode.value === 'batch') {
    activeTab.value = 'batch'
  }
  if (initialIp.value) {
    ensureRobotInList(initialIp.value)
    selectedIp.value = initialIp.value
  } else {
    selectFallbackDevice()
  }

  if (selectedIp.value && selectedIps.value.length === 0) {
    selectedIps.value = [selectedIp.value]
  }
})
</script>

<style scoped>
.device-control-view {
  --console-text: #1f2a37;
  --console-muted: #6b7280;
  --console-border: #e6ebf2;
  --console-soft: #f7f9fc;
  --console-active: #f2f7ff;
  height: 100%;
  display: flex;
  flex-direction: column;
  padding: 0 20px 0;
  background: #fff;
  color: var(--console-text);
  text-align: left;
}

.device-context {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 18px;
  min-height: 64px;
  padding: 10px 0;
  border-bottom: 1px solid var(--console-border);
}

.device-context.is-batch {
  background: linear-gradient(180deg, rgba(247, 249, 252, 0.68), rgba(255, 255, 255, 0));
}

.device-identity,
.device-meta {
  display: flex;
  align-items: center;
  min-width: 0;
}

.device-identity {
  gap: 12px;
}

.device-copy {
  display: grid;
  gap: 3px;
  min-width: 0;
}

.device-name {
  overflow: hidden;
  color: var(--console-text);
  font-size: 15px;
  font-weight: 650;
  line-height: 1.2;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.device-address,
.device-ip,
.meta-item {
  color: var(--console-muted);
  font-size: 12px;
  line-height: 1.3;
}

.device-address {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  min-width: 0;
}

.device-ip {
  overflow: hidden;
  font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.device-meta {
  gap: 8px;
  flex-wrap: wrap;
  justify-content: flex-end;
}

.inline-status {
  color: #64748b;
  font-size: 12px;
  font-weight: 650;
  line-height: 1.3;
}

.inline-status.normal {
  color: #16803c;
}

.inline-status.error {
  color: #c24141;
}

.status-pill,
.device-count {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  min-width: 24px;
  height: 24px;
  padding: 0 8px;
  border-radius: 999px;
  background: #eef2f7;
  color: #64748b;
  font-size: 12px;
  line-height: 1;
}

.status-pill.normal {
  background: #ecfdf3;
  color: #16803c;
}

.status-pill.error {
  background: #fef2f2;
  color: #c24141;
}

.workbench {
  flex: 1;
  min-height: 0;
  overflow: hidden;
}

.workbench-tabs {
  height: 100%;
  display: flex;
  flex-direction: column;
}

.workbench-tabs :deep(.el-tabs__header) {
  margin: 0;
}

.workbench-tabs :deep(.el-tabs__content) {
  flex: 1;
  min-height: 0;
  overflow: auto;
  padding-top: 14px;
}

.workbench-tabs :deep(.el-tab-pane) {
  min-height: 100%;
}

.panel-empty {
  min-height: 320px;
  display: flex;
  align-items: center;
  justify-content: center;
}

.command-console {
  max-width: 860px;
}

.command-form-grid {
  display: grid;
  grid-template-columns: 180px minmax(0, 1fr);
  gap: 12px;
  margin-bottom: 12px;
}

.command-field {
  display: grid;
  gap: 7px;
  min-width: 0;
  color: var(--console-muted);
  font-size: 12px;
  font-weight: 600;
}

.command-actions-row {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  margin: 12px 0;
}

.command-result {
  margin-top: 16px;
  border: 1px solid #d9eadf;
  border-radius: 6px;
  background: #f7fcf9;
  overflow: hidden;
}

.command-result.is-error {
  border-color: #f4cccc;
  background: #fff8f8;
}

.command-result-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  padding: 10px 12px;
  border-bottom: 1px solid #e6ebf2;
  color: var(--console-text);
  font-size: 13px;
  font-weight: 650;
}

.command-result-body {
  max-height: 420px;
  margin: 0;
  padding: 12px;
  overflow: auto;
  color: #1f2a37;
  font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace;
  font-size: 12px;
  line-height: 1.5;
  white-space: pre-wrap;
  word-break: break-word;
}

.batch-workspace {
  min-height: 520px;
  display: grid;
  grid-template-columns: 292px minmax(0, 1fr);
  border-top: 1px solid var(--console-border);
}

.batch-device-panel {
  min-width: 0;
  padding: 14px 14px 14px 0;
  border-right: 1px solid var(--console-border);
  overflow-y: auto;
}

.batch-command-panel {
  min-width: 0;
  padding: 14px 0 14px 18px;
}

.batch-topbar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
}

.batch-panel-header {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 12px;
}

.panel-title {
  color: var(--console-text);
  font-size: 14px;
  font-weight: 650;
}

.device-count {
  margin-left: auto;
}

.manual-ip {
  display: flex;
  gap: 8px;
  margin-bottom: 12px;
}

.batch-device-list {
  display: grid;
  gap: 4px;
  width: 100%;
}

.batch-device-list :deep(.el-checkbox) {
  width: 100%;
  height: auto;
  margin: 0;
  padding: 9px 10px;
  border: 1px solid transparent;
  border-radius: 6px;
  transition: background-color 0.18s ease, border-color 0.18s ease;
}

.batch-device-list :deep(.el-checkbox:hover),
.batch-device-list :deep(.el-checkbox.is-checked) {
  border-color: #d7e6fb;
  background: var(--console-active);
}

.batch-device-list :deep(.el-checkbox__label) {
  min-width: 0;
  display: grid;
  grid-template-columns: minmax(0, 1fr) auto;
  gap: 4px 10px;
  padding-left: 8px;
}

.batch-device-name {
  overflow: hidden;
  color: var(--console-text);
  font-size: 14px;
  font-weight: 600;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.batch-device-ip {
  grid-column: 1 / 2;
  overflow: hidden;
  color: var(--console-muted);
  font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace;
  font-size: 12px;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.batch-device-status {
  grid-row: 1 / 3;
  grid-column: 2 / 3;
  align-self: center;
  padding: 2px 7px;
  border-radius: 999px;
  background: #eef2f7;
  color: #64748b;
  font-size: 12px;
}

.batch-device-status.normal {
  background: #ecfdf3;
  color: #16803c;
}

.batch-device-status.error {
  background: #fef2f2;
  color: #c24141;
}

.batch-summary {
  display: inline-flex;
  align-items: baseline;
  gap: 8px;
  margin-bottom: 18px;
}

.summary-value {
  color: var(--console-text);
  font-size: 28px;
  font-weight: 700;
  line-height: 1;
}

.summary-label {
  color: var(--console-muted);
  font-size: 13px;
}

.batch-action-tabs :deep(.el-tabs__header) {
  margin-bottom: 14px;
}

.batch-form-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 12px;
  margin-bottom: 12px;
}

.batch-field {
  display: grid;
  gap: 7px;
  min-width: 0;
  color: var(--console-muted);
  font-size: 12px;
  font-weight: 600;
}

.batch-actions-row {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  margin: 12px 0;
}

.batch-editor {
  margin-top: 8px;
}

.native-file-input {
  min-height: 32px;
  padding: 4px 0;
  color: var(--console-muted);
  font-size: 13px;
}

.batch-result-list {
  display: grid;
  gap: 8px;
  margin-top: 18px;
  padding-top: 14px;
  border-top: 1px solid var(--console-border);
}

.batch-result-item {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  padding: 10px 0;
  border-bottom: 1px solid #eef2f7;
}

.batch-result-item:last-child {
  border-bottom: 0;
}

.result-title {
  color: var(--console-text);
  font-size: 13px;
  font-weight: 650;
}

.result-message {
  margin-top: 3px;
  color: var(--console-muted);
  font-size: 12px;
  word-break: break-word;
}

@media (max-width: 900px) {
  .device-control-view {
    padding: 0 14px;
  }

  .device-context {
    align-items: flex-start;
    flex-direction: column;
  }

  .device-meta {
    justify-content: flex-start;
  }

  .batch-workspace {
    grid-template-columns: 1fr;
  }

  .batch-device-panel {
    padding-right: 0;
    border-right: none;
    border-bottom: 1px solid var(--console-border);
  }

  .batch-command-panel {
    padding-left: 0;
  }

  .batch-form-grid {
    grid-template-columns: 1fr;
  }

  .command-form-grid {
    grid-template-columns: 1fr;
  }
}
</style>
