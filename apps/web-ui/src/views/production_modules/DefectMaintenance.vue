<template>
  <details class="defect-maintenance" @toggle="onToggle">
    <summary>{{ text.title }}</summary>
    <div class="defect-maintenance-body">
      <p v-if="statusError" class="defect-inline-error" role="alert">{{ statusError }} <button type="button" class="defect-text-button" @click="loadStatus">{{ text.retry }}</button></p>
      <dl v-if="status" class="defect-maintenance-status">
        <div><dt>{{ text.version }}</dt><dd>{{ status.data_version || '—' }}</dd></div>
        <div><dt>{{ text.updated }}</dt><dd>{{ formatDate(status.last_updated) }}</dd></div>
        <div><dt>{{ text.backups }}</dt><dd>{{ status.backup_count }}<template v-if="lastBackup"> · {{ lastBackup }}</template></dd></div>
      </dl>
      <p class="defect-dialog-note">{{ text.note }}</p>
      <div class="defect-maintenance-controls">
        <label class="defect-file-label"><span>{{ text.csv }}</span><input type="file" accept=".csv,text/csv" :disabled="Boolean(busy)" @change="selectFile" /></label>
        <button type="button" class="defect-reset-button" :disabled="Boolean(busy) || !csvContent" @click="previewImport">{{ busy === 'preview' ? text.previewing : text.preview }}</button>
        <button type="button" class="defect-reset-button" :disabled="Boolean(busy)" @click="backup">{{ busy === 'backup' ? text.backingUp : text.backup }}</button>
      </div>
      <p v-if="error" class="defect-inline-error" role="alert">{{ error }}</p>
      <p v-if="message" class="defect-operation-success" role="status">{{ message }}</p>
      <details v-if="status?.changes?.length" class="defect-maintenance-log"><summary>{{ text.changeLog }}</summary><ul><li v-for="(entry, index) in status.changes" :key="index"><span>{{ formatDate(entry.created_at) }} · {{ text.csvImport }}</span><p>{{ text.counts(entry.details.rows ?? 0, entry.details.inserted ?? 0, entry.details.updated ?? 0, entry.details.unchanged ?? 0) }}</p></li></ul></details>
      <section v-if="preview" class="defect-import-preview" aria-live="polite">
        <h3>{{ text.previewTitle }}</h3>
        <p>{{ text.counts(preview.rows, preview.inserted, preview.updated, preview.unchanged) }}</p>
        <p v-if="preview.errors.length" class="defect-inline-error">{{ text.errors(preview.errors.length) }}</p>
        <ul v-if="preview.errors.length" class="defect-import-errors"><li v-for="(entry, index) in preview.errors.slice(0, 50)" :key="index">{{ errorLabel(entry) }}</li></ul>
        <p v-if="preview.errors.length > 50" class="defect-dialog-note">{{ text.moreErrors }}</p>
        <p v-else-if="!preview.errors.length" class="defect-dialog-note">{{ text.importNote }}</p>
        <button type="button" class="defect-search-button" :disabled="Boolean(busy) || preview.errors.length > 0 || !preview.preview_token || !(preview.inserted + preview.updated)" @click="confirmImport">{{ busy === 'import' ? text.importing : text.confirm }}</button>
      </section>
    </div>
  </details>
</template>

<script setup lang="ts">
import { maintenanceEnglish, maintenanceChinese } from '@/i18n/locales/defectSearch'
import { computed, ref } from 'vue'
import axios from 'axios'
import { defectSearchApi, type DefectImportPreview, type DefectMaintenanceStatus } from '@/scripts/api'

const props = defineProps<{ english: boolean }>()
const emit = defineEmits<{ imported: [] }>()
const status = ref<DefectMaintenanceStatus | null>(null)
const statusError = ref('')
const csvContent = ref('')
const preview = ref<DefectImportPreview | null>(null)
const busy = ref('')
const error = ref('')
const message = ref('')
let selectionVersion = 0
const text = computed(() => props.english ? maintenanceEnglish : maintenanceChinese)
const lastBackup = computed(() => {
  const value = status.value?.last_backup
  if (!value) return ''
  return typeof value === 'string' ? value.split('/').pop() : value.created_at || value.name || value.path?.split('/').pop() || ''
})
function apiError(value: unknown, fallback: string): string {
  if (axios.isAxiosError(value)) { const detail: unknown = value.response?.data?.detail; if (typeof detail === 'string') return detail }
  return fallback
}
function formatDate(value?: string): string {
  if (!value) return '—'
  const date = new Date(value)
  return Number.isNaN(date.getTime()) ? value : date.toLocaleString(props.english ? 'en-GB' : 'zh-CN', { timeZone: 'Asia/Shanghai', hour12: false })
}
function errorLabel(value: DefectImportPreview['errors'][number]): string {
  if (typeof value === 'string') return value
  return [value.row ? `${text.value.row} ${value.row}` : '', value.field || '', value.message || value.error || ''].filter(Boolean).join(' · ')
}
function onToggle(event: Event): void { if ((event.target as HTMLDetailsElement).open) void loadStatus() }
async function loadStatus(): Promise<void> {
  statusError.value = ''
  try { status.value = (await defectSearchApi.getMaintenance()).data }
  catch { statusError.value = text.value.statusFailed }
}
async function selectFile(event: Event): Promise<void> {
  const version = ++selectionVersion
  csvContent.value = ''; preview.value = null; error.value = ''; message.value = ''
  const file = (event.target as HTMLInputElement).files?.[0]
  if (!file) return
  if (!file.name.toLowerCase().endsWith('.csv')) { error.value = text.value.csvRequired; return }
  if (file.size > 5 * 1024 * 1024) { error.value = text.value.tooLarge; return }
  try { const value = await file.text(); if (version === selectionVersion) csvContent.value = value }
  catch { if (version === selectionVersion) error.value = text.value.readFailed }
}
async function previewImport(): Promise<void> {
  if (busy.value || !csvContent.value) return
  busy.value = 'preview'; error.value = ''; message.value = ''; preview.value = null
  try { preview.value = (await defectSearchApi.previewImport(csvContent.value)).data }
  catch (value) { error.value = apiError(value, text.value.operationFailed) }
  finally { busy.value = '' }
}
async function confirmImport(): Promise<void> {
  if (busy.value || !preview.value || preview.value.errors.length) return
  busy.value = 'import'; error.value = ''; message.value = ''
  try {
    const response = await defectSearchApi.importCases(csvContent.value, preview.value.preview_token)
    message.value = text.value.imported(response.data.inserted, response.data.updated)
    preview.value = null
    emit('imported')
    await loadStatus()
  } catch (value) { error.value = apiError(value, text.value.operationFailed) }
  finally { busy.value = '' }
}
async function backup(): Promise<void> {
  if (busy.value) return
  busy.value = 'backup'; error.value = ''; message.value = ''
  try { await defectSearchApi.backup(); message.value = text.value.backupDone; await loadStatus() }
  catch (value) { error.value = apiError(value, text.value.operationFailed) }
  finally { busy.value = '' }
}
</script>
