<template>
  <main class="defect-search-page tf-page">
    <header class="defect-search-topbar">
      <RouterLink class="defect-search-brand" to="/" aria-label="Productions"><img :src="productionsLogo" alt="Productions" /><span>{{ knowledgeCopy.platform }}</span></RouterLink>
      <div class="defect-search-account"><LocaleSwitcher /><AuthUserMenu /></div>
    </header>
    <div class="defect-search-content tf-content">
      <nav class="defect-search-breadcrumb" aria-label="breadcrumb"><RouterLink to="/">{{ knowledgeCopy.home }}</RouterLink><span>/</span><RouterLink :to="{ name: 'DefectSearch' }">{{ knowledgeCopy.title }}</RouterLink><span>/</span><span>{{ t('testFailures.title') }}</span></nav>
      <section class="defect-search-heading"><div><p class="defect-search-eyebrow">QUALITY OPERATIONS</p><h1>{{ knowledgeCopy.title }}</h1><p class="defect-search-intro">{{ t('testFailures.intro') }}</p></div></section>
      <nav class="defect-section-tabs" :aria-label="knowledgeCopy.title">
        <RouterLink :to="{ name: 'DefectSearch' }" exact-active-class="is-active">{{ t('testFailures.knowledgeTab') }}</RouterLink>
        <RouterLink :to="{ name: 'TestFailures' }" exact-active-class="is-active">{{ t('testFailures.failuresTab') }}</RouterLink>
      </nav>
      <section class="tf-panel tf-results" :aria-busy="loading">
        <div class="tf-results-heading">
          <div class="tf-results-title"><h2>{{ t('testFailures.folderReports') }}</h2><span>{{ t('testFailures.total', { count: response?.total ?? 0 }) }}</span></div>
          <dl class="tf-inline-stats">
            <div v-for="item in summaryCards" :key="item.key" :class="{ 'is-highlight': item.key === 'pending', 'is-error': item.key === 'parseErrors' && item.value > 0 }"><dt>{{ t(`testFailures.${item.key}`) }}</dt><dd>{{ item.value.toLocaleString() }}</dd></div>
          </dl>
        </div>
        <form class="tf-filters" novalidate @submit.prevent="applyFilters">
          <div class="tf-filter-bar">
            <label class="tf-search-filter"><span class="tf-visually-hidden">{{ t('testFailures.search') }}</span><input v-model="filters.q" type="search" maxlength="500" autocomplete="off" :placeholder="t('testFailures.search')" /></label>
            <div class="tf-filter-actions">
              <button class="tf-button is-primary" type="submit">{{ t(advancedFiltersOpen ? 'testFailures.apply' : 'testFailures.searchAction') }}</button>
              <button class="tf-button tf-more-filters" type="button" :aria-expanded="advancedFiltersOpen" aria-controls="tf-advanced-filters" @click="advancedFiltersOpen = !advancedFiltersOpen"><span>{{ t(advancedFiltersOpen ? 'testFailures.lessFilters' : 'testFailures.moreFilters') }}</span><span v-if="activeAdvancedFilters.length" class="tf-filter-count">{{ activeAdvancedFilters.length }}</span><svg aria-hidden="true" viewBox="0 0 16 16"><path d="m4 6 4 4 4-4" /></svg></button>
              <button class="tf-button" type="button" @click="resetFilters">{{ t('testFailures.reset') }}</button>
            </div>
            <div class="tf-actions tf-scan-actions"><button class="tf-button" type="button" :disabled="loading" @click="refresh">{{ t('testFailures.refresh') }}</button><button v-if="canEdit" class="tf-button" type="button" :disabled="scan?.running || startingScan" @click="startScan">{{ t(scan?.running || startingScan ? 'testFailures.scanning' : 'testFailures.scan') }}</button></div>
          </div>
          <div v-show="advancedFiltersOpen" id="tf-advanced-filters" class="tf-advanced-filters">
            <label><span>{{ t('testFailures.mode') }}</span><select v-model="filters.mode"><option value="">{{ t('testFailures.allModes') }}</option><option v-for="mode in response?.options.modes || []" :key="mode" :value="mode">{{ mode }}</option></select></label>
            <label><span>{{ t('testFailures.kind') }}</span><select v-model="filters.kind"><option value="">{{ t('testFailures.allKinds') }}</option><option v-for="kind in kinds" :key="kind" :value="kind">{{ t(`testFailures.kinds.${kind}`) }}</option></select></label>
            <label><span>{{ t('testFailures.dateFrom') }}</span><input v-model="filters.date_from" type="date" :max="filters.date_to || undefined" /></label>
            <label><span>{{ t('testFailures.dateTo') }}</span><input v-model="filters.date_to" type="date" :min="filters.date_from || undefined" /></label>
            <p class="tf-note">{{ t('testFailures.dateHint') }}</p>
          </div>
          <div v-if="!advancedFiltersOpen && activeAdvancedFilters.length" class="tf-active-filters"><span>{{ t('testFailures.activeFilters') }}</span><span v-for="item in activeAdvancedFilters" :key="item.key" class="tf-chip is-neutral">{{ item.text }}</span></div>
          <p v-if="filterError" class="tf-error" role="alert">{{ filterError }}</p>
        </form>
        <div class="tf-scan-panel" aria-live="polite">
          <div class="tf-scan-status"><span class="tf-chip" :class="scan?.running ? 'is-running' : 'is-neutral'">{{ t(scan?.running ? 'testFailures.scanning' : 'testFailures.scanIdle') }}</span><span>{{ t('testFailures.lastScan') }}: {{ formatFailureTime(scan?.last_scan_at, locale) }}</span><span>{{ t('testFailures.pendingFiles') }}: {{ scan?.pending_files ?? 0 }}</span></div>
          <p v-if="scan?.source_status === 'degraded' || scan?.source_status === 'unavailable'" class="tf-note" role="status">{{ t(`testFailures.sourceStates.${scan.source_status}`) }} · {{ t('testFailures.lastSuccessfulScan') }}: {{ formatFailureTime(scan.last_successful_scan_at, locale) }}</p>
          <p v-if="scanError || scan?.error" class="tf-error" role="alert">{{ scanError || scan?.error }}</p>
          <details v-if="scan?.errors?.length" class="tf-scan-errors"><summary>{{ t('testFailures.scanErrors') }} ({{ scan.errors.length }})</summary><ul><li v-for="(item, i) in scan.errors" :key="i"><strong>{{ item.path }}</strong>: {{ item.message }}</li></ul></details>
        </div>
        <div class="tf-classification">
          <div class="tf-model-filters" role="group" :aria-label="t('testFailures.product')">
            <button type="button" class="tf-model-filter" :aria-pressed="!applied.product" @click="selectProduct('')"><span>{{ t('testFailures.allProducts') }}</span><span class="tf-filter-count">{{ facetCount(facets?.all.total) }}</span></button>
            <button v-for="item in productFacets" :key="item.product" type="button" class="tf-model-filter" :aria-pressed="applied.product === item.product" @click="selectProduct(item.product)"><span>{{ item.product || t('testFailures.unknownProduct') }}</span><span class="tf-filter-count">{{ facetCount(item.total) }}</span></button>
          </div>
          <div class="tf-confirmation-filters" role="group" :aria-label="t('testFailures.confirmation')">
            <button v-for="item in confirmationFilters" :key="item.value" type="button" class="tf-confirmation-filter" :aria-pressed="applied.confirmation === item.value" @click="selectConfirmation(item.value)"><span>{{ t(item.label) }}</span><span class="tf-filter-count">{{ facetCount(item.count) }}</span></button>
          </div>
        </div>
        <p v-if="savedReportFolder" class="tf-success tf-save-notice" role="status">{{ t('testFailures.savedReport', { folder: savedReportFolder }) }}</p>
        <p v-if="!canEdit" class="tf-note">{{ t('testFailures.readOnly') }}</p>
        <p v-if="loading" class="tf-note" role="status">{{ t('testFailures.loading') }}</p>
        <p v-if="error" class="tf-error" role="alert">{{ error }} <button class="tf-link" type="button" @click="refresh">{{ t('testFailures.retry') }}</button></p>
        <div v-if="!loading && !error && !devices.length" class="tf-empty"><span class="tf-empty-category">{{ currentCategory }}</span><strong>{{ t(applied.confirmation === 'pending' ? 'testFailures.emptyPendingTitle' : 'testFailures.emptyTitle') }}</strong><p>{{ t('testFailures.emptyCategoryHint') }}</p><button v-if="applied.confirmation === 'pending' && (confirmationCounts?.confirmed ?? 0) > 0" type="button" class="tf-button" @click="selectConfirmation('confirmed')">{{ t('testFailures.viewConfirmed', { count: confirmationCounts?.confirmed ?? 0 }) }}</button></div>
        <div v-if="devices.length" class="tf-table-wrap">
          <table class="tf-table tf-device-table">
            <thead><tr><th>{{ t('testFailures.reportFolder') }}</th><th>{{ t('testFailures.summary') }}</th><th>{{ t('testFailures.confirmation') }}</th></tr></thead>
            <tbody><tr v-for="device in devices" :key="device.id">
              <td>
                <button class="tf-device-link tf-folder-name" type="button" @click="openReport(device)">{{ device.report_folder }}</button>
                <p class="tf-report-serial">{{ t('testFailures.serial') }}: <strong>{{ device.sn || '—' }}</strong></p>
                <p class="tf-device-classification"><span>{{ device.product || '—' }}</span><span class="tf-chip" :class="{ 'is-success': device.unconfirmed_count === 0 }">{{ t(device.unconfirmed_count > 0 ? 'testFailures.pendingOnly' : 'testFailures.confirmedOnly') }}</span></p>
                <p class="tf-report-time"><span>{{ t('testFailures.testTime') }}</span><time :datetime="device.last_test_at || undefined">{{ formatFailureTime(device.last_test_at, locale) }}</time></p>
                <p class="tf-report-count">{{ t('testFailures.reportCount', { count: device.report_count }) }}<span v-if="device.unconfirmed_count" class="tf-chip">{{ t('testFailures.pendingReports', { count: device.unconfirmed_count }) }}</span></p><button class="tf-link" type="button" @click="openReport(device)">{{ t('testFailures.details') }}</button>
                <TestFailureFolderReportLinks :device="device" />
              </td>
              <td><div class="tf-tags"><span v-for="kind in device.failure_types" :key="kind" class="tf-chip">{{ kindLabel(kind) }}</span></div><TestFailureSummary v-if="device.summary.length" :items="device.summary" /><p v-else class="tf-muted">{{ t('testFailures.noSummary') }}</p><p v-if="device.summary_omitted" class="tf-note">{{ t('testFailures.summaryOmitted', { count: device.summary_omitted }) }} <button class="tf-link" type="button" @click="openReport(device)">{{ t('testFailures.details') }}</button></p><TestFailureDeviceAnalysis :device="device" @refresh="loadDevices()" @view-report="openReport(device, $event)" /></td>
              <td>
                <ol v-if="recentConfirmations(device).length" class="tf-recent-confirmations" :aria-label="t('testFailures.recentConfirmations')">
                  <li v-for="(item, index) in recentConfirmations(device)" :key="item.id" class="tf-confirmation-card" :class="{ 'is-latest': index === 0 }">
                    <span class="tf-confirmation-label">{{ t(index === 0 ? 'testFailures.latestConfirmation' : 'testFailures.previousConfirmation') }}</span>
                    <p class="tf-confirmation-text">{{ item.text }}</p>
                    <small class="tf-confirmation-meta">{{ item.created_by_name || item.created_by }} · <time :datetime="item.created_at">{{ formatFailureTime(item.created_at, locale) }}</time></small>
                  </li>
                </ol>
                <p v-else class="tf-muted">{{ t('testFailures.noConfirmation') }}</p>
                <template v-if="canEdit">
                  <textarea :value="drafts[device.id]?.text || ''" rows="3" maxlength="4000" :aria-label="`${t('testFailures.confirmation')} ${device.report_folder}`" :placeholder="t('testFailures.placeholder')" :disabled="saving.has(device.id)" @input="editDraft(device, ($event.target as HTMLTextAreaElement).value)" />
                  <small class="tf-muted">{{ t('testFailures.signedBy') }}</small>
                  <p v-if="drafts[device.id]?.restored" class="tf-note">{{ t('testFailures.draftRestored') }}</p>
                  <p v-if="drafts[device.id]?.storageFailed" class="tf-note">{{ t('testFailures.draftStorageUnavailable') }}</p>
                  <p v-if="drafts[device.id]?.version && drafts[device.id].version !== device.version" class="tf-note">{{ t('testFailures.changed') }}</p>
                  <p v-if="drafts[device.id]?.error" class="tf-error" role="alert">{{ drafts[device.id].error }}</p>
                  <div class="tf-actions"><button class="tf-button is-primary" type="button" :disabled="saving.has(device.id) || !drafts[device.id]?.text.trim()" @click="save(device)">{{ t(saving.has(device.id) ? 'testFailures.saving' : 'testFailures.save') }}</button><button v-if="drafts[device.id]?.conflict || (drafts[device.id]?.version && drafts[device.id].version !== device.version)" class="tf-link" type="button" :disabled="loading" @click="loadDevices(device.id)">{{ t('testFailures.rebase') }}</button></div>
                </template>
                <button class="tf-link tf-history-link" type="button" @click="openHistory(device)">{{ t('testFailures.history') }}</button>
              </td>
            </tr></tbody>
          </table>
        </div>
        <div class="tf-pagination"><label>{{ t('testFailures.pageSize') }} <select :value="applied.page_size" @change="setPageSize(Number(($event.target as HTMLSelectElement).value))"><option :value="20">20</option><option :value="50">50</option><option :value="100">100</option></select></label><span>{{ t('testFailures.page', { page: applied.page, pages: pageCount }) }}</span><div class="tf-actions"><button class="tf-button" type="button" :disabled="applied.page <= 1 || loading" @click="changePage(applied.page - 1)">{{ t('testFailures.previous') }}</button><button class="tf-button" type="button" :disabled="applied.page >= pageCount || loading" @click="changePage(applied.page + 1)">{{ t('testFailures.next') }}</button></div></div>
      </section>
    </div>
    <TestFailureDetail :device="selectedDevice" :section="detailSection" :report-id="detailReportId" @close="selectedDevice = null; detailSection = 'reports'; detailReportId = ''" />
  </main>
</template>

<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, reactive, ref, watch } from 'vue'
import axios from 'axios'
import { RouterLink } from 'vue-router'
import AuthUserMenu from '@/components/AuthUserMenu.vue'
import LocaleSwitcher from '@/components/LocaleSwitcher.vue'
import productionsLogo from '@/assets/dashboard/productions-logo.svg'
import { useAppLocale } from '@/i18n'
import { chineseCopy, englishCopy } from '@/i18n/locales/defectSearch'
import { useAuthStore } from '@/scripts/stores/auth'
import { formatFailureTime, testFailuresApi, type FailureConfirmationFilter, type FailureDevice, type FailureDeviceQuery, type FailureDevicesResponse, type FailureKind, type FailureScan } from '@/scripts/api/testFailures'
import { defaultFailureReportId } from '@/scripts/utils/failureReportSelection'
import { createFailureDraftStorage } from '@/scripts/utils/failureDraftStorage'
import TestFailureDetail from './TestFailureDetail.vue'
import TestFailureSummary from './TestFailureSummary.vue'
import TestFailureDeviceAnalysis from './TestFailureDeviceAnalysis.vue'
import TestFailureFolderReportLinks from './TestFailureFolderReportLinks.vue'
import '@/styles/dashboard/defect-search.css'
import '@/styles/dashboard/test-failures.css'

const { t, locale } = useAppLocale()
const authStore = useAuthStore()
const canEdit = computed(() => Boolean(authStore.user && authStore.user.role !== 'viewer'))
const knowledgeCopy = computed(() => locale.value === 'en-US' ? englishCopy : chineseCopy)
const kinds: FailureKind[] = ['test_failure', 'runtime_error', 'mixed', 'incomplete']
const initialFilters = () => ({ q: '', mode: '', kind: '' as FailureKind | '', date_from: '', date_to: '' })
const filters = reactive(initialFilters())
const applied = reactive<FailureDeviceQuery>({ ...initialFilters(), product: '', confirmation: 'pending', page: 1, page_size: 20 })
const advancedFiltersOpen = ref(false)
const activeAdvancedFilters = computed(() => [
  { key: 'mode', value: applied.mode, text: `${t('testFailures.mode')}: ${applied.mode}` },
  { key: 'kind', value: applied.kind, text: applied.kind ? t(`testFailures.kinds.${applied.kind}`) : '' },
  { key: 'date_from', value: applied.date_from, text: `${t('testFailures.dateFrom')}: ${applied.date_from}` },
  { key: 'date_to', value: applied.date_to, text: `${t('testFailures.dateTo')}: ${applied.date_to}` },
].filter(item => item.value))
const response = ref<FailureDevicesResponse | null>(null)
const loadedQuery = ref<FailureDeviceQuery | null>(null)
const currentResults = computed(() => loadedQuery.value && JSON.stringify(loadedQuery.value) === JSON.stringify(applied))
const devices = computed(() => currentResults.value ? response.value?.devices || [] : [])
const facets = computed(() => response.value?.facets)
const productFacets = computed(() => facets.value?.products || [])
const confirmationCounts = computed(() => {
  if (loadedQuery.value?.product === applied.product) return facets.value?.confirmation
  return applied.product ? productFacets.value.find(item => item.product === applied.product) : facets.value?.all
})
const confirmationFilters = computed(() => [
  { value: 'pending' as const, label: 'testFailures.pendingOnly', count: confirmationCounts.value?.pending },
  { value: 'confirmed' as const, label: 'testFailures.confirmedOnly', count: confirmationCounts.value?.confirmed },
  { value: 'all' as const, label: 'testFailures.all', count: confirmationCounts.value?.total },
])
const currentCategory = computed(() => `${applied.product || t('testFailures.allProducts')} · ${t(confirmationFilters.value.find(item => item.value === applied.confirmation)?.label || 'testFailures.all')}`)
const summaryCards = computed(() => [
  { key: 'devices', value: response.value?.summary.devices || 0 },
  { key: 'pending', value: response.value?.summary.pending || 0 },
  { key: 'reports', value: response.value?.summary.reports || 0 },
  { key: 'parseErrors', value: response.value?.summary.parse_errors || 0 },
])
const pageCount = computed(() => Math.max(1, Math.ceil((response.value?.total || 0) / applied.page_size)))
const loading = ref(false)
const error = ref('')
const filterError = ref('')
const scan = ref<FailureScan | null>(null)
const scanError = ref('')
const startingScan = ref(false)
const selectedDevice = ref<FailureDevice | null>(null)
const detailSection = ref<'reports' | 'history'>('reports')
const detailReportId = ref('')
interface Draft { text: string; version: string; error: string; conflict: boolean; restored?: boolean; storageFailed?: boolean }
const drafts = reactive<Record<string, Draft>>({})
const draftStorage = createFailureDraftStorage()
const draftUserId = computed(() => authStore.user?.id || '')
const saving = reactive(new Set<string>())
const savedReportFolder = ref('')
let listController: AbortController | null = null
let scanController: AbortController | null = null
const mutationControllers = new Set<AbortController>()
let pollTimer: ReturnType<typeof setTimeout> | undefined
let stopped = false
let reloadAfterScan = false

function kindLabel(kind: string): string { return kinds.includes(kind as FailureKind) ? t(`testFailures.kinds.${kind}`) : kind }
function facetCount(value: number | undefined): string { return value == null ? '—' : value.toLocaleString() }
function recentConfirmations(device: FailureDevice) {
  return (device.recent_confirmations ?? (device.confirmation ? [device.confirmation] : [])).slice(0, 2)
}
function selectProduct(product: string): void { applied.product = product; applied.page = 1; void loadDevices() }
function selectConfirmation(confirmation: FailureConfirmationFilter): void { applied.confirmation = confirmation; applied.page = 1; void loadDevices() }
function openReport(device: FailureDevice, reportId = ''): void { detailSection.value = 'reports'; detailReportId.value = reportId || defaultFailureReportId(device); selectedDevice.value = device }
function openHistory(device: FailureDevice): void { detailSection.value = 'history'; detailReportId.value = ''; selectedDevice.value = device }
function editDraft(device: FailureDevice, text: string): void {
  const draft = drafts[device.id] || { text: '', version: device.version, error: '', conflict: false }
  draft.text = text
  if (!draft.conflict) draft.error = ''
  drafts[device.id] = draft
  draft.storageFailed = !draftStorage.write(draftUserId.value, device.id, draft)
}
function restoreDraft(device: FailureDevice): void {
  if (drafts[device.id]) return
  const stored = draftStorage.read(draftUserId.value, device.id)
  if (stored) drafts[device.id] = { ...stored, error: '', conflict: false, restored: true }
}
watch(draftUserId, () => {
  for (const id of Object.keys(drafts)) delete drafts[id]
  for (const device of devices.value) restoreDraft(device)
}, { flush: 'sync' })
async function loadDevices(rebaseDraftId?: string): Promise<void> {
  listController?.abort()
  const controller = new AbortController(); listController = controller
  loading.value = true; error.value = ''
  try {
    const query = { ...applied }
    const { data } = await testFailuresApi.devices(query, controller.signal)
    if (controller.signal.aborted) return
    response.value = data; loadedQuery.value = query; scan.value = data.scan
    if (data.total > 0 && applied.page > Math.ceil(data.total / applied.page_size)) {
      applied.page = Math.ceil(data.total / applied.page_size); void loadDevices(rebaseDraftId); return
    }
    if (data.total === 0) { applied.page = 1; loadedQuery.value.page = 1 }
    for (const device of data.devices) {
      if (selectedDevice.value?.id === device.id) selectedDevice.value = device
      restoreDraft(device)
      if (device.id === rebaseDraftId && drafts[device.id] && !saving.has(device.id)) {
        drafts[device.id].version = device.version; drafts[device.id].conflict = false; drafts[device.id].error = ''
        drafts[device.id].storageFailed = !draftStorage.write(draftUserId.value, device.id, drafts[device.id])
      }
    }
  } catch {
    if (!controller.signal.aborted) error.value = t('testFailures.loadFailed')
  } finally {
    if (listController === controller) loading.value = false
  }
}
function applyFilters(event?: Event): void {
  const form = event?.currentTarget as HTMLFormElement | undefined
  if (form && Array.from(form.querySelectorAll<HTMLInputElement>('input[type="date"]')).some(input => input.validity.badInput)) {
    advancedFiltersOpen.value = true; filterError.value = t('testFailures.dateIncomplete'); return
  }
  if (filters.date_from && filters.date_to && filters.date_from > filters.date_to) { advancedFiltersOpen.value = true; filterError.value = t('testFailures.dateInvalid'); return }
  filterError.value = ''; Object.assign(applied, filters, { q: filters.q.trim(), page: 1 }); void loadDevices()
}
function resetFilters(): void { Object.assign(filters, initialFilters()); applied.product = ''; applied.confirmation = 'pending'; applyFilters() }
function changePage(page: number): void { applied.page = page; void loadDevices() }
function setPageSize(size: number): void { applied.page_size = size; applied.page = 1; void loadDevices() }
function refresh(): void { void loadDevices(); void pollScan() }

function schedulePoll(): void {
  if (pollTimer) clearTimeout(pollTimer)
  if (!stopped) pollTimer = setTimeout(() => { void pollScan() }, scan.value?.running ? 2000 : 15000)
}
async function pollScan(): Promise<void> {
  if (stopped) return
  if (pollTimer) clearTimeout(pollTimer)
  scanController?.abort()
  const controller = new AbortController(); scanController = controller
  try {
    const { data } = await testFailuresApi.scan(controller.signal)
    if (controller.signal.aborted) return
    const changed = Boolean(scan.value && (scan.value.running || scan.value.last_scan_at !== data.last_scan_at) && !data.running)
    scan.value = data; scanError.value = ''
    if (changed) reloadAfterScan = true
    if (reloadAfterScan && !data.running && !loading.value && saving.size === 0) { reloadAfterScan = false; await loadDevices() }
  } catch {
    if (!controller.signal.aborted) scanError.value = t('testFailures.scanFailed')
  } finally {
    if (scanController === controller) schedulePoll()
  }
}
async function startScan(): Promise<void> {
  if (!canEdit.value || startingScan.value || scan.value?.running) return
  const controller = new AbortController(); mutationControllers.add(controller)
  startingScan.value = true; scanError.value = ''
  try {
    const { data } = await testFailuresApi.startScan(controller.signal)
    if (controller.signal.aborted) return
    scan.value = data; reloadAfterScan = true; void pollScan()
  } catch {
    if (!controller.signal.aborted) scanError.value = t('testFailures.scanFailed')
  } finally {
    mutationControllers.delete(controller); startingScan.value = false
  }
}
async function save(device: FailureDevice): Promise<void> {
  const draft = drafts[device.id]
  if (!canEdit.value || !draft?.text.trim() || saving.has(device.id)) return
  const controller = new AbortController(); mutationControllers.add(controller)
  const userId = draftUserId.value
  const submitted = { text: draft.text, version: draft.version }
  saving.add(device.id); draft.error = ''; savedReportFolder.value = ''
  try {
    const { data } = await testFailuresApi.confirm(device.id, submitted.text.trim(), submitted.version, controller.signal)
    if (controller.signal.aborted) return
    const stored = draftStorage.read(userId, device.id)
    if (stored?.text === submitted.text && stored.version === submitted.version) draftStorage.remove(userId, device.id)
    if (draftUserId.value !== userId) return
    if (drafts[device.id] === draft && draft.text === submitted.text && draft.version === submitted.version) delete drafts[device.id]
    savedReportFolder.value = data.device.report_folder
    // The confirmation response has no active filter context. Retain this view's
    // matched evidence until the filtered list response is available.
    const displayed = response.value?.devices.find(item => item.id === device.id) || device
    const updatedDevice = { ...data.device, ...(displayed.matched_report_ids ? {
      matched_report_ids: displayed.matched_report_ids.filter(id => data.device.reports.some(report => report.id === id)),
    } : {}) }
    if (response.value) response.value.devices = response.value.devices
      .map(item => item.id === device.id ? updatedDevice : item)
      .filter(item => applied.confirmation === 'pending' ? item.unconfirmed_count > 0 : applied.confirmation === 'confirmed' ? item.unconfirmed_count === 0 : true)
    if (selectedDevice.value?.id === device.id) selectedDevice.value = updatedDevice
    await loadDevices()
  } catch (value) {
    if (controller.signal.aborted || draftUserId.value !== userId) return
    draft.conflict = axios.isAxiosError(value) && value.response?.status === 409
    draft.error = t(draft.conflict ? 'testFailures.conflict' : 'testFailures.saveFailed')
  } finally {
    mutationControllers.delete(controller); saving.delete(device.id)
  }
}
onMounted(async () => { await loadDevices(); if (!stopped) void pollScan() })
onBeforeUnmount(() => {
  stopped = true; if (pollTimer) clearTimeout(pollTimer)
  listController?.abort(); scanController?.abort(); mutationControllers.forEach(controller => controller.abort())
})
</script>
