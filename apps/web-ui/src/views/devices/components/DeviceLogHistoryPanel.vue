<template>
  <section class="log-history-panel">
    <div class="log-record-toolbar">
      <div>
        <div class="log-section-title">服务器下载记录</div>
        <div class="log-section-description">
          {{ robotIp ? `仅显示 ${robotIp} 的 Log 下载记录。` : '显示全部设备的 Log 下载记录。' }}
        </div>
      </div>
      <el-button :icon="Refresh" :loading="loading" @click="loadRecords">
        刷新
      </el-button>
    </div>

    <el-table
      v-loading="loading"
      :data="records"
      :cell-style="getTableCellStyle"
      :header-cell-style="getTableCellStyle"
      class="log-record-table"
      empty-text="暂无下载记录"
    >
      <el-table-column type="expand" width="48">
        <template #default="scope">
          <div class="log-record-command-detail">
            <div class="log-section-title">执行命令记录</div>
            <div v-if="scope.row.command_logs?.length" class="log-command-console is-record">
              <article
                v-for="commandLog in getDisplayCommandLogs(scope.row.command_logs)"
                :key="commandLog.id"
                class="log-command-entry"
              >
                <div class="log-command-meta">
                  <span>{{ formatCommandTime(commandLog.started_at) }} · {{ commandLog.label }}</span>
                  <el-tag size="small" :type="getCommandStatusTagType(commandLog.status)">
                    {{ getCommandStatusLabel(commandLog.status) }}
                  </el-tag>
                </div>
                <pre class="log-command-content">{{ commandLog.command }}</pre>
                <pre v-if="commandLog.output" class="log-command-output">{{ commandLog.output }}</pre>
                <pre v-if="commandLog.error" class="log-command-output is-error">{{ commandLog.error }}</pre>
              </article>
            </div>
            <el-empty v-else description="暂无命令记录" :image-size="48" />
          </div>
        </template>
      </el-table-column>
      <el-table-column label="设备名" prop="device_name" min-width="150" />
      <el-table-column label="IP" prop="robot_ip" width="132" />
      <el-table-column label="Log 文件夹" min-width="220" align="left" header-align="left">
        <template #default="scope">
          <el-tooltip placement="top" :show-after="300">
            <template #content>
              <div class="log-record-folder-tooltip">
                <el-tag
                  v-for="folder in scope.row.selected_folders"
                  :key="`${scope.row._id}-tooltip-${folder.key}`"
                  size="small"
                  type="info"
                >
                  {{ folder.label }}
                </el-tag>
              </div>
            </template>
            <div class="log-record-folders">
              <el-tag
                v-for="folder in scope.row.selected_folders"
                :key="`${scope.row._id}-${folder.key}`"
                size="small"
                type="info"
              >
                {{ folder.label }}
              </el-tag>
            </div>
          </el-tooltip>
        </template>
      </el-table-column>
      <el-table-column label="服务器文件目录" min-width="320">
        <template #default="scope">
          <el-tooltip :content="scope.row.archive_path || scope.row.server_directory" placement="top">
            <span class="log-record-path">{{ scope.row.archive_path || scope.row.server_directory }}</span>
          </el-tooltip>
        </template>
      </el-table-column>
      <el-table-column label="文件大小" width="110">
        <template #default="scope">{{ formatBytes(scope.row.archive_size) }}</template>
      </el-table-column>
      <el-table-column label="进度" width="150">
        <template #default="scope">
          <el-progress
            :percentage="scope.row.progress"
            :status="getRecordProgressStatus(scope.row)"
            :stroke-width="16"
            :text-inside="true"
          />
        </template>
      </el-table-column>
      <el-table-column label="状态" width="100">
        <template #default="scope">
          <el-tag v-if="scope.row.file_deleted_at" size="small" type="info">已删除</el-tag>
          <el-tooltip
            v-else-if="scope.row.status === 'warning'"
            :content="scope.row.cleanup_error || scope.row.current_step"
            placement="top"
          >
            <el-tag size="small" type="warning">清理警告</el-tag>
          </el-tooltip>
          <el-tooltip v-else-if="scope.row.error" :content="scope.row.error" placement="top">
            <el-tag size="small" :type="getLogStatusTagType(scope.row.status)">
              {{ getLogStatusLabel(scope.row.status) }}
            </el-tag>
          </el-tooltip>
          <el-tag v-else size="small" :type="getLogStatusTagType(scope.row.status)">
            {{ getLogStatusLabel(scope.row.status) }}
          </el-tag>
        </template>
      </el-table-column>
      <el-table-column label="下载时间" width="180">
        <template #default="scope">
          {{ formatDate(scope.row.downloaded_at || scope.row.finished_at || scope.row.started_at) }}
        </template>
      </el-table-column>
      <el-table-column label="操作" width="128" fixed="right">
        <template #default="scope">
          <div class="log-record-actions">
            <el-tooltip
              :disabled="scope.row.file_available"
              :content="scope.row.file_unavailable_reason || '服务器文件不可用'"
              placement="top"
            >
              <span>
                <el-button
                  type="primary"
                  link
                  :disabled="!scope.row.file_available"
                  @click="downloadServerLog(scope.row)"
                >
                  下载
                </el-button>
              </span>
            </el-tooltip>
            <el-tooltip
              :disabled="scope.row.file_available"
              :content="scope.row.file_unavailable_reason || '服务器文件不可用'"
              placement="top"
            >
              <span>
                <el-button
                  type="danger"
                  link
                  :loading="deletingRecordId === scope.row._id"
                  :disabled="!scope.row.file_available"
                  @click="deleteServerLog(scope.row)"
                >
                  删除
                </el-button>
              </span>
            </el-tooltip>
          </div>
        </template>
      </el-table-column>
    </el-table>

    <el-pagination
      v-if="total > pageSize"
      v-model:current-page="page"
      :page-size="pageSize"
      :total="total"
      layout="prev, pager, next, total"
      class="log-record-pagination"
      @current-change="loadRecords"
    />
  </section>
</template>

<script setup lang="ts">
import { onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { Refresh } from '@element-plus/icons-vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import {
  robotApi,
  type RobotLogCommandEntry,
  type RobotLogDownloadRecord,
  type RobotLogDownloadStatus
} from '@/scripts/api'

const props = defineProps<{
  robotIp?: string | null
}>()

const records = ref<RobotLogDownloadRecord[]>([])
const loading = ref(false)
const page = ref(1)
const pageSize = 20
const total = ref(0)
const deletingRecordId = ref('')
let pollTimer: ReturnType<typeof setTimeout> | null = null

function normalizeError(error: any): string {
  return error?.response?.data?.detail?.message
    || error?.response?.data?.detail
    || error?.response?.data?.message
    || error?.message
    || '未知错误'
}

function clearPollTimer() {
  if (!pollTimer) return
  clearTimeout(pollTimer)
  pollTimer = null
}

function schedulePolling() {
  clearPollTimer()
  if (records.value.some(record => ['queued', 'running'].includes(record.status))) {
    pollTimer = setTimeout(() => loadRecords(true), 1000)
  }
}

async function loadRecords(silent = false) {
  if (loading.value) return
  clearPollTimer()
  loading.value = !silent
  try {
    const response = await robotApi.getLogDownloadRecords({
      page: page.value,
      pageSize,
      robotIp: props.robotIp || undefined
    })
    records.value = response.data.records
    total.value = response.data.total
  } catch (error: any) {
    if (!silent) ElMessage.error('加载 Log 下载记录失败: ' + normalizeError(error))
  } finally {
    loading.value = false
    schedulePolling()
  }
}

function downloadServerLog(record: RobotLogDownloadRecord) {
  if (!record.file_available) return
  const anchor = document.createElement('a')
  anchor.href = robotApi.getServerLogDownloadUrl(record._id)
  anchor.download = record.archive_name || 'diagnostics.tar.gz'
  document.body.appendChild(anchor)
  anchor.click()
  anchor.remove()
}

async function deleteServerLog(record: RobotLogDownloadRecord) {
  if (!record.file_available) return
  try {
    await ElMessageBox.confirm(
      `确认删除服务器上的 ${record.archive_name || 'Log 文件'}？下载记录会保留。`,
      '删除服务器 Log',
      {
        confirmButtonText: '删除',
        cancelButtonText: '取消',
        type: 'warning'
      }
    )
  } catch {
    return
  }

  deletingRecordId.value = record._id
  try {
    const response = await robotApi.deleteServerLog(record._id)
    record.file_available = false
    record.file_deleted_at = response.data.file_deleted_at
    ElMessage.success('服务器 Log 已删除，下载记录已保留')
  } catch (error: any) {
    ElMessage.error('删除服务器 Log 失败: ' + normalizeError(error))
  } finally {
    deletingRecordId.value = ''
  }
}

function getLogStatusLabel(status: RobotLogDownloadStatus) {
  const labels: Partial<Record<RobotLogDownloadStatus, string>> = {
    queued: '等待中',
    running: '下载中',
    success: '成功',
    warning: '警告',
    failed: '失败',
    completed: '已完成',
    completed_with_warnings: '完成有警告',
    completed_with_errors: '完成有失败'
  }
  return labels[status] || status
}

function getLogStatusTagType(status: RobotLogDownloadStatus) {
  if (['success', 'completed'].includes(status)) return 'success'
  if (['failed', 'completed_with_errors'].includes(status)) return 'danger'
  if (['warning', 'completed_with_warnings'].includes(status)) return 'warning'
  return 'info'
}

function getRecordProgressStatus(record: RobotLogDownloadRecord) {
  if (record.status === 'failed') return 'exception'
  if (record.status === 'warning') return 'warning'
  if (record.status === 'success') return 'success'
  return undefined
}

function getTableCellStyle({ column }: { column: { label?: string } }) {
  return { textAlign: column.label === 'Log 文件夹' ? 'left' : 'center' }
}

function getDisplayCommandLogs(commandLogs?: RobotLogCommandEntry[]) {
  return [...(commandLogs || [])].reverse()
}

function getCommandStatusLabel(status: RobotLogCommandEntry['status']) {
  if (status === 'running') return '执行中'
  if (status === 'success') return '成功'
  return '失败'
}

function getCommandStatusTagType(status: RobotLogCommandEntry['status']) {
  if (status === 'success') return 'success'
  if (status === 'failed') return 'danger'
  return 'warning'
}

function formatCommandTime(value?: string | null) {
  if (!value) return '--:--:--'
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return value
  return new Intl.DateTimeFormat('zh-CN', {
    hour: '2-digit',
    minute: '2-digit',
    second: '2-digit',
    hour12: false
  }).format(date)
}

function formatDate(value?: string | null) {
  if (!value) return '-'
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return value
  return new Intl.DateTimeFormat('zh-CN', {
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
    second: '2-digit',
    hour12: false
  }).format(date)
}

function formatBytes(value?: number | null) {
  const bytes = Number(value || 0)
  if (!bytes) return '-'
  const units = ['B', 'KB', 'MB', 'GB']
  const unitIndex = Math.min(Math.floor(Math.log(bytes) / Math.log(1024)), units.length - 1)
  const amount = bytes / Math.pow(1024, unitIndex)
  return `${amount.toFixed(unitIndex === 0 ? 0 : 1)} ${units[unitIndex]}`
}

watch(() => props.robotIp, () => {
  page.value = 1
  void loadRecords()
})

onMounted(loadRecords)
onBeforeUnmount(clearPollTimer)
</script>

<style scoped>
.log-history-panel {
  min-width: 0;
}

.log-record-toolbar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
  margin-bottom: 14px;
}

.log-section-title {
  color: #1f2a37;
  font-size: 14px;
  font-weight: 650;
}

.log-section-description {
  margin-top: 4px;
  color: #6b7280;
  font-size: 12px;
}

.log-record-table {
  width: 100%;
}

.log-record-command-detail {
  padding: 12px 20px 18px;
}

.log-record-command-detail > .log-section-title {
  margin-bottom: 10px;
}

.log-record-folders,
.log-record-folder-tooltip {
  display: flex;
  flex-wrap: nowrap;
  gap: 4px;
  min-width: 0;
  overflow: hidden;
}

.log-record-folder-tooltip {
  max-width: 420px;
  flex-wrap: wrap;
}

.log-record-path {
  display: block;
  overflow: hidden;
  font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace;
  font-size: 12px;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.log-record-actions {
  display: flex;
  justify-content: center;
  gap: 4px;
}

.log-record-pagination {
  justify-content: center;
  margin-top: 16px;
}

.log-command-console {
  max-height: 520px;
  overflow: auto;
  border: 1px solid #253244;
  border-radius: 6px;
  background: #111827;
  color: #dbeafe;
}

.log-command-entry {
  padding: 10px;
  border-bottom: 1px solid #253244;
}

.log-command-entry:last-child {
  border-bottom: 0;
}

.log-command-meta {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  margin-bottom: 7px;
  color: #cbd5e1;
  font-size: 12px;
}

.log-command-content,
.log-command-output {
  margin: 0;
  overflow: auto;
  color: #e2e8f0;
  font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace;
  font-size: 12px;
  line-height: 1.55;
  white-space: pre-wrap;
  word-break: break-word;
}

.log-command-output {
  margin-top: 8px;
  padding-top: 8px;
  border-top: 1px dashed #334155;
  color: #a7f3d0;
}

.log-command-output.is-error {
  color: #fecaca;
}

@media (max-width: 760px) {
  .log-record-toolbar {
    align-items: flex-start;
    flex-direction: column;
  }
}
</style>
