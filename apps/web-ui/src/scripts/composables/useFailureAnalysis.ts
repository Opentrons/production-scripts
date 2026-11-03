import { computed, onBeforeUnmount, shallowRef, watch } from 'vue'
import { testFailuresApi } from '../api/testFailures'
import { createFailureAnalysisStore, emptyFailureAnalysisState, failureAnalysisCanGenerate, type AnalysisLoadPriority, type FailureAnalysisSubscription } from './failureAnalysisStore'

const store = createFailureAnalysisStore({
  load: async (reportId, signal) => (await testFailuresApi.analysis(reportId, signal)).data,
  start: async (reportId, revision, signal, force) => (await testFailuresApi.startAnalysis(reportId, revision, signal, force)).data,
})

export function useFailureAnalysis(reportId: () => string, reportRevision: () => string, evidenceVersion: () => string = () => '') {
  const state = shallowRef(emptyFailureAnalysisState())
  let subscription: FailureAnalysisSubscription | null = null
  const stop = watch([reportId, reportRevision, evidenceVersion], ([id, revision, evidence]) => {
    subscription?.unsubscribe()
    subscription = null
    state.value = emptyFailureAnalysisState()
    subscription = store.subscribe(id, revision, value => { state.value = value }, evidence)
  }, { immediate: true, flush: 'sync' })
  onBeforeUnmount(() => { stop(); subscription?.unsubscribe(); subscription = null })

  return {
    analysis: computed(() => state.value.analysis),
    loading: computed(() => state.value.loading),
    queued: computed(() => state.value.queued),
    starting: computed(() => state.value.starting),
    errorKey: computed(() => state.value.errorKey),
    revisionChanged: computed(() => state.value.revisionChanged),
    conflict: computed(() => state.value.conflict),
    canGenerate: computed(() => failureAnalysisCanGenerate(state.value)),
    loadAnalysis: (priority?: AnalysisLoadPriority) => subscription?.loadAnalysis(priority) ?? Promise.resolve({ status: 'cancelled' as const }),
    startAnalysis: (force = false) => subscription?.startAnalysis(force) ?? Promise.resolve({ status: 'cancelled' as const }),
  }
}
