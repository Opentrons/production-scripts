import { computed, onBeforeUnmount, shallowRef, watch } from 'vue'
import { testFailuresApi } from '../api/testFailures'
import { failureReportLinkKey, type FailureReportLinkIdentity } from '../utils/failureReportLinks'
import { createFailureReportLinkStore, emptyFailureReportLinkState } from './failureReportLinkStore'

const store = createFailureReportLinkStore({
  load: async (id, signal) => (await testFailuresApi.reportLink(id, signal)).data,
  refresh: async (id, signal) => (await testFailuresApi.refreshReportLink(id, signal)).data,
})

export function useFailureReportLink(identity: () => FailureReportLinkIdentity, visible: () => boolean) {
  const state = shallowRef(emptyFailureReportLinkState())
  let subscription: ReturnType<typeof store.subscribe> | null = null
  const stop = watch([() => failureReportLinkKey(identity()), visible, () => identity().id], ([, active]) => {
    subscription?.unsubscribe()
    subscription = null
    state.value = emptyFailureReportLinkState()
    const report = identity()
    if (!active || !report.id || !report.sn?.trim() || !report.report_run_id?.trim()) return
    subscription = store.subscribe(report, value => { state.value = value })
  }, { immediate: true, flush: 'sync' })
  onBeforeUnmount(() => { stop(); subscription?.unsubscribe(); subscription = null })
  return {
    result: computed(() => state.value.result),
    loading: computed(() => state.value.loading),
    failed: computed(() => state.value.failed),
    refresh: (force = false) => subscription?.refresh(force),
  }
}
