<template>
  <section class="tf-detail-section tf-analysis" :class="{ 'is-compact': compact }" :aria-busy="loading || starting || analysis?.status === 'running'">
    <div class="tf-section-heading">
      <h3>{{ t('testFailures.analysis.title') }}</h3>
      <div class="tf-actions">
        <button class="tf-link" type="button" :disabled="starting || (loading && !queued) || manualRefreshing" @click="refreshAnalysis">{{ t(manualRefreshing || (loading && !queued) ? 'testFailures.analysis.refreshing' : 'testFailures.analysis.refresh') }}</button>
        <button v-if="canEdit && canGenerate" class="tf-button is-primary" type="button" :disabled="loading || starting" @click="startAnalysis">{{ t(starting ? 'testFailures.analysis.starting' : analysis?.status === 'idle' ? 'testFailures.analysis.generate' : 'testFailures.analysis.regenerate') }}</button>
      </div>
    </div>
    <slot name="source" />
    <p class="tf-note">{{ t(compact ? 'testFailures.analysis.compactNote' : 'testFailures.analysis.note') }}</p>
    <p class="tf-note">{{ t('testFailures.analysis.refreshHint') }}</p>
    <p v-if="errorKey" class="tf-error" role="alert">{{ t(errorKey) }}</p>
    <button v-if="revisionChanged || conflict" class="tf-link" type="button" @click="refreshReport">{{ t('testFailures.analysis.refreshReport') }}</button>
    <p v-if="loading" class="tf-muted" role="status">{{ t(queued ? 'testFailures.analysis.queued' : 'testFailures.analysis.refreshing') }}</p>
    <p v-else-if="checkedAt && !errorKey && !starting" class="tf-success" role="status">{{ t('testFailures.analysis.refreshed', { time: formatFailureTime(checkedAt, locale) }) }}</p>
    <template v-if="analysis">
      <div class="tf-analysis-meta" role="status">
        <span class="tf-chip" :class="analysis.status === 'failed' ? 'is-failure' : analysis.status === 'complete' ? 'is-success' : analysis.status === 'running' ? 'is-running' : 'is-neutral'">{{ t(`testFailures.analysis.statuses.${analysis.status}`) }}</span>
        <span class="tf-chip is-neutral">{{ t(`testFailures.analysis.modes.${analysis.mode}`) }}</span>
        <span v-if="analysis.generated_at">{{ t('testFailures.analysis.generatedAt') }}: {{ formatFailureTime(analysis.generated_at, locale) }}</span>
      </div>
      <p v-if="analysis.status === 'idle'" class="tf-note">{{ t('testFailures.analysis.idleHint') }}</p>
      <p v-if="analysis.status === 'running'" class="tf-note">{{ t('testFailures.analysis.runningHint') }}</p>
      <p v-if="analysis.status === 'stale'" class="tf-note">{{ t('testFailures.analysis.staleHint') }}</p>
      <p v-if="analysis.status === 'unsupported'" class="tf-note">{{ t('testFailures.analysis.unsupportedHint') }}</p>
      <p v-if="analysis.status === 'failed'" class="tf-error">{{ t('testFailures.analysis.failedHint') }}</p>
      <p v-if="analysis.error && ['failed', 'unsupported', 'stale'].includes(analysis.status)" class="tf-error" role="alert">{{ analysis.error }}</p>
      <p v-if="!canEdit && canGenerate" class="tf-muted">{{ t('testFailures.analysis.readOnlyHint') }}</p>
      <template v-if="analysis.status === 'complete' && analysis.result">
        <p class="tf-note">{{ t(hasModelAssessments ? 'testFailures.analysis.modelHint' : 'testFailures.analysis.rulesHint') }}<span v-if="hasModelAssessments && analysis.result.model_analysis.model"> · {{ analysis.result.model_analysis.model }}</span></p>
        <p v-if="!findings.length" class="tf-note">{{ t('testFailures.analysis.noFindings') }}</p>
        <template v-if="compact && !expanded">
          <p v-if="findings.length" class="tf-analysis-preview-count">{{ t('testFailures.analysis.previewCount', { shown: Math.min(2, findings.length), total: findings.length }) }}</p>
          <article v-for="finding in findings.slice(0, 2)" :key="finding.finding_id" class="tf-analysis-preview">
            <div class="tf-analysis-finding-heading"><strong>{{ categoryLabel(finding.category) }}</strong><span v-if="assessmentFor(finding.finding_id)" class="tf-chip is-neutral">{{ t('testFailures.analysis.priority', { value: assessmentFor(finding.finding_id)?.priority ?? '' }) }}</span></div>
            <p class="tf-muted">{{ findingStatusLabel(finding.status) }}</p>
            <p class="tf-analysis-observed tf-analysis-excerpt">{{ failureValue(finding.observed) }}</p>
            <dl class="tf-analysis-preview-values">
              <dt>{{ t('testFailures.analysis.firstChecks') }}</dt><dd><ol class="tf-check-list"><li v-for="(line, index) in displayLines(finding.checks).slice(0, 2)" :key="index" class="tf-analysis-excerpt">{{ line }}</li></ol></dd>
              <dt>{{ t('testFailures.analysis.direction') }}</dt><dd class="tf-analysis-excerpt">{{ displayLines(finding.direction)[0] }}</dd>
              <dt>{{ t('testFailures.retest') }}</dt><dd class="tf-analysis-excerpt">{{ displayLines(finding.retest)[0] }}</dd>
            </dl>
          </article>
          <p v-if="analysis.result.evidence.blocked_tests.length" class="tf-note tf-analysis-blocked-note">{{ t('testFailures.analysis.blockedCount', { count: analysis.result.evidence.blocked_tests.length }) }}</p>
        </template>
        <template v-else>
        <article v-for="finding in findings" :key="finding.finding_id" class="tf-evidence tf-analysis-finding">
          <div class="tf-analysis-finding-heading"><strong>{{ finding.finding_id }} · {{ categoryLabel(finding.category) }}</strong><span v-if="assessmentFor(finding.finding_id)" class="tf-chip is-neutral">{{ t('testFailures.analysis.priority', { value: assessmentFor(finding.finding_id)?.priority ?? '' }) }}</span></div>
          <p class="tf-muted">{{ findingStatusLabel(finding.status) }}</p>
          <p class="tf-analysis-observed">{{ failureValue(finding.observed) }}</p>
          <dl class="tf-key-values">
            <dt>{{ t('testFailures.nextChecks') }}</dt><dd><ol class="tf-check-list"><li v-for="(line, index) in displayLines(finding.checks)" :key="index">{{ line }}</li></ol></dd>
            <dt>{{ t('testFailures.analysis.direction') }}</dt><dd><p v-for="(line, index) in displayLines(finding.direction)" :key="index">{{ line }}</p></dd>
            <dt>{{ t('testFailures.retest') }}</dt><dd><p v-for="(line, index) in displayLines(finding.retest)" :key="index">{{ line }}</p></dd>
          </dl>
          <div v-if="assessmentFor(finding.finding_id)" class="tf-analysis-reasoning">
            <strong>{{ t('testFailures.analysis.modelReasoning') }}</strong>
            <p>{{ assessmentFor(finding.finding_id)?.reasoning }}</p>
            <p v-if="assessmentFor(finding.finding_id)?.next_question"><strong>{{ t('testFailures.analysis.nextQuestion') }}: </strong>{{ assessmentFor(finding.finding_id)?.next_question }}</p>
          </div>
          <details><summary>{{ t('testFailures.evidence') }} ({{ finding.evidence_refs.length }})</summary>
            <div v-for="reference in finding.evidence_refs" :key="reference" class="tf-analysis-evidence"><code>{{ reference }}</code><pre class="tf-code">{{ evidenceFor(reference) }}</pre></div>
            <details v-if="finding.threshold_evidence_refs?.length"><summary>{{ t('testFailures.analysis.thresholds') }}</summary><div v-for="reference in finding.threshold_evidence_refs" :key="reference" class="tf-analysis-evidence"><code>{{ reference }}</code><pre class="tf-code">{{ evidenceFor(reference) }}</pre></div></details>
            <p v-if="finding.omitted_evidence_refs" class="tf-note">{{ t('testFailures.analysis.omittedEvidence', { count: finding.omitted_evidence_refs }) }}</p>
          </details>
        </article>
        <div v-if="analysis.result.evidence.blocked_tests.length" class="tf-analysis-blocked">
          <h4>{{ t('testFailures.analysis.blocked') }}</h4>
          <p class="tf-note">{{ t('testFailures.analysis.blockedHint') }}</p>
          <details v-for="(item, index) in analysis.result.evidence.blocked_tests" :key="index">
            <summary>{{ blockedStatusLabel(item.status) }}<span v-if="item.tip_volume_ul != null"> · {{ item.tip_volume_ul }} µL</span> · {{ item.evidence_ref }}</summary>
            <p v-if="item.numeric_values_are_placeholders" class="tf-note">{{ t('testFailures.analysis.placeholderValues') }}</p>
            <pre class="tf-code">{{ evidenceFor(item.evidence_ref) }}</pre>
            <pre v-if="item.blocked_by" class="tf-code">{{ failureValue(item.blocked_by) }}</pre>
          </details>
        </div>
        <div v-if="analysis.result.evidence.limitations.length" class="tf-analysis-limitations"><h4>{{ t('testFailures.analysis.limitations') }}</h4><ul class="tf-summary-list"><li v-for="(line, index) in analysis.result.evidence.limitations" :key="index">{{ line }}</li></ul></div>
        </template>
      </template>
    </template>
    <div v-if="compact" class="tf-actions tf-analysis-footer">
      <button v-if="analysis?.status === 'complete' && analysis.result" class="tf-link" type="button" :aria-expanded="expanded" @click="expanded = !expanded">{{ t(expanded ? 'testFailures.analysis.collapse' : 'testFailures.analysis.expand') }}</button>
      <button class="tf-link" type="button" @click="emit('viewEvidence')">{{ t('testFailures.analysis.viewEvidence') }}</button>
    </div>
  </section>
</template>

<script setup lang="ts">
import { computed, onBeforeUnmount, ref, watch } from 'vue'
import { useAppLocale } from '@/i18n'
import { testFailuresEn } from '@/i18n/locales/testFailures'
import { useAuthStore } from '@/scripts/stores/auth'
import { failureValue, formatFailureTime } from '@/scripts/api/testFailures'
import { useFailureAnalysis } from '@/scripts/composables/useFailureAnalysis'

const props = defineProps<{ reportId: string; reportRevision: string; evidenceVersion?: string; compact?: boolean }>()
const emit = defineEmits<{ refreshReport: []; viewEvidence: [] }>()
const { t, locale } = useAppLocale()
const authStore = useAuthStore()
const canEdit = computed(() => Boolean(authStore.user && authStore.user.role !== 'viewer'))
const { analysis, loading, queued, starting, errorKey, revisionChanged, conflict, canGenerate, loadAnalysis, startAnalysis: requestAnalysis } = useFailureAnalysis(() => props.reportId, () => props.reportRevision, () => props.evidenceVersion || '')
const expanded = ref(false)
const manualRefreshing = ref(false)
const checkedAt = ref('')
let refreshRequest = 0
let disposed = false
const assessments = computed(() => analysis.value?.result?.model_analysis.assessments || [])
const hasModelAssessments = computed(() => assessments.value.length > 0)
const findings = computed(() => [...(analysis.value?.result?.evidence.deterministic_findings || [])].sort((left, right) => (assessmentFor(left.finding_id)?.priority ?? 4) - (assessmentFor(right.finding_id)?.priority ?? 4)))

function assessmentFor(id: string) { return assessments.value.find(item => item.finding_id === id) }
function categoryLabel(category: string): string {
  return category in testFailuresEn.analysis.categories ? t(`testFailures.analysis.categories.${category}`) : category
}
function findingStatusLabel(status: string): string {
  return status in testFailuresEn.analysis.findingStatuses ? t(`testFailures.analysis.findingStatuses.${status}`) : status
}
function blockedStatusLabel(status: string): string {
  return status in testFailuresEn.analysis.blockedStatuses ? t(`testFailures.analysis.blockedStatuses.${status}`) : status
}
function displayLines(value: unknown): string[] {
  return Array.isArray(value) ? value.map(failureValue) : [failureValue(value)]
}
function evidenceFor(reference: string): string {
  const catalog = analysis.value?.result?.evidence.evidence_catalog
  return catalog && Object.hasOwn(catalog, reference) ? failureValue(catalog[reference]) : t('testFailures.analysis.evidenceUnavailable')
}
async function startAnalysis(): Promise<void> {
  if (canEdit.value) {
    checkedAt.value = ''
    await requestAnalysis(analysis.value?.status === 'complete')
  }
}
async function refreshAnalysis(): Promise<void> {
  if (manualRefreshing.value || starting.value) return
  const request = ++refreshRequest
  const reportId = props.reportId, revision = props.reportRevision
  checkedAt.value = ''; manualRefreshing.value = true
  try {
    const result = await loadAnalysis('user')
    if (!disposed && request === refreshRequest && props.reportId === reportId && props.reportRevision === revision && result.status === 'success') {
      checkedAt.value = result.checkedAt
    }
  } finally {
    if (!disposed && request === refreshRequest) manualRefreshing.value = false
  }
}
function refreshReport(): void {
  emit('refreshReport')
  // Another view may still subscribe to this revision while details remount.
  // Refresh its shared status as well, including a previous busy response.
  void loadAnalysis()
}
watch([() => props.reportId, () => props.reportRevision, () => props.evidenceVersion], () => {
  expanded.value = false; checkedAt.value = ''; manualRefreshing.value = false; refreshRequest += 1
}, { flush: 'sync' })
onBeforeUnmount(() => { disposed = true; refreshRequest += 1 })
</script>
