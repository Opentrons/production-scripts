<template>
  <div ref="container">
  <TestFailureAnalysis v-if="activated && selectedReport" :report-id="selectedReport.id" :report-revision="selectedReport.revision" :evidence-version="selectedReport.evidence_version" compact @refresh-report="emit('refresh')" @view-evidence="emit('viewReport', selectedReport.id)">
    <template #source>
      <div class="tf-analysis-source">
        <label v-if="device.reports.length > 1" :for="`tf-analysis-report-${device.id}`">{{ t('testFailures.analysis.sourceReport') }}</label>
        <select v-if="device.reports.length > 1" :id="`tf-analysis-report-${device.id}`" :value="selectedReport.id" @change="selectedId = ($event.target as HTMLSelectElement).value">
          <option v-for="item in device.reports" :key="item.id" :value="item.id">{{ formatFailureTime(item.test_time, locale) }} · {{ reportLabel(item) }} · {{ item.mode }}</option>
        </select>
        <span v-else>{{ t('testFailures.analysis.sourceReport') }} · {{ reportLabel(selectedReport) }}</span>
        <p><time :datetime="selectedReport.test_time || undefined">{{ formatFailureTime(selectedReport.test_time, locale) }}</time><span>{{ selectedReport.mode }} · {{ t(`testFailures.kinds.${selectedReport.kind}`) }}</span></p>
        <p v-if="selectedReport.report_role === 'right_reference'" class="tf-note">{{ t('testFailures.referenceSnapshotNote') }}</p>
      </div>
    </template>
  </TestFailureAnalysis>
  <div v-else-if="selectedReport" class="tf-analysis tf-analysis-placeholder is-compact"><strong>{{ t('testFailures.analysis.title') }}</strong><button type="button" class="tf-link" @click="activate">{{ t('testFailures.analysis.load') }}</button></div>
  </div>
</template>

<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { useAppLocale } from '@/i18n'
import { formatFailureTime, type FailureDevice, type FailureReportSummary } from '@/scripts/api/testFailures'
import { defaultFailureReportId } from '@/scripts/utils/failureReportSelection'
import TestFailureAnalysis from './TestFailureAnalysis.vue'

const props = defineProps<{ device: FailureDevice }>()
const emit = defineEmits<{ refresh: []; viewReport: [reportId: string] }>()
const { t, locale } = useAppLocale()
const selectedId = ref('')
const container = ref<HTMLElement | null>(null)
const activated = ref(false)
let observer: IntersectionObserver | null = null
const selectedReport = computed(() => props.device.reports.find(item => item.id === (selectedId.value || defaultFailureReportId(props.device))))
watch(() => props.device.id, () => { selectedId.value = '' })
watch(() => props.device.reports, reports => {
  if (!reports.some(item => item.id === selectedId.value)) selectedId.value = ''
})
watch(() => JSON.stringify(props.device.matched_report_ids), () => { selectedId.value = '' })

function activate(): void { activated.value = true; observer?.disconnect(); observer = null }
onMounted(() => {
  if (typeof IntersectionObserver === 'undefined' || !container.value) { activate(); return }
  observer = new IntersectionObserver(entries => {
    if (entries.some(entry => entry.isIntersecting)) activate()
  }, { rootMargin: '300px 0px' })
  observer.observe(container.value)
})
onBeforeUnmount(() => { observer?.disconnect(); observer = null })

function reportLabel(item: FailureReportSummary): string {
  return item.report_role === 'right_reference'
    ? t('testFailures.referenceSnapshot', { volume: item.reference_tip_volume_ul ?? '—' })
    : t(item.stage === 'result-summary' ? 'testFailures.finalReport' : 'testFailures.mainReport')
}
</script>
