import assert from 'node:assert/strict'
import fs from 'node:fs'
import { test } from 'node:test'
import ts from 'typescript'
import { computed, effectScope, nextTick, reactive, ref, watch } from 'vue'
import { defaultFailureReportId } from '../src/scripts/utils/failureReportSelection.ts'

function loadScript(file, exposed) {
  const source = fs.readFileSync(new URL(`../src/views/production_modules/${file}`, import.meta.url), 'utf8')
    .match(/<script setup lang="ts">([\s\S]*?)<\/script>/)[1].replace(/^import .*\n/gm, '')
  const script = ts.transpileModule(source, { compilerOptions: { target: ts.ScriptTarget.ES2022 } }).outputText
  return new Function('dependencies', `
    const { computed, ref, watch, onMounted, onBeforeUnmount, defineProps, defineEmits,
      useAppLocale, testFailuresApi, defaultFailureReportId, failureKnowledgeQueries,
      failureKnowledgeProduct, testFailuresEn, IntersectionObserver } = dependencies;
    ${script}
    return { ${exposed} };
  `)
}
const instantiateDetail = loadScript('TestFailureDetail.vue', 'report, selectedId, selectionNotice, history, error, selectReport')
const instantiateInline = loadScript('TestFailureDeviceAnalysis.vue', 'selectedReport, selectedId, activated, container, activate')
const flush = async () => { await nextTick(); await new Promise(resolve => setImmediate(resolve)); await nextTick() }
function device() {
  return { id: 'folder-a', version: 'version-1', matched_report_ids: ['probe'], reports: [
    { id: 'main', revision: 'main-1', evidence_version: 'main-evidence-1', report_folder: 'folder-a', report_role: 'main' },
    { id: 'probe', revision: 'probe-1', evidence_version: 'probe-evidence-1', report_folder: 'folder-a', report_role: 'right_reference' },
  ] }
}
function harness(t, initial = device(), reportId = '') {
  const props = reactive({ device: initial, reportId })
  const calls = [], historyCalls = [], dispose = []
  const scope = effectScope()
  const detail = scope.run(() => instantiateDetail({
    computed, ref, watch, defineProps: () => props, defineEmits: () => () => {},
    onBeforeUnmount: callback => dispose.push(callback), useAppLocale: () => ({ t: key => key, locale: ref('en-US') }),
    defaultFailureReportId, failureKnowledgeQueries: () => [], failureKnowledgeProduct: () => null, testFailuresEn: {},
    testFailuresApi: {
      report: async (id, signal) => {
        calls.push({ id, signal })
        return { data: { ...props.device.reports.find(item => item.id === id), summary: [], product: 'P50M', attachments: [{ kind: 'log' }] } }
      },
      confirmations: async (id, signal) => {
        historyCalls.push({ id, signal })
        return { data: { items: [{ id: `confirmation-${historyCalls.length}`, text: 'repair recorded' }] } }
      },
    },
  }))
  t.after(() => { scope.stop(); dispose.forEach(callback => callback()) })
  return { props, detail, calls, historyCalls }
}

test('detail defaults to the filtered evidence package and refresh retains report/attachments', async t => {
  const { props, detail, calls, historyCalls } = harness(t)
  await flush()
  assert.equal(detail.selectedId.value, 'probe')
  const initialReport = detail.report.value
  const initialHistory = detail.history.value
  props.device = JSON.parse(JSON.stringify(props.device))
  await flush()
  assert.equal(calls.length, 1)
  assert.equal(historyCalls.length, 1)
  assert.equal(detail.report.value, initialReport)
  assert.equal(detail.history.value, initialHistory)
  assert.equal(calls[0].signal.aborted, false)
})

test('confirmation refreshes history without clearing active evidence', async t => {
  const { props, detail, calls, historyCalls } = harness(t)
  await flush()
  const initialReport = detail.report.value
  props.device.version = 'new-confirmation'
  await flush()
  assert.equal(calls.length, 1)
  assert.equal(detail.report.value, initialReport)
  assert.equal(calls[0].signal.aborted, false)
  assert.equal(historyCalls.length, 2)
  assert.equal(detail.history.value[0].id, 'confirmation-2')
})

test('only a change to the selected evidence revision reloads its details', async t => {
  const { props, detail, calls } = harness(t)
  await flush()
  props.device.reports[0].revision = 'main-2'
  props.device.version = 'version-2'
  await flush()
  assert.equal(calls.length, 1)
  props.device.reports[1].revision = 'probe-2'
  await flush()
  assert.equal(calls.length, 2)
  assert.equal(detail.report.value.revision, 'probe-2')
})

test('attachment changes reload only the selected evidence without changing confirmation revision', async t => {
  const { props, detail, calls, historyCalls } = harness(t)
  await flush()
  const initialReport = detail.report.value
  props.device.reports[0].evidence_version = 'main-log-arrived'
  await flush()
  assert.equal(calls.length, 1)
  assert.equal(detail.report.value, initialReport)
  props.device.reports[1].evidence_version = 'probe-encoder-arrived'
  await flush()
  assert.equal(calls.length, 2)
  assert.equal(detail.report.value.revision, 'probe-1')
  assert.equal(detail.report.value.evidence_version, 'probe-encoder-arrived')
  assert.equal(historyCalls.length, 1, 'attachment updates do not invalidate confirmation history')
  const updatedReport = detail.report.value
  props.device = JSON.parse(JSON.stringify(props.device))
  await flush()
  assert.equal(calls.length, 2)
  assert.equal(detail.report.value, updatedReport)
})

test('removed selected evidence resets to an available package with a visible notice', async t => {
  const { props, detail, calls } = harness(t)
  await flush()
  props.device.reports = props.device.reports.filter(item => item.id === 'main')
  await flush()
  assert.equal(detail.selectedId.value, 'main')
  assert.equal(detail.report.value.id, 'main')
  assert.equal(detail.selectionNotice.value, true)
  assert.deepEqual(calls.map(call => call.id), ['probe', 'main'])
})

test('an explicit missing evidence link never silently opens different evidence', async t => {
  const { detail, calls } = harness(t, device(), 'removed-reference')
  await flush()
  assert.equal(detail.report.value, null)
  assert.equal(calls.length, 0)
  assert.equal(detail.error.value, 'testFailures.reportUnavailable')
})

test('closing the drawer aborts owned requests and clears old report history', async t => {
  const { props, detail, calls, historyCalls } = harness(t)
  await flush()
  props.device = null
  await flush()
  assert.equal(detail.report.value, null)
  assert.deepEqual(detail.history.value, [])
  assert.equal(calls[0].signal.aborted, true)
  assert.equal(historyCalls[0].signal.aborted, true)
})

test('inline analysis stays dormant until near viewport and follows matching filters', async t => {
  const props = reactive({ device: device() })
  const mounted = [], dispose = [], observer = { callback: null, observed: [], disconnected: 0 }
  class Observer {
    constructor(callback, options) { observer.callback = callback; assert.equal(options.rootMargin, '300px 0px') }
    observe(target) { observer.observed.push(target) }
    disconnect() { observer.disconnected += 1 }
  }
  const scope = effectScope()
  const inline = scope.run(() => instantiateInline({
    computed, ref, watch, onMounted: callback => mounted.push(callback), onBeforeUnmount: callback => dispose.push(callback),
    defineProps: () => props, defineEmits: () => () => {}, IntersectionObserver: Observer,
    useAppLocale: () => ({ t: key => key, locale: ref('en-US') }), defaultFailureReportId,
  }))
  t.after(() => { scope.stop(); dispose.forEach(callback => callback()) })
  inline.container.value = { row: 'target' }
  mounted.forEach(callback => callback())
  assert.equal(inline.activated.value, false)
  assert.equal(inline.selectedReport.value.id, 'probe')
  observer.callback([{ isIntersecting: false }])
  assert.equal(inline.activated.value, false)
  observer.callback([{ isIntersecting: true }])
  assert.equal(inline.activated.value, true)
  assert.equal(observer.disconnected, 1)
  inline.selectedId.value = 'probe'
  props.device.matched_report_ids = ['main']
  await flush()
  assert.equal(inline.selectedReport.value.id, 'main')
})

test('matching an absent report never selects outside the current folder', () => {
  const input = device()
  input.matched_report_ids = ['another-folder-main']
  assert.equal(defaultFailureReportId(input), 'main')
  input.reports = []
  assert.equal(defaultFailureReportId(input), '')
})
