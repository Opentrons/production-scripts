<template>
  <section class="log-history-panel app-log-analysis-panel">
    <div class="log-record-toolbar">
      <div>
        <div class="log-section-title">{{ t('devices.logs.analysisRecords') }}</div>
        <div class="log-section-description">
          {{ robotIp ? t('devices.logs.analysisCurrentDeviceOnly', { ip: robotIp }) : t('devices.logs.analysisAllDevices') }}
        </div>
      </div>
      <div class="log-record-toolbar-actions">
        <el-upload
          :show-file-list="false"
          accept=".zip,application/zip"
          :before-upload="handleManualUpload"
        >
          <el-button type="primary" :icon="Upload" :loading="uploading">
            {{ t('devices.logs.uploadZip') }}
          </el-button>
        </el-upload>
        <el-button :icon="Refresh" :loading="loading" @click="loadRecords">
          {{ t('common.actions.refresh') }}
        </el-button>
      </div>
    </div>

    <el-table
      v-loading="loading"
      :data="records"
      class="log-record-table"
      :empty-text="t('devices.logs.analysisEmpty')"
    >
      <el-table-column :label="t('devices.logs.deviceName')" prop="device_name" min-width="140" />
      <el-table-column label="IP" prop="robot_ip" width="132" />
      <el-table-column :label="t('devices.logs.analysisArchive')" prop="archive_name" min-width="220" show-overflow-tooltip />
      <el-table-column :label="t('devices.logs.analysisTime')" min-width="180">
        <template #default="scope">
          {{ scope.row.summary?.time || '—' }}
        </template>
      </el-table-column>
      <el-table-column :label="t('devices.logs.analysisError')" min-width="260" show-overflow-tooltip>
        <template #default="scope">
          {{ scope.row.summary?.error || scope.row.error || '—' }}
        </template>
      </el-table-column>
      <el-table-column :label="t('devices.logs.analysisCode')" width="120">
        <template #default="scope">
          {{ formatCode(scope.row) }}
        </template>
      </el-table-column>
      <el-table-column :label="t('devices.logs.status')" width="100">
        <template #default="scope">
          <el-tag size="small" :type="scope.row.status === 'completed' ? 'success' : 'danger'">
            {{ scope.row.status === 'completed' ? t('devices.logs.statuses.success') : t('devices.logs.statuses.failed') }}
          </el-tag>
        </template>
      </el-table-column>
      <el-table-column :label="t('devices.logs.downloadedAt')" width="180">
        <template #default="scope">
          {{ formatDate(scope.row.created_at) }}
        </template>
      </el-table-column>
      <el-table-column :label="t('devices.logs.action')" width="96" fixed="right">
        <template #default="scope">
          <el-button type="primary" link @click="openPreview(scope.row)">
            {{ t('devices.logs.analysisPreview') }}
          </el-button>
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

    <el-drawer
      v-model="previewOpen"
      :title="t('devices.logs.analysisPreviewTitle')"
      size="480px"
      destroy-on-close
    >
      <template v-if="previewRecord">
        <el-descriptions :column="1" border class="analysis-preview-desc">
          <el-descriptions-item :label="t('devices.logs.deviceName')">
            {{ previewRecord.device_name }}
          </el-descriptions-item>
          <el-descriptions-item label="IP">{{ previewRecord.robot_ip }}</el-descriptions-item>
          <el-descriptions-item :label="t('devices.logs.analysisArchive')">
            {{ previewRecord.archive_name || '—' }}
          </el-descriptions-item>
          <el-descriptions-item :label="t('devices.logs.status')">
            {{ previewRecord.status }}
          </el-descriptions-item>
          <el-descriptions-item v-if="previewRecord.error" :label="t('devices.logs.analysisFailure')">
            {{ previewRecord.error }}
          </el-descriptions-item>
          <el-descriptions-item :label="t('devices.logs.analysisTime')">
            {{ previewRecord.summary?.time || '—' }}
          </el-descriptions-item>
          <el-descriptions-item :label="t('devices.logs.analysisError')">
            {{ previewRecord.summary?.error || '—' }}
          </el-descriptions-item>
          <el-descriptions-item :label="t('devices.logs.analysisCode')">
            {{ formatCode(previewRecord) }}
          </el-descriptions-item>
          <el-descriptions-item :label="t('devices.logs.analysisException')">
            {{ previewRecord.summary?.exception || '—' }}
          </el-descriptions-item>
          <el-descriptions-item :label="t('devices.logs.analysisProtocol')">
            {{ previewRecord.summary?.protocol || '—' }}
          </el-descriptions-item>
          <el-descriptions-item :label="t('devices.logs.analysisFile')">
            {{ previewRecord.summary?.file || '—' }}
          </el-descriptions-item>
          <el-descriptions-item :label="t('devices.logs.analysisRun')">
            {{ previewRecord.summary?.run || '—' }}
          </el-descriptions-item>
          <el-descriptions-item :label="t('devices.logs.analysisTest')">
            {{ previewRecord.summary?.test || '—' }}
          </el-descriptions-item>
        </el-descriptions>
        <pre v-if="previewRecord.summary?.evidence?.length" class="analysis-preview-json">{{
          JSON.stringify(previewRecord.summary.evidence, null, 2)
        }}</pre>
        <pre class="analysis-preview-json">{{ JSON.stringify(previewRecord.summary || {}, null, 2) }}</pre>
      </template>
    </el-drawer>
  </section>
</template>

<script setup lang="ts">
import { onMounted, ref, watch } from 'vue'
import { Refresh, Upload } from '@element-plus/icons-vue'
import { ElMessage } from 'element-plus'
import { useI18n } from 'vue-i18n'
import { useAppLocale } from '@/i18n'
import { robotApi, type RobotAppLogAnalysisRecord } from '@/scripts/api'

const { t } = useI18n()
const { locale } = useAppLocale()

const props = defineProps<{
  robotIp?: string | null
  deviceName?: string | null
}>()

const records = ref<RobotAppLogAnalysisRecord[]>([])
const loading = ref(false)
const page = ref(1)
const pageSize = 20
const total = ref(0)
const previewOpen = ref(false)
const previewRecord = ref<RobotAppLogAnalysisRecord | null>(null)
const uploading = ref(false)

function normalizeError(error: any): string {
  return error?.response?.data?.detail?.message
    || error?.response?.data?.detail
    || error?.response?.data?.message
    || error?.message
    || t('errors.unknown')
}

function formatDate(value?: string | null): string {
  if (!value) return '—'
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return value
  return new Intl.DateTimeFormat(locale.value, {
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
    second: '2-digit',
    hour12: false,
  }).format(date)
}

function formatCode(record: RobotAppLogAnalysisRecord): string {
  const code = record.summary?.code
  const name = record.summary?.code_name
  if (code && name) return `${code} ${name}`
  return code || name || '—'
}

async function loadRecords() {
  loading.value = true
  try {
    const response = await robotApi.getAppLogAnalysisRecords({
      page: page.value,
      pageSize,
      robotIp: props.robotIp || undefined,
    })
    records.value = response.data.records || []
    total.value = response.data.total || 0
  } catch (error: any) {
    records.value = []
    total.value = 0
    ElMessage.error(t('devices.logs.analysisLoadFailed', { error: normalizeError(error) }))
  } finally {
    loading.value = false
  }
}

async function handleManualUpload(file: File) {
  if (!file.name.toLowerCase().endsWith('.zip')) {
    ElMessage.error(t('devices.logs.zipOnly'))
    return false
  }
  uploading.value = true
  try {
    const response = await robotApi.uploadAppLogForAnalysis(
      file,
      props.robotIp || 'manual',
      props.deviceName || undefined,
    )
    if (response.data.status === 'completed') {
      ElMessage.success(t('devices.logs.uploadSuccess'))
    } else {
      ElMessage.warning(response.data.error || t('devices.logs.uploadFailed'))
    }
    page.value = 1
    await loadRecords()
  } catch (error: any) {
    ElMessage.error(t('devices.logs.uploadFailedWithError', { error: normalizeError(error) }))
  } finally {
    uploading.value = false
  }
  return false
}

function openPreview(record: RobotAppLogAnalysisRecord) {
  previewRecord.value = record
  previewOpen.value = true
}

watch(() => props.robotIp, () => {
  page.value = 1
  loadRecords()
})

onMounted(() => {
  loadRecords()
})
</script>

<style scoped>
.analysis-preview-desc {
  margin-bottom: 16px;
}

.analysis-preview-json {
  margin: 0 0 12px;
  padding: 12px;
  border-radius: 8px;
  background: #f5f7f6;
  color: #24302c;
  font-size: 12px;
  line-height: 1.5;
  white-space: pre-wrap;
  word-break: break-word;
  max-height: 280px;
  overflow: auto;
}

.log-record-toolbar-actions {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-wrap: wrap;
}
</style>
