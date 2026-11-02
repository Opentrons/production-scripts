<template>
  <section class="tf-detail-section">
    <h3>{{ t('testFailures.attachments') }}</h3>
    <div class="tf-attachment-list">
      <div v-for="item in attachments" :key="item.kind" class="tf-attachment-row">
        <span><strong>{{ item.name }}</strong><small>{{ item.kind.toUpperCase() }} · {{ formatSize(item.size) }}</small></span>
        <span v-if="!item.available" class="tf-muted">{{ t('testFailures.unavailable') }}</span>
        <template v-else>
          <button type="button" class="tf-button" :aria-pressed="activeKind === item.kind" @click="preview(item.kind)">{{ t('testFailures.preview') }}</button>
          <button type="button" class="tf-button" :disabled="downloading.has(item.kind)" @click="download(item.kind, item.name)">{{ t(item.kind === 'encoder' ? 'testFailures.downloadCsv' : 'testFailures.download') }}</button>
        </template>
      </div>
    </div>
    <p v-if="downloadError" class="tf-error" role="alert">{{ downloadError }}</p>
    <div v-if="activeKind" class="tf-preview" aria-live="polite">
      <strong>{{ activeKind.toUpperCase() }}</strong>
      <p v-if="loading">{{ t('testFailures.loading') }}</p>
      <p v-else-if="error" class="tf-error" role="alert">{{ error }} <button type="button" class="tf-link" @click="preview(activeKind)">{{ t('testFailures.retry') }}</button></p>
      <template v-else-if="content">
        <p v-if="content.truncated" class="tf-note">{{ t('testFailures.truncated') }}</p>
        <div v-if="content.columns?.length" class="tf-table-wrap tf-encoder-table">
          <table class="tf-table"><thead><tr><th v-for="(column, i) in content.columns" :key="i">{{ column }}</th></tr></thead>
            <tbody><tr v-for="(row, i) in content.rows" :key="i"><td v-for="(cell, j) in row" :key="j">{{ cell }}</td></tr></tbody>
          </table>
        </div>
        <pre v-else-if="content.text" class="tf-code">{{ content.text }}</pre>
        <p v-else class="tf-muted">{{ t('testFailures.previewEmpty') }}</p>
      </template>
    </div>
  </section>
</template>

<script setup lang="ts">
import { onBeforeUnmount, ref, watch } from 'vue'
import { useAppLocale } from '@/i18n'
import { testFailuresApi, type AttachmentKind, type FailureAttachmentPreview, type FailureReport } from '@/scripts/api/testFailures'

const props = defineProps<{ reportId: string; attachments: FailureReport['attachments'] }>()
const { t } = useAppLocale()
const activeKind = ref<AttachmentKind | null>(null)
const content = ref<FailureAttachmentPreview | null>(null)
const loading = ref(false)
const error = ref('')
const downloadError = ref('')
const downloading = ref(new Set<AttachmentKind>())
let previewController: AbortController | null = null
const downloads = new Set<AbortController>()
const objectUrls = new Set<string>()
const revokeTimers = new Set<ReturnType<typeof setTimeout>>()

function formatSize(size: number): string { return size < 1024 ? `${size} B` : `${(size / 1024).toFixed(1)} KB` }
async function preview(kind: AttachmentKind): Promise<void> {
  previewController?.abort()
  const controller = new AbortController()
  previewController = controller
  activeKind.value = kind; loading.value = true; error.value = ''; content.value = null
  try {
    const { data } = await testFailuresApi.preview(props.reportId, kind, controller.signal)
    if (!controller.signal.aborted) content.value = data
  } catch {
    if (!controller.signal.aborted) error.value = t('testFailures.previewFailed')
  } finally {
    if (previewController === controller) loading.value = false
  }
}

async function download(kind: AttachmentKind, name: string): Promise<void> {
  const controller = new AbortController()
  downloads.add(controller); downloading.value.add(kind); downloadError.value = ''
  try {
    const { data } = await testFailuresApi.attachment(props.reportId, kind, controller.signal)
    if (controller.signal.aborted) return
    const url = URL.createObjectURL(data)
    objectUrls.add(url)
    const anchor = document.createElement('a')
    anchor.href = url; anchor.download = name; document.body.appendChild(anchor)
    anchor.click(); anchor.remove()
    const timer = setTimeout(() => { URL.revokeObjectURL(url); objectUrls.delete(url); revokeTimers.delete(timer) }, 1000)
    revokeTimers.add(timer)
  } catch {
    if (!controller.signal.aborted) downloadError.value = t('testFailures.downloadFailed')
  } finally {
    downloads.delete(controller); downloading.value.delete(kind)
  }
}
function clear(): void {
  previewController?.abort(); downloads.forEach(controller => controller.abort())
  revokeTimers.forEach(clearTimeout); objectUrls.forEach(url => URL.revokeObjectURL(url))
  revokeTimers.clear(); objectUrls.clear(); activeKind.value = null; content.value = null
  loading.value = false; error.value = ''; downloadError.value = ''
}
watch(() => props.reportId, clear)
onBeforeUnmount(clear)
</script>
