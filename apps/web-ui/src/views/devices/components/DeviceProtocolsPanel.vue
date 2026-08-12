<template>
  <div v-loading="loading" class="device-protocols-panel" :class="{ 'is-standalone': standalone }">
    <div v-if="!ip" class="panel-empty">
      <el-empty :description="t('devices.selectOne')" />
    </div>

    <template v-else>
      <div class="protocol-toolbar">
        <div class="title-group">
          <span class="section-title">{{ t('devices.protocols.workspace') }}</span>
          <div class="protocol-switch">
            <button
              class="switch-button"
              :class="{ 'is-active': activePanel === 'protocols' }"
              type="button"
              @click="activePanel = 'protocols'"
            >
              {{ t('devices.protocols.deviceProtocols') }}
              <span>{{ protocols.length }}</span>
            </button>
            <button
              class="switch-button"
              :class="{ 'is-active': activePanel === 'runs' }"
              type="button"
              @click="activePanel = 'runs'"
            >
              {{ t('devices.protocols.runHistory') }}
              <span>{{ runs.length }}</span>
            </button>
          </div>
        </div>
        <div class="header-actions">
          <el-upload
            :auto-upload="false"
            :show-file-list="false"
            multiple
            accept=".py,.json,.zip"
            :on-change="handleUploadChange"
          >
            <el-button type="primary" :icon="Upload" :loading="uploading" :disabled="!ip">
              {{ t('devices.protocols.upload') }}
            </el-button>
          </el-upload>
          <el-tooltip :content="t('common.actions.refresh')" placement="top">
            <el-button :icon="Refresh" circle :disabled="!ip" :loading="loading" @click="refreshAll" />
          </el-tooltip>
        </div>
      </div>

      <div class="protocol-workspace">
        <template v-if="activePanel === 'protocols'">
          <div v-if="protocols.length" class="protocol-list">
            <article
              v-for="protocol in protocols"
              :key="String(protocol.id)"
              class="protocol-item"
            >
              <div class="protocol-icon">
                <el-icon><Document /></el-icon>
              </div>
              <div class="protocol-info">
                <div class="protocol-name">{{ protocolDisplayName(protocol) }}</div>
                <div class="protocol-meta">
                  <span>{{ String(protocol.protocolType || 'protocol') }}</span>
                  <span>{{ formatTime(protocol.createdAt) }}</span>
                  <span class="protocol-id">{{ compactId(protocol.id) }}</span>
                </div>
              </div>
              <div class="protocol-actions">
                <el-dropdown
                  trigger="click"
                  @command="(format: 'json' | 'source') => downloadProtocol(String(protocol.id), format)"
                >
                  <el-button :icon="Download" circle :disabled="!protocol.id" />
                  <template #dropdown>
                    <el-dropdown-menu>
                      <el-dropdown-item command="source">
                        {{ t('devices.protocols.downloadSource') }}
                      </el-dropdown-item>
                      <el-dropdown-item command="json">
                        {{ t('devices.protocols.downloadJson') }}
                      </el-dropdown-item>
                    </el-dropdown-menu>
                  </template>
                </el-dropdown>
                <el-tooltip :content="t('devices.protocols.analyze')" placement="top">
                  <el-button
                    :icon="DataAnalysis"
                    circle
                    :disabled="!protocol.id"
                    @click="analyzeProtocol(String(protocol.id))"
                  />
                </el-tooltip>
                <el-tooltip :content="t('devices.protocols.execute')" placement="top">
                  <el-button
                    :icon="SwitchButton"
                    circle
                    type="success"
                    :disabled="!protocol.id"
                    @click="executeProtocol(String(protocol.id))"
                  />
                </el-tooltip>
              </div>
            </article>
          </div>
          <el-empty v-else :description="t('devices.protocols.empty')" :image-size="96" />
        </template>

        <template v-else>
          <div v-if="runs.length" class="run-list">
            <article
              v-for="run in runs"
              :key="String(run.id)"
              class="run-card"
            >
              <div class="run-main">
                <div class="run-topline">
                  <span class="run-id">{{ compactId(run.id) }}</span>
                </div>
                <div class="run-protocol">{{ compactId(run.protocolId) }}</div>
                <div class="run-meta">{{ formatTime(run.createdAt) }}</div>
              </div>
              <div class="run-status">
                <el-tag size="small" effect="light" :type="runStatusType(run.status)">
                  {{ formatRunStatus(run.status) }}
                </el-tag>
              </div>
              <div class="run-actions">
                <el-tooltip :content="t('devices.protocols.play')" placement="top">
                  <el-button
                    :icon="VideoPlay"
                    circle
                    size="small"
                    type="primary"
                    :disabled="!run.id"
                    @click="controlRun(String(run.id), 'play')"
                  />
                </el-tooltip>
                <el-tooltip :content="t('devices.protocols.pause')" placement="top">
                  <el-button
                    :icon="VideoPause"
                    circle
                    size="small"
                    :disabled="!run.id"
                    @click="controlRun(String(run.id), 'pause')"
                  />
                </el-tooltip>
                <el-tooltip :content="t('devices.protocols.stop')" placement="top">
                  <el-button
                    :icon="Close"
                    circle
                    size="small"
                    type="danger"
                    :disabled="!run.id"
                    @click="controlRun(String(run.id), 'stop')"
                  />
                </el-tooltip>
              </div>
            </article>
          </div>
          <el-empty v-else :description="t('devices.protocols.emptyRuns')" :image-size="80" />
        </template>
      </div>
    </template>

    <el-dialog v-model="analysisVisible" :title="t('devices.protocols.analysisTitle', { id: analysisProtocolId })" width="720px">
      <pre class="analysis-pre">{{ analysisText }}</pre>
      <template #footer>
        <el-button @click="analysisVisible = false">{{ t('common.actions.close') }}</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { ref, watch } from 'vue'
import { ElMessage } from 'element-plus'
import {
  Close,
  DataAnalysis,
  Document,
  Download,
  Refresh,
  SwitchButton,
  Upload,
  VideoPause,
  VideoPlay
} from '@element-plus/icons-vue'
import type { UploadFile } from 'element-plus'
import { robotApi } from '@/scripts/api'
import { useAppLocale } from '@/i18n'

const { locale, t } = useAppLocale()

const props = withDefaults(defineProps<{
  ip: string | null
  standalone?: boolean
}>(), {
  standalone: false
})

const loading = ref(false)
const uploading = ref(false)
const protocols = ref<Record<string, unknown>[]>([])
const runs = ref<Record<string, unknown>[]>([])
const activePanel = ref<'protocols' | 'runs'>('protocols')
const analysisVisible = ref(false)
const analysisProtocolId = ref('')
const analysisText = ref('')

function formatTime(value: unknown): string {
  if (!value || typeof value !== 'string') return '-'
  const date = new Date(value)
  return Number.isNaN(date.getTime()) ? String(value) : date.toLocaleString(locale.value)
}

function compactId(value: unknown): string {
  if (!value) return '-'
  const text = String(value)
  if (text.length <= 24) return text
  return `${text.slice(0, 10)}...${text.slice(-8)}`
}

function protocolDisplayName(protocol: Record<string, unknown>): string {
  const metadata = protocol.metadata
  if (metadata && typeof metadata === 'object') {
    const meta = metadata as Record<string, unknown>
    const name = meta.protocolName || meta.name || meta.title
    if (name) return String(name)
  }
  const files = protocol.files
  if (Array.isArray(files) && files.length > 0) {
    const first = files[0] as Record<string, unknown>
    if (first.name) return String(first.name)
  }
  return String(protocol.id || t('devices.protocols.unnamed'))
}

function runStatusType(status: unknown): 'success' | 'warning' | 'danger' | 'info' {
  const value = String(status || '')
  if (value === 'succeeded') return 'success'
  if (value === 'running' || value === 'paused') return 'warning'
  if (value === 'failed' || value === 'stopped') return 'danger'
  return 'info'
}

function formatRunStatus(status: unknown): string {
  const value = String(status || '')
  const statusMap: Record<string, string> = {
    succeeded: t('devices.protocols.statuses.succeeded'),
    running: t('devices.protocols.statuses.running'),
    paused: t('devices.protocols.statuses.paused'),
    failed: t('devices.protocols.statuses.failed'),
    stopped: t('devices.protocols.statuses.stopped'),
    idle: t('devices.protocols.statuses.idle')
  }
  return statusMap[value] || value || '-'
}

async function refreshAll() {
  if (!props.ip) return
  loading.value = true
  try {
    const [protocolResponse, runResponse] = await Promise.all([
      robotApi.listProtocols(props.ip),
      robotApi.listRuns(props.ip)
    ])
    protocols.value = protocolResponse.data.protocols
    runs.value = runResponse.data.runs
  } catch (error: any) {
    ElMessage.error(t('devices.protocols.loadFailed', { error: error.message || t('errors.unknown') }))
  } finally {
    loading.value = false
  }
}

async function handleUploadChange(uploadFile: UploadFile, uploadFiles: UploadFile[]) {
  if (!props.ip || uploading.value) return
  if (uploadFiles[uploadFiles.length - 1]?.uid !== uploadFile.uid) return

  uploading.value = true
  loading.value = true
  try {
    const files = uploadFiles
      .map(item => item.raw)
      .filter((file): file is NonNullable<typeof file> => file instanceof File)
    await robotApi.uploadProtocol(props.ip, files)
    ElMessage.success(t('devices.protocols.uploaded'))
    await refreshAll()
  } catch (error: any) {
    ElMessage.error(t('devices.protocols.uploadFailed', { error: error.message || t('errors.unknown') }))
  } finally {
    uploading.value = false
    loading.value = false
  }
}

function getFilenameFromDisposition(contentDisposition: string | undefined, fallback: string): string {
  if (!contentDisposition) return fallback
  const match = contentDisposition.match(/filename="([^"]+)"/)
  return match?.[1] || fallback
}

async function downloadProtocol(protocolId: string, format: 'json' | 'source') {
  if (!props.ip) return
  try {
    const response = await robotApi.downloadProtocol(props.ip, protocolId, format)
    const blob = response.data
    const fallback =
      format === 'json' ? `${protocolId}.protocol.json` : `${protocolId}.zip`
    const filename = getFilenameFromDisposition(response.headers['content-disposition'], fallback)
    const url = URL.createObjectURL(blob)
    const anchor = document.createElement('a')
    anchor.href = url
    anchor.download = filename
    anchor.click()
    URL.revokeObjectURL(url)
    ElMessage.success(format === 'source' ? t('devices.protocols.sourceDownloadStarted') : t('devices.protocols.jsonDownloadStarted'))
  } catch (error: any) {
    ElMessage.error(t('devices.protocols.downloadFailed', { error: error.message || t('errors.unknown') }))
  }
}

async function analyzeProtocol(protocolId: string) {
  if (!props.ip) return
  loading.value = true
  try {
    await robotApi.analyzeProtocol(props.ip, protocolId)
    const response = await robotApi.getProtocolAnalyses(props.ip, protocolId)
    analysisProtocolId.value = protocolId
    analysisText.value = JSON.stringify(response.data.data?.analyses ?? response.data, null, 2)
    analysisVisible.value = true
    ElMessage.success(t('devices.protocols.analysisCompleted'))
  } catch (error: any) {
    ElMessage.error(t('devices.protocols.analysisFailed', { error: error.message || t('errors.unknown') }))
  } finally {
    loading.value = false
  }
}

async function executeProtocol(protocolId: string) {
  if (!props.ip) return
  loading.value = true
  try {
    await robotApi.createRun(props.ip, protocolId)
    ElMessage.success(t('devices.protocols.runCreated'))
    await refreshAll()
  } catch (error: any) {
    ElMessage.error(t('devices.protocols.executionFailed', { error: error.message || t('errors.unknown') }))
  } finally {
    loading.value = false
  }
}

async function controlRun(runId: string, actionType: 'play' | 'pause' | 'stop') {
  if (!props.ip) return
  try {
    await robotApi.controlRun(props.ip, runId, actionType)
    ElMessage.success(t('devices.protocols.controlSent'))
    await refreshAll()
  } catch (error: any) {
    ElMessage.error(t('devices.protocols.controlFailed', { error: error.message || t('errors.unknown') }))
  }
}

watch(
  () => props.ip,
  () => {
    protocols.value = []
    runs.value = []
    if (props.ip) {
      void refreshAll()
    }
  },
  { immediate: true }
)
</script>

<style scoped>
.device-protocols-panel {
  min-height: 260px;
}

.device-protocols-panel.is-standalone {
  min-height: 0;
}

.panel-empty {
  min-height: 320px;
  display: flex;
  align-items: center;
  justify-content: center;
}

.protocol-toolbar {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  gap: 16px;
  margin-bottom: 10px;
}

.title-group {
  display: flex;
  align-items: center;
  min-width: 0;
  gap: 16px;
  flex-wrap: wrap;
}

.section-title {
  font-size: 15px;
  font-weight: 600;
  color: #1f2a37;
}

.protocol-switch {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  padding: 2px;
  border: 1px solid #e6ebf2;
  border-radius: 6px;
  background: #f7f9fc;
}

.switch-button {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  height: 28px;
  padding: 0 10px;
  border: none;
  border-radius: 4px;
  background: transparent;
  color: #64748b;
  font-size: 12px;
  font-weight: 600;
  cursor: pointer;
}

.switch-button.is-active {
  background: #fff;
  color: #1f2a37;
  box-shadow: 0 0 0 1px rgba(230, 235, 242, 0.9);
}

.switch-button span {
  color: #94a3b8;
  font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace;
}

.header-actions {
  display: flex;
  gap: 8px;
  align-items: center;
}

.protocol-workspace {
  min-height: 280px;
  border-top: 1px solid #eef2f7;
}

.run-list,
.protocol-list {
  padding: 4px 0;
}

.run-list {
  display: grid;
  gap: 0;
  max-height: 420px;
  overflow-y: auto;
}

.run-card {
  display: grid;
  grid-template-columns: minmax(0, 1fr) auto auto;
  align-items: center;
  gap: 14px;
  padding: 10px 0;
  border-bottom: 1px solid #f0f3f8;
  background: transparent;
}

.run-topline,
.run-actions,
.protocol-actions,
.protocol-meta {
  display: flex;
  align-items: center;
}

.run-topline {
  min-width: 0;
}

.run-id,
.protocol-id {
  font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace;
}

.run-id {
  min-width: 0;
  overflow: hidden;
  color: #27364a;
  font-size: 13px;
  font-weight: 600;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.run-protocol,
.run-meta {
  margin-top: 8px;
  overflow: hidden;
  color: #7b8797;
  font-size: 12px;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.run-actions {
  gap: 8px;
  justify-content: flex-end;
}

.run-status {
  display: flex;
  align-items: center;
  justify-content: center;
  min-width: 64px;
}

.protocol-list {
  display: grid;
  gap: 0;
  max-height: 420px;
  overflow-y: auto;
}

.protocol-item {
  display: grid;
  grid-template-columns: 40px minmax(0, 1fr) auto;
  align-items: center;
  gap: 12px;
  padding: 10px 0;
  border-bottom: 1px solid #f0f3f8;
  background: #fff;
  transition: background-color 0.18s ease;
}

.protocol-item:hover {
  background: #f8fbff;
}

.protocol-icon {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 28px;
  height: 28px;
  color: #2b6cb0;
  font-size: 18px;
}

.protocol-info {
  min-width: 0;
}

.protocol-name {
  overflow: hidden;
  color: #1f2a37;
  font-size: 14px;
  font-weight: 600;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.protocol-meta {
  gap: 10px;
  margin-top: 6px;
  overflow: hidden;
  color: #7b8797;
  font-size: 12px;
  white-space: nowrap;
}

.protocol-meta span {
  min-width: 0;
  overflow: hidden;
  text-overflow: ellipsis;
}

.protocol-actions {
  gap: 8px;
  justify-content: flex-end;
  flex-wrap: nowrap;
}

.analysis-pre {
  margin: 0;
  max-height: 480px;
  overflow: auto;
  padding: 12px;
  background: #f5f7fa;
  border-radius: 4px;
  font-size: 12px;
  line-height: 1.5;
}

@media (max-width: 900px) {
  .protocol-toolbar {
    align-items: flex-start;
    flex-direction: column;
  }

  .protocol-item {
    grid-template-columns: 28px minmax(0, 1fr);
  }

  .protocol-actions {
    grid-column: 1 / -1;
    justify-content: flex-start;
  }

  .run-card {
    grid-template-columns: 1fr;
  }

  .run-status {
    justify-content: flex-start;
  }
}
</style>
