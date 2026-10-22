<template>
  <dialog ref="dialog" class="defect-dialog" aria-labelledby="defect-dialog-title" @cancel="cancel" @click="outsideClick">
    <div class="defect-dialog-heading">
      <h2 id="defect-dialog-title">{{ mode === 'feedback' ? text.feedbackTitle : text.sourceTitle }}</h2>
      <button type="button" class="defect-reset-button" :disabled="saving" @click="emit('close')">{{ text.close }}</button>
    </div>
    <p v-if="loading" class="defect-dialog-status" role="status">{{ text.loading }}</p>
    <p v-if="sourceError" class="defect-inline-error" role="alert">
      {{ sourceError }} <a :href="fallbackUrl" target="_blank" rel="noopener noreferrer">{{ text.htmlFallback }}</a>
    </p>
    <template v-if="record">
      <p class="defect-dialog-description"><strong>{{ record.product || '—' }}</strong> · {{ record.defect_description || '—' }}</p>
      <dl v-if="mode === 'source'" class="defect-source-fields">
        <template v-for="field in sourceFields" :key="field.key">
          <dt>{{ field.label }}</dt><dd>{{ field.value }}</dd>
        </template>
      </dl>
      <form v-if="mode === 'feedback'" class="defect-feedback-form" @submit.prevent="save">
        <p class="defect-dialog-note">{{ text.feedbackNote }}</p>
        <div class="defect-repair-session">
          <div><strong>{{ text.currentRepair }}</strong><button type="button" class="defect-text-button" :disabled="saving" @click="newRepair">{{ text.newRepair }}</button></div>
          <label><span>{{ text.actualSerial }}</span><input v-model="actualSerialNumber" type="text" maxlength="128" :placeholder="text.serialPlaceholder" :disabled="saving || Boolean(repairSessionId)" autocomplete="off" /></label>
          <p v-if="repairSessionId" class="defect-dialog-note">{{ text.sessionLocked(actualSerialNumber) }}</p>
          <p v-else class="defect-dialog-note">{{ text.sessionNew }}</p>
        </div>
        <div v-if="initialAction && !form.action && !repairSessionId" class="defect-feedback-reference"><span>{{ text.referenceAction }}</span><p>{{ initialAction }}</p><button type="button" class="defect-text-button" :disabled="saving" @click="useAction(initialAction)">{{ text.useReference }}</button></div>
        <label><span>{{ text.action }}</span><textarea v-model="form.action" required maxlength="2000" rows="3" :placeholder="text.actionPlaceholder" :disabled="saving" /></label>
        <div class="defect-feedback-selects">
          <label><span>{{ text.outcome }}</span><select v-model="form.outcome" :disabled="saving"><option value="pending">{{ text.pending }}</option><option value="passed">{{ text.passed }}</option><option value="failed">{{ text.failed }}</option></select></label>
          <label><span>{{ text.recurrence }}</span><select v-model="form.recurrence" :disabled="saving"><option value="unknown">{{ text.unknown }}</option><option value="no">{{ text.noRecurrence }}</option><option value="yes">{{ text.recurred }}</option></select></label>
        </div>
        <label><span>{{ text.note }}</span><textarea v-model="form.note" maxlength="3000" rows="2" :disabled="saving" /></label>
        <p v-if="saveError" class="defect-inline-error" role="alert">{{ saveError }}</p>
        <p v-if="saved" class="defect-dialog-note" role="status">{{ text.saved }}</p>
        <button type="submit" class="defect-search-button" :disabled="saving || !form.action.trim()">{{ saving ? text.saving : text.save }}</button>
      </form>
      <section v-if="resultGuidance" class="defect-next-step" aria-live="polite">
        <h3>{{ text.resultNote }}</h3><strong>{{ resultGuidance.action }}</strong><p>{{ resultGuidance.reason }}</p>
      </section>
      <section class="defect-feedback-history" aria-labelledby="defect-feedback-history-title">
        <h3 id="defect-feedback-history-title">{{ mode === 'feedback' ? text.sessionHistory : text.history }}</h3>
        <p v-if="historyError" class="defect-inline-error" role="alert">{{ historyError }}</p>
        <p v-else-if="!history.length && !loading" class="defect-dialog-note">{{ mode === 'feedback' ? text.noSessionHistory : text.noHistory }}</p>
        <article v-for="entry in history" :key="entry.id">
          <div><strong>{{ outcomeLabel(entry.outcome) }}</strong><span>{{ formatDate(entry.created_at) }}</span></div>
          <p>{{ entry.action }}</p><p v-if="entry.note" class="defect-dialog-note">{{ entry.note }}</p>
          <small>{{ recurrenceLabel(entry.recurrence) }}<template v-if="entry.actual_serial_number"> · {{ text.device }}: {{ entry.actual_serial_number }}</template><template v-if="entry.query"> · {{ text.query }}: {{ entry.query }}</template></small>
        </article>
      </section>
    </template>
  </dialog>
</template>

<script setup lang="ts">
import { dialogEnglish, dialogChinese, sourceFieldLabels } from '@/i18n/locales/defectSearch'
import { computed, nextTick, onBeforeUnmount, reactive, ref, watch } from 'vue'
import { API_BASE_URL } from '@/scripts/api/http'
import { defectSearchApi, type DefectFeedback, type DefectNextStep, type DefectRepairSession, type DefectSearchCase } from '@/scripts/api'

const props = defineProps<{ recordId: number | null; mode: 'source' | 'feedback'; query: string; initialAction?: string; repairSession?: DefectRepairSession; english: boolean }>()
const emit = defineEmits<{ close: []; source: [id: number]; session: [caseId: number, session: DefectRepairSession | null] }>()
const dialog = ref<HTMLDialogElement | null>(null)
const record = ref<DefectSearchCase | null>(null)
const history = ref<DefectFeedback[]>([])
const resultGuidance = ref<DefectNextStep | null>(null)
const loading = ref(false)
const saving = ref(false)
const sourceError = ref('')
const historyError = ref('')
const saveError = ref('')
const saved = ref(false)
const repairSessionId = ref('')
const actualSerialNumber = ref('')
const form = reactive({ action: '', outcome: 'pending' as DefectFeedback['outcome'], recurrence: 'unknown' as DefectFeedback['recurrence'], note: '' })
let controller: AbortController | null = null
let generation = 0
const fallbackUrl = computed(() => `${API_BASE_URL}/defect-search/source/${props.recordId}`)
const text = computed(() => props.english ? dialogEnglish : dialogChinese)
const sourceFields = computed(() => {
  if (!record.value) return []

  return sourceFieldLabels.filter(([key]) => Boolean(record.value?.[key]) && (key !== 'original_product' || record.value?.original_product !== record.value?.product)).map(([key, zh, en]) => ({ key, label: props.english ? en : zh, value: record.value![key] }))
})

function outcomeLabel(value: DefectFeedback['outcome']): string { return text.value[value] }
function recurrenceLabel(value: DefectFeedback['recurrence']): string { return value === 'yes' ? text.value.recurred : value === 'no' ? text.value.noRecurrence : text.value.unknown }
function formatDate(value: string): string { const date = new Date(value); return Number.isNaN(date.getTime()) ? value : date.toLocaleString(props.english ? 'en-GB' : 'zh-CN', { timeZone: 'Asia/Shanghai', hour12: false }) }
function cancel(event: Event): void { event.preventDefault(); if (!saving.value) emit('close') }
function outsideClick(event: MouseEvent): void {
  if (event.target !== dialog.value || saving.value || !dialog.value) return
  const rect = dialog.value.getBoundingClientRect()
  if (event.clientX < rect.left || event.clientX > rect.right || event.clientY < rect.top || event.clientY > rect.bottom) emit('close')
}
function openSource(event: MouseEvent, id: string): void { const value = Number(id); if (Number.isInteger(value) && value > 0) { event.preventDefault(); if (!saving.value) emit('source', value) } }
function useAction(action: string): void { form.action = action; form.outcome = 'pending'; form.recurrence = 'unknown'; form.note = ''; saved.value = false }
function newRepair(): void {
  if (!props.recordId || saving.value) return
  repairSessionId.value = ''; actualSerialNumber.value = ''; history.value = []; resultGuidance.value = null
  form.action = ''; form.note = ''; form.outcome = 'pending'; form.recurrence = 'unknown'
  saved.value = false; saveError.value = ''; historyError.value = ''
  emit('session', props.recordId, null)
}

async function load(): Promise<void> {
  controller?.abort()
  const version = ++generation
  const id = props.recordId
  if (!id) { dialog.value?.close(); return }
  await nextTick()
  if (version !== generation || props.recordId !== id) return
  if (!dialog.value?.open) dialog.value?.showModal()
  controller = new AbortController()
  const signal = controller.signal
  record.value = null; history.value = []
  const storedGuidance = props.mode === 'feedback' ? props.repairSession?.next_step : undefined
  resultGuidance.value = storedGuidance && ['resolved', 'pending', 'engineering_review'].includes(storedGuidance.kind) ? storedGuidance : null
  sourceError.value = ''; historyError.value = ''; saveError.value = ''
  repairSessionId.value = props.mode === 'feedback' ? props.repairSession?.repair_session_id ?? '' : ''
  actualSerialNumber.value = props.mode === 'feedback' ? props.repairSession?.actual_serial_number ?? '' : ''
  saved.value = false; form.action = ''; form.note = ''; form.outcome = 'pending'; form.recurrence = 'unknown'
  loading.value = true
  const shouldLoadHistory = props.mode === 'source' || Boolean(repairSessionId.value)
  const responses = await Promise.allSettled([defectSearchApi.getSource(id, signal), shouldLoadHistory ? defectSearchApi.getFeedback(id, signal, repairSessionId.value || undefined) : Promise.resolve(null)])
  if (signal.aborted || generation !== version) return
  const [sourceResult, historyResult] = responses
  if (sourceResult.status === 'fulfilled') record.value = sourceResult.value.data.case
  else sourceError.value = text.value.sourceFailed
  if (historyResult.status === 'fulfilled') history.value = historyResult.value?.data.feedback ?? []
  else historyError.value = text.value.historyFailed
  loading.value = false
}

async function save(): Promise<void> {
  if (!props.recordId || saving.value || !form.action.trim()) return
  saving.value = true; saveError.value = ''
  saved.value = false
  try {
    const response = await defectSearchApi.saveFeedback({ case_id: props.recordId, query: props.query, action: form.action.trim(), outcome: form.outcome, recurrence: form.recurrence, note: form.note.trim(), repair_session_id: repairSessionId.value || undefined, actual_serial_number: actualSerialNumber.value.trim() })
    history.value = [response.data.feedback, ...history.value]
    resultGuidance.value = response.data.next_step
    repairSessionId.value = response.data.feedback.repair_session_id || repairSessionId.value
    actualSerialNumber.value = response.data.feedback.actual_serial_number ?? actualSerialNumber.value.trim()
    if (repairSessionId.value) emit('session', props.recordId, { repair_session_id: repairSessionId.value, actual_serial_number: actualSerialNumber.value, next_step: response.data.next_step })
    form.action = ''; form.note = ''; form.outcome = 'pending'; form.recurrence = 'unknown'; saved.value = true
    historyError.value = ''
  } catch { saveError.value = text.value.saveFailed }
  finally { saving.value = false }
}

watch(() => [props.recordId, props.mode] as const, () => { void load() }, { immediate: true, flush: 'post' })
onBeforeUnmount(() => { controller?.abort(); dialog.value?.close() })
</script>
