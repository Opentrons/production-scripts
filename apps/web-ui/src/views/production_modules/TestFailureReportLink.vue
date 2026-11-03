<template>
  <div ref="container" class="tf-report-link" :aria-busy="loading">
    <div class="tf-report-link-heading">
      <span>{{ t('testFailures.reportLink.title') }}</span>
      <button v-if="completeIdentity" type="button" class="tf-link" :disabled="loading || (result?.status === 'running' && !failed)" :aria-label="`${t(canEdit ? 'testFailures.reportLink.refresh' : 'testFailures.reportLink.refreshStatus')} ${report.report_run_id}`" @click="refresh(canEdit)">{{ t(canEdit ? 'testFailures.reportLink.refresh' : 'testFailures.reportLink.refreshStatus') }}</button>
    </div>
    <p v-if="showIdentity" class="tf-report-link-identity">{{ report.sn || '—' }} · <span>{{ report.report_run_id || '—' }}</span></p>
    <p v-if="!completeIdentity" class="tf-muted">{{ t(!report.sn?.trim() ? 'testFailures.reportLink.missingSerial' : 'testFailures.reportLink.missingRun') }}</p>
    <template v-else>
      <p v-if="failed" class="tf-report-link-warning" role="status">{{ t('testFailures.reportLink.loadFailed') }}</p>
      <p v-if="result?.stale || (failed && result?.matches.length)" class="tf-report-link-warning">{{ t('testFailures.reportLink.stale') }}</p>
      <p v-if="statusKey" class="tf-muted" role="status">{{ t(statusKey) }}</p>
      <ul v-if="matches.length" class="tf-report-link-matches">
        <li v-for="(match, index) in matches" :key="match.url + match.source_url">
          <a class="tf-link" :href="match.url" target="_blank" rel="noopener noreferrer">{{ t(matches.length > 1 || result?.status === 'ambiguous' ? 'testFailures.reportLink.candidate' : 'testFailures.reportLink.open', { index: index + 1 }) }} ↗</a>
          <a v-if="match.source_url" class="tf-report-link-source" :href="match.source_url" target="_blank" rel="noopener noreferrer" :title="`${match.sheet_title} · ${t('testFailures.reportLink.row', { row: match.row })}`">{{ t('testFailures.reportLink.source') }}</a>
          <span v-if="result?.status === 'ambiguous'" class="tf-muted">{{ match.sheet_title }} · {{ t('testFailures.reportLink.row', { row: match.row }) }}</span>
        </li>
      </ul>
      <p v-else-if="result?.matches.length" class="tf-report-link-warning">{{ t('testFailures.reportLink.invalidLink') }}</p>
      <small v-if="result?.checked_at" class="tf-report-link-checked">{{ t('testFailures.reportLink.checked') }} {{ formatFailureTime(result.checked_at, locale) }}</small>
    </template>
  </div>
</template>

<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref } from 'vue'
import { useAppLocale } from '@/i18n'
import { formatFailureTime } from '@/scripts/api/testFailures'
import { useAuthStore } from '@/scripts/stores/auth'
import { useFailureReportLink } from '@/scripts/composables/useFailureReportLink'
import { safeFailureReportUrl, type FailureReportLinkIdentity } from '@/scripts/utils/failureReportLinks'

const props = defineProps<{ report: FailureReportLinkIdentity; showIdentity?: boolean }>()
const { t, locale } = useAppLocale()
const authStore = useAuthStore()
const canEdit = computed(() => Boolean(authStore.user && authStore.user.role !== 'viewer'))
const container = ref<HTMLElement | null>(null), visible = ref(false)
const completeIdentity = computed(() => Boolean(props.report.sn?.trim() && props.report.report_run_id?.trim()))
const { result, loading, failed, refresh } = useFailureReportLink(() => props.report, () => visible.value)
const matches = computed(() => (result.value?.matches || []).flatMap(match => {
  const url = safeFailureReportUrl(match.url)
  return url ? [{ ...match, url, source_url: safeFailureReportUrl(match.source_url) }] : []
}))
const statusKey = computed(() => {
  if (failed.value) return ''
  if (loading.value && !result.value) return 'testFailures.reportLink.states.running'
  if (!result.value) return 'testFailures.reportLink.waiting'
  if (result.value.status === 'unavailable' && result.value.error_code === 'invalid_link') return 'testFailures.reportLink.invalidLink'
  if (result.value.status === 'matched') return ''
  return `testFailures.reportLink.states.${result.value.status}`
})
let observer: IntersectionObserver | null = null
onMounted(() => {
  if (typeof IntersectionObserver === 'undefined' || !container.value) { visible.value = true; return }
  observer = new IntersectionObserver(entries => { visible.value = entries.some(entry => entry.isIntersecting) })
  observer.observe(container.value)
})
onBeforeUnmount(() => { observer?.disconnect(); observer = null })
</script>
