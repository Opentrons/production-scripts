<template>
  <el-drawer :model-value="Boolean(device)" :title="`${t('testFailures.reportDetail')} · ${device?.sn || ''}`" size="min(1100px, 96vw)" append-to-body destroy-on-close @close="emit('close')" @opened="focusSection">
    <div v-if="device" class="tf-detail">
      <div class="tf-detail-heading">
        <div class="tf-detail-folder">
          <span class="tf-muted">{{ t('testFailures.reportFolder') }}</span>
          <strong class="tf-folder-name">{{ device.report_folder }}</strong>
          <span>{{ t('testFailures.serial') }}: {{ device.sn || '—' }} · {{ device.product || '—' }}</span>
          <p class="tf-report-time"><span>{{ t('testFailures.testTime') }}</span><time :datetime="device.last_test_at || undefined">{{ formatFailureTime(device.last_test_at, locale) }}</time></p>
        </div>
      </div>
      <div class="tf-report-layout">
        <nav class="tf-report-list" :aria-label="t('testFailures.reportList')">
          <h3>{{ t('testFailures.reportList') }} ({{ device.reports.length }})</h3>
          <p v-if="!device.reports.length" class="tf-muted">{{ t('testFailures.noReports') }}</p>
          <section v-for="group in reportGroups" :key="group.id" class="tf-report-run">
            <h4>{{ formatFailureTime(group.reports[0]?.test_time, locale) }}</h4>
            <button v-for="item in group.reports" :key="item.id" type="button" :class="{ 'is-active': selectedId === item.id }" :aria-current="selectedId === item.id ? 'true' : undefined" @click="selectReport(item.id)">
              <strong>{{ reportLabel(item) }}</strong>
              <span>{{ item.mode || '—' }} · {{ kindLabel(item.kind) }}</span>
              <small>{{ item.stage || '—' }} · {{ parseLabel(item.parse_status) }}</small>
              <small v-if="item.confirmation_status">{{ t(item.confirmation_status === 'confirmed' ? 'testFailures.packageConfirmed' : 'testFailures.packagePending') }}</small>
            </button>
          </section>
        </nav>
        <div class="tf-report-body" aria-live="polite">
          <p v-if="selectionNotice" class="tf-note" role="status">{{ t('testFailures.selectionChanged') }}</p>
          <p v-if="loading">{{ t('testFailures.loading') }}</p>
          <p v-else-if="error" class="tf-error" role="alert">{{ error }} <button class="tf-link" type="button" @click="selectReport(selectedId)">{{ t('testFailures.retry') }}</button></p>
          <template v-else-if="report">
            <div class="tf-report-meta">
              <span class="tf-chip">{{ kindLabel(report.kind) }}</span><span class="tf-chip is-neutral">{{ parseLabel(report.parse_status) }}</span>
              <span>{{ report.mode || '—' }} · {{ t('testFailures.stage') }}: {{ report.stage || '—' }}</span>
            </div>
            <p class="tf-source">{{ t('testFailures.source') }}: {{ report.source_name }}</p>
            <TestFailureReportLink :report="report" show-identity />
            <aside v-if="report.report_role === 'right_reference'" class="tf-reference-note">
              <strong>{{ reportLabel(report) }}</strong>
              <p>{{ t('testFailures.referenceSnapshotNote') }}</p>
              <p v-if="report.reference_handled === true">{{ t('testFailures.referenceHandled') }}</p>
              <button v-if="relatedMain" class="tf-link" type="button" @click="selectReport(relatedMain.id)">{{ t('testFailures.viewRunReport') }}</button>
            </aside>
            <div v-if="knowledgeQueries.length" class="tf-knowledge-search">
              <label class="tf-knowledge-field"><span>{{ t('testFailures.knowledgeFailure') }}</span><select v-model="selectedKnowledgeQuery" :aria-describedby="`tf-knowledge-hint-${report.id}`"><option v-for="query in knowledgeQueries" :key="query" :value="query">{{ query }}</option></select></label>
              <RouterLink v-if="knowledgeLink" class="tf-button" :to="knowledgeLink" target="_blank" rel="noopener noreferrer" :aria-describedby="`tf-knowledge-hint-${report.id}`">{{ t('testFailures.knowledge') }}</RouterLink>
              <p :id="`tf-knowledge-hint-${report.id}`" class="tf-note">{{ t(knowledgeProduct ? 'testFailures.knowledgeHint' : 'testFailures.knowledgeHintWithoutProduct') }}<span v-if="report.product.trim() && !knowledgeProduct"> {{ t('testFailures.knowledgeProductOmitted') }}</span></p>
            </div>
            <p v-else class="tf-note">{{ t('testFailures.knowledgeEmpty') }}</p>
            <TestFailureSummary v-if="report.summary.length" :items="report.summary" />

            <TestFailureAnalysis :key="report.id + report.revision" :report-id="report.id" :report-revision="report.revision" :evidence-version="report.evidence_version" @refresh-report="selectReport(selectedId)" />

            <section class="tf-detail-section">
              <h3>{{ t('testFailures.failures') }} ({{ report.failures.length }})</h3>
              <p v-if="!report.failures.length" class="tf-note">{{ t('testFailures.noFailures') }}</p>
              <article v-for="(item, i) in report.failures" :key="item.evidence_id || i" class="tf-evidence">
                <strong>{{ item.section || '—' }} / {{ item.tag || '—' }} <span v-if="item.index != null" class="tf-muted">· {{ t('testFailures.index') }} {{ item.index }}</span></strong>
                <dl class="tf-key-values">
                  <dt>{{ t('testFailures.result') }}</dt><dd>{{ failureValue(item.result) }}</dd>
                  <dt>{{ t('testFailures.errorCodes') }}</dt><dd>{{ item.error_codes?.join(', ') || '—' }}</dd>
                  <dt>{{ t('testFailures.reasons') }}</dt><dd>{{ item.failure_reasons?.join('\n') || '—' }}</dd>
                  <dt>{{ t('testFailures.elapsed') }}</dt><dd>{{ item.elapsed_seconds ?? '—' }}</dd>
                </dl>
                <details v-if="item.data != null"><summary>{{ t('testFailures.evidence') }}</summary><pre class="tf-code">{{ failureValue(item.data) }}</pre></details>
              </article>
            </section>

            <section class="tf-detail-section">
              <h3>{{ t('testFailures.tests') }}</h3><p class="tf-note">{{ t('testFailures.statusNote') }}</p>
              <p v-if="!Object.keys(report.tests).length" class="tf-muted">{{ t('testFailures.noTests') }}</p>
              <div v-else class="tf-table-wrap"><table class="tf-table tf-test-table"><thead><tr><th>{{ t('testFailures.section') }}</th><th>{{ t('testFailures.result') }}</th><th>{{ t('testFailures.reasons') }}</th></tr></thead><tbody>
                <tr v-for="(test, name) in report.tests" :key="name"><td>{{ name }}</td><td><span class="tf-chip" :class="statusClass(test.status)">{{ statusLabel(test.status) }}</span></td><td><pre>{{ failureValue(test.error ?? test.last_handled_exception) }}</pre><small v-if="test.blocking_stage">{{ t('testFailures.stage') }}: {{ test.blocking_stage }}</small></td></tr>
              </tbody></table></div>
            </section>

            <section v-if="report.runtime_error" class="tf-detail-section"><h3>{{ t('testFailures.runtime') }}</h3><pre class="tf-code is-error">{{ failureValue(report.runtime_error) }}</pre></section>
            <section v-if="report.last_failure" class="tf-detail-section"><h3>{{ t('testFailures.lastFailure') }}</h3><pre class="tf-code">{{ failureValue(report.last_failure) }}</pre></section>
            <section v-if="report.recommendations.length" class="tf-detail-section">
              <h3>{{ t('testFailures.recommendations') }}</h3><p class="tf-note">{{ t('testFailures.recommendationNote') }}</p>
              <article v-for="(item, i) in report.recommendations" :key="i" class="tf-evidence">
                <strong>{{ categoryLabel(item.category) }} <span class="tf-muted">· {{ recommendationStatusLabel(item.status) }}</span></strong>
                <dl class="tf-key-values"><dt>{{ t('testFailures.nextChecks') }}</dt><dd><ul class="tf-check-list"><li v-for="(line, index) in displayLines(item.next_checks)" :key="index">{{ line }}</li></ul></dd><dt>{{ t('testFailures.retest') }}</dt><dd><p v-for="(line, index) in displayLines(item.retest)" :key="index">{{ line }}</p></dd></dl>
                <details><summary>{{ t('testFailures.evidence') }}</summary><pre class="tf-code">{{ failureValue(item.evidence) }}</pre></details>
              </article>
            </section>
            <section v-if="report.warnings.length" class="tf-detail-section"><h3>{{ t('testFailures.warnings') }}</h3><ul class="tf-summary-list"><li v-for="(warning, i) in report.warnings" :key="i">{{ warning }}</li></ul></section>
            <details class="tf-detail-section"><summary>{{ t('testFailures.rawReport') }}</summary><p class="tf-source">{{ t('testFailures.revision') }}: {{ report.revision }}</p><strong>{{ t('testFailures.identity') }}</strong><pre class="tf-code">{{ failureValue(report.identity) }}</pre></details>
            <TestFailureAttachments :key="report.id + report.revision + (report.evidence_version || '')" :report-id="report.id" :attachments="report.attachments" />
          </template>
        </div>
      </div>

      <section ref="historySection" class="tf-detail-section tf-history" tabindex="-1">
        <div class="tf-section-heading"><h3>{{ t('testFailures.history') }}</h3><button class="tf-link" type="button" :disabled="historyLoading" @click="loadHistory">{{ t('testFailures.refresh') }}</button></div>
        <p v-if="historyLoading">{{ t('testFailures.loading') }}</p>
        <p v-else-if="historyError" class="tf-error" role="alert">{{ historyError }} <button class="tf-link" type="button" @click="loadHistory">{{ t('testFailures.retry') }}</button></p>
        <p v-else-if="!history.length" class="tf-muted">{{ t('testFailures.historyEmpty') }}</p>
        <article v-for="item in history" :key="item.id" class="tf-history-entry">
          <p>{{ item.text }}</p><small>{{ item.created_by_name || item.created_by }} · {{ formatFailureTime(item.created_at, locale) }}</small>
          <details v-if="item.coverage?.length" class="tf-confirmation-coverage">
            <summary>{{ t('testFailures.coverage', { count: item.coverage.length }) }}</summary>
            <ul>
              <li v-for="covered in item.coverage" :key="covered.report_id + covered.revision">
                <strong>{{ covered.source_name || covered.report_id }}</strong>
                <span class="tf-chip" :class="covered.current ? 'is-success' : 'is-neutral'">{{ t(covered.current ? 'testFailures.coverageCurrent' : 'testFailures.coverageHistorical') }}</span>
                <p v-if="covered.metadata_recorded">{{ covered.report_folder }} · {{ t(covered.report_role === 'right_reference' ? 'testFailures.referenceEvidence' : 'testFailures.mainReport') }} · {{ formatFailureTime(covered.test_time, locale) }}</p>
                <p v-else class="tf-muted">{{ t('testFailures.coverageLegacy') }}</p>
                <small>{{ t('testFailures.revision') }}: <code>{{ covered.revision }}</code></small>
              </li>
            </ul>
          </details>
        </article>
      </section>
    </div>
  </el-drawer>
</template>

<script setup lang="ts">
import { computed, onBeforeUnmount, ref, watch } from 'vue'
import { RouterLink } from 'vue-router'
import { useAppLocale } from '@/i18n'
import { testFailuresEn } from '@/i18n/locales/testFailures'
import { failureValue, formatFailureTime, testFailuresApi, type FailureConfirmation, type FailureDevice, type FailureKind, type FailureReport, type FailureReportSummary } from '@/scripts/api/testFailures'
import { failureKnowledgeProduct, failureKnowledgeQueries } from '@/scripts/utils/failureKnowledge'
import { defaultFailureReportId } from '@/scripts/utils/failureReportSelection'
import TestFailureAttachments from './TestFailureAttachments.vue'
import TestFailureAnalysis from './TestFailureAnalysis.vue'
import TestFailureSummary from './TestFailureSummary.vue'
import TestFailureReportLink from './TestFailureReportLink.vue'

const props = defineProps<{ device: FailureDevice | null; section?: 'reports' | 'history'; reportId?: string }>()
const emit = defineEmits<{ close: [] }>()
const { t, locale } = useAppLocale()
const selectedId = ref('')
const report = ref<FailureReport | null>(null)
const loading = ref(false)
const error = ref('')
const selectionNotice = ref(false)
const history = ref<FailureConfirmation[]>([])
const historyLoading = ref(false)
const historyError = ref('')
const historySection = ref<HTMLElement | null>(null)
let reportController: AbortController | null = null
let reportRequestKey = ''
let historyController: AbortController | null = null
const selectedKnowledgeQuery = ref('')
const reportGroups = computed(() => {
  const groups = new Map<string, { id: string; reports: FailureReportSummary[] }>()
  for (const item of props.device?.reports || []) {
    const id = item.run_group_id || item.id
    if (!groups.has(id)) groups.set(id, { id, reports: [] })
    groups.get(id)!.reports.push(item)
  }
  for (const group of groups.values()) {
    group.reports.sort((a, b) => Number(a.report_role === 'right_reference') - Number(b.report_role === 'right_reference')
      || (a.reference_tip_volume_ul || 0) - (b.reference_tip_volume_ul || 0))
  }
  return [...groups.values()]
})
const relatedMain = computed(() => report.value?.run_group_id
  ? props.device?.reports.find(item => item.id !== report.value?.id && item.report_folder === report.value?.report_folder && item.run_group_id === report.value?.run_group_id && item.report_role === 'main')
  : undefined)
const knowledgeQueries = computed(() => !loading.value && report.value ? failureKnowledgeQueries(report.value.summary) : [])
const knowledgeProduct = computed(() => failureKnowledgeProduct(report.value?.product || ''))
const knowledgeLink = computed(() => {
  const q = selectedKnowledgeQuery.value
  if (!report.value || !q || !knowledgeQueries.value.includes(q)) return null
  return { name: 'DefectSearch', query: { q, ...(knowledgeProduct.value ? { product: knowledgeProduct.value } : {}) } }
})
watch(knowledgeQueries, queries => {
  if (!queries.includes(selectedKnowledgeQuery.value)) selectedKnowledgeQuery.value = queries[0] || ''
})

function focusSection(): void {
  if (props.section === 'history') { historySection.value?.scrollIntoView({ block: 'start' }); historySection.value?.focus({ preventScroll: true }) }
}

function kindLabel(kind: FailureKind): string { return t(`testFailures.kinds.${kind}`) }
function reportLabel(item: FailureReportSummary): string {
  return item.report_role === 'right_reference'
    ? t('testFailures.referenceSnapshot', { volume: item.reference_tip_volume_ul ?? '—' })
    : t(item.stage === 'result-summary' ? 'testFailures.finalReport' : 'testFailures.mainReport')
}
function parseLabel(status: FailureReport['parse_status']): string { return t(`testFailures.parse.${status}`) }
function categoryLabel(category: string): string {
  return category in testFailuresEn.categories ? t(`testFailures.categories.${category}`) : category
}
function recommendationStatusLabel(status: string): string {
  return status in testFailuresEn.recommendationStatuses ? t(`testFailures.recommendationStatuses.${status}`) : status
}
function displayLines(value: unknown): string[] {
  if (Array.isArray(value)) return value.length ? value.map(failureValue) : ['—']
  return [failureValue(value)]
}
function normalizedStatus(value: string): string {
  const status = String(value || '').toLowerCase().replace(/[\s-]+/g, '_')
  if (['pass', 'passed', 'success', 'succeeded', 'ok'].includes(status)) return 'pass'
  if (['fail', 'failed', 'failure', 'ng'].includes(status)) return 'fail'
  if (['not_run', 'not_executed', 'unexecuted', 'notrun'].includes(status)) return 'not_run'
  if (status === 'not_started') return 'not_started'
  if (status === 'not_run_due_to_previous_failure') return 'blocked'
  if (status === 'skipped_by_configuration') return 'skipped_configuration'
  if (['skip', 'skipped'].includes(status)) return 'skipped'
  if (['error', 'errored', 'runtime_error', 'execution_error', 'exception'].includes(status)) return 'error'
  if (['running', 'completed', 'pending'].includes(status)) return status
  return 'unknown'
}
function statusLabel(status: string): string {
  const normalized = normalizedStatus(status)
  return `${t(`testFailures.statuses.${normalized}`)}${normalized === 'unknown' && status ? ` (${status})` : ''}`
}
function statusClass(status: string): string {
  const normalized = normalizedStatus(status)
  return ['fail', 'error'].includes(normalized) ? 'is-failure' : normalized === 'pass' ? 'is-success' : 'is-neutral'
}
async function selectReport(id: string): Promise<void> {
  reportController?.abort()
  const expected = props.device?.reports.find(item => item.id === id)
  reportRequestKey = JSON.stringify([id, expected?.revision || '', expected?.evidence_version || ''])
  selectedId.value = id; report.value = null; error.value = ''; selectedKnowledgeQuery.value = ''
  if (!id) { loading.value = false; return }
  const controller = new AbortController(); reportController = controller; loading.value = true
  try {
    const { data } = await testFailuresApi.report(id, controller.signal)
    if (!controller.signal.aborted) report.value = data
  } catch {
    if (!controller.signal.aborted) error.value = t('testFailures.reportFailed')
  } finally {
    if (reportController === controller) loading.value = false
  }
}
async function loadHistory(): Promise<void> {
  historyController?.abort()
  if (!props.device) return
  const controller = new AbortController(); historyController = controller
  historyLoading.value = true; historyError.value = ''
  try {
    const { data } = await testFailuresApi.confirmations(props.device.id, controller.signal)
    if (!controller.signal.aborted) history.value = data.items
  } catch {
    if (!controller.signal.aborted) historyError.value = t('testFailures.historyFailed')
  } finally {
    if (historyController === controller) historyLoading.value = false
  }
}
watch([() => props.device?.id, () => props.reportId,
  () => JSON.stringify(props.device?.reports.map(item => [item.id, item.revision, item.evidence_version]))], ([deviceId, requestedId], previous) => {
  if (!props.device) { void selectReport(''); selectionNotice.value = false; return }
  const opening = deviceId !== previous?.[0] || requestedId !== previous?.[1]
  const available = (id: string) => props.device!.reports.some(item => item.id === id)
  // An explicit evidence link must never silently open a different report.
  if (opening && requestedId && !available(requestedId)) {
    void selectReport(''); error.value = t('testFailures.reportUnavailable'); selectionNotice.value = false; return
  }
  const previousId = opening ? '' : selectedId.value
  const nextId = (opening ? requestedId : available(previousId) ? previousId : '') || defaultFailureReportId(props.device)
  selectionNotice.value = Boolean(previousId && !available(previousId))
  const nextReport = props.device.reports.find(item => item.id === nextId)
  const nextKey = JSON.stringify([nextId, nextReport?.revision || '', nextReport?.evidence_version || ''])
  // A list refresh or confirmation never tears down unchanged evidence/attachments.
  if (opening || nextKey !== reportRequestKey) void selectReport(nextId)
}, { immediate: true })
watch([() => props.device?.id, () => props.device?.version], ([deviceId], previous) => {
  if (deviceId !== previous?.[0]) { historyController?.abort(); history.value = []; historyError.value = ''; historyLoading.value = false }
  if (props.device) void loadHistory()
}, { immediate: true })
onBeforeUnmount(() => { reportController?.abort(); historyController?.abort() })
</script>
