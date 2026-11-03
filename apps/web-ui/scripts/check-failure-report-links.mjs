import assert from 'node:assert/strict'
import fs from 'node:fs'
import { test } from 'node:test'
import ts from 'typescript'
import { computed, effectScope, reactive, shallowRef, watch } from 'vue'
import { failureReportLinkKey, failureReportLinkTargets, safeFailureReportUrl } from '../src/scripts/utils/failureReportLinks.ts'

const storeSource = fs.readFileSync(new URL('../src/scripts/composables/failureReportLinkStore.ts', import.meta.url), 'utf8')
const script = ts.transpileModule(storeSource, { compilerOptions: { module: ts.ModuleKind.ES2022, target: ts.ScriptTarget.ES2022 } }).outputText
  .replace('../utils/failureReportLinks', new URL('../src/scripts/utils/failureReportLinks.ts', import.meta.url).href)
const { createFailureReportLinkStore, emptyFailureReportLinkState } = await import(`data:text/javascript,${encodeURIComponent(script)}`)
const composableSource = fs.readFileSync(new URL('../src/scripts/composables/useFailureReportLink.ts', import.meta.url), 'utf8')
  .replace(/^import .*\n/gm, '').replace(/const store = createFailureReportLinkStore\([\s\S]*?\n}\)\n/, '')
const composableScript = ts.transpileModule(composableSource, { compilerOptions: { target: ts.ScriptTarget.ES2022 } }).outputText.replace(/export /g, '')
const instantiateComposable = new Function('dependencies', `const {computed, onBeforeUnmount, shallowRef, watch, store, emptyFailureReportLinkState, failureReportLinkKey} = dependencies; ${composableScript}; return useFailureReportLink;`)
const flush = () => new Promise(resolve => setImmediate(resolve))
const identity = (id = 'main', folder = 'folder-1', run = 'run-1') => ({ id, report_folder: folder, sn: 'P50M123', report_run_id: run })
const result = (status = 'matched', overrides = {}) => ({ status, sn: 'P50M123', report_run_id: 'run-1', checked_at: '2026-11-02T01:00:00Z', stale: false, matches: [], error_code: null, ...overrides })
function deferred() {
  let resolve, reject
  const promise = new Promise((done, fail) => { resolve = done; reject = fail })
  return { promise, resolve, reject }
}
function harness(t, options = {}) {
  const gets = [], posts = [], states = new Map(), timers = new Map(), subscriptions = []
  let timerId = 0
  const request = (list, id, signal) => { const item = { ...deferred(), id, signal }; list.push(item); return item.promise }
  const store = createFailureReportLinkStore({ load: (id, signal) => request(gets, id, signal), refresh: (id, signal) => request(posts, id, signal) }, {
    ...options, setTimer(callback) { timers.set(++timerId, callback); return timerId }, clearTimer(id) { timers.delete(id) },
  })
  t.after(() => subscriptions.forEach(subscription => subscription.unsubscribe()))
  return {
    store, gets, posts, states, timers,
    subscribe(report = identity(), label = report.id) {
      const subscription = store.subscribe(report, state => states.set(label, state))
      subscriptions.push(subscription)
      return subscription
    },
    tick() { const callbacks = [...timers.values()]; timers.clear(); callbacks.forEach(callback => callback()) },
  }
}

test('same-folder main and reference evidence share an identity; separate runs/folders remain separate', () => {
  const reference = { ...identity('reference'), report_role: 'right_reference' }, main = { ...identity(), report_role: 'main' }
  const otherRun = identity('other-run', 'folder-1', 'run-2'), otherFolder = identity('other-folder', 'folder-2')
  const missingA = identity('missing-a', 'folder-1', null), missingB = identity('missing-b', 'folder-1', null)
  assert.deepEqual(failureReportLinkTargets([reference, otherRun, main, otherFolder, missingA, missingB]).map(report => report.id), ['main', 'other-run', 'other-folder', 'missing-a', 'missing-b'])
})

test('report product participates in matching identity and same-product references deduplicate', () => {
  const main = { ...identity(), product: 'p50_single_flex', report_role: 'main' }
  const reference = { ...identity('reference'), product: ' p50_single_flex ', report_role: 'right_reference' }
  const multi = { ...identity('multi'), product: 'p50_multi_flex', report_role: 'main' }
  assert.equal(failureReportLinkKey(main), failureReportLinkKey(reference))
  assert.notEqual(failureReportLinkKey(main), failureReportLinkKey(multi))
  assert.deepEqual(failureReportLinkTargets([reference, multi, main]).map(report => report.id), ['main', 'multi'])
})

test('external links only allow HTTPS Google report destinations without embedded credentials', () => {
  for (const value of ['javascript:alert(1)', 'http://docs.google.com/test', 'https://docs.google.com.attacker.test/', 'https://user@docs.google.com/', 'https://docs.google.com:8443/', '/relative']) assert.equal(safeFailureReportUrl(value), null)
  assert.equal(safeFailureReportUrl('https://docs.google.com/spreadsheets/d/example/edit#gid=1'), 'https://docs.google.com/spreadsheets/d/example/edit#gid=1')
  assert.equal(safeFailureReportUrl('https://drive.google.com/file/d/example/view'), 'https://drive.google.com/file/d/example/view')
})

test('list and detail share GET and running poll; only editor refresh requests POST', async t => {
  const h = harness(t), list = h.subscribe(identity(), 'list'), detail = h.subscribe(identity('reference'), 'detail')
  assert.equal(h.gets.length, 1)
  h.gets[0].resolve(result('running')); await flush()
  assert.equal(h.timers.size, 1)
  assert.strictEqual(h.states.get('list').result, h.states.get('detail').result)
  list.unsubscribe(); h.tick()
  assert.equal(h.gets.length, 2)
  h.gets[1].resolve(result()); await flush()
  assert.equal(h.timers.size, 0)
  detail.refresh(false)
  assert.equal(h.gets.length, 3)
  assert.equal(h.posts.length, 0)
  h.gets[2].resolve(result()); await flush()
  detail.refresh(true)
  assert.equal(h.posts.length, 1)
  h.posts[0].resolve(result('running')); await flush()
  assert.equal(h.timers.size, 1)
  detail.unsubscribe()
  assert.equal(h.timers.size, 0)
})

test('offscreen/unmounted last subscriber aborts requests and ignores late results', async t => {
  const h = harness(t), first = h.subscribe(identity(), 'first')
  const original = h.gets[0]
  first.unsubscribe()
  assert.equal(original.signal.aborted, true)
  h.subscribe(identity(), 'reopened')
  h.gets[1].resolve(result('not_found')); await flush()
  original.resolve(result()); await flush()
  assert.equal(h.states.get('reopened').result.status, 'not_found')
  assert.equal(h.timers.size, 0)
})

test('requests are bounded and queued invisible reports are discarded', async t => {
  const h = harness(t, { maxConcurrent: 2 })
  const items = Array.from({ length: 4 }, (_, i) => h.subscribe(identity(`r${i}`, `f${i}`)))
  assert.deepEqual(h.gets.map(item => item.id), ['r0', 'r1'])
  items[2].unsubscribe()
  items[0].unsubscribe(); await flush()
  assert.deepEqual(h.gets.map(item => item.id), ['r0', 'r1', 'r3'])
})

test('transport errors retain prior links with failure state and stop polling', async t => {
  const h = harness(t), subscription = h.subscribe()
  h.gets[0].resolve(result('matched', { matches: [{ url: 'https://docs.google.com/report' }] })); await flush()
  subscription.refresh()
  h.gets[1].reject(new Error('Unavailable')); await flush()
  assert.equal(h.states.get('main').failed, true)
  assert.equal(h.states.get('main').result.matches.length, 1)
  assert.equal(h.timers.size, 0)
  subscription.refresh()
  h.gets[2].resolve(result('running')); await flush()
  h.tick()
  h.gets[3].reject(new Error('Unavailable')); await flush()
  assert.equal(h.timers.size, 0)
})

test('a response for another run is rejected and different folders never share requests', async t => {
  const h = harness(t)
  h.subscribe(identity(), 'first')
  h.subscribe(identity('second', 'folder-2'), 'second')
  assert.equal(h.gets.length, 2)
  h.gets[0].resolve(result('matched', { report_run_id: 'wrong-run' }))
  h.gets[1].resolve(result()); await flush()
  assert.equal(h.states.get('first').result, null)
  assert.equal(h.states.get('first').failed, true)
  assert.equal(h.states.get('second').result.status, 'matched')
})

test('visibility and identity changes release subscriptions and never request a missing run', async t => {
  const h = harness(t), props = reactive({ report: identity(), visible: false }), dispose = [], scope = effectScope()
  const useLink = instantiateComposable({ computed, shallowRef, watch, store: h.store, emptyFailureReportLinkState, failureReportLinkKey, onBeforeUnmount: callback => dispose.push(callback) })
  const link = scope.run(() => useLink(() => props.report, () => props.visible))
  t.after(() => { scope.stop(); dispose.forEach(callback => callback()) })
  assert.equal(h.gets.length, 0)
  props.visible = true
  assert.equal(h.gets.length, 1)
  props.visible = false
  assert.equal(h.gets[0].signal.aborted, true)
  assert.equal(link.result.value, null)
  props.report = identity('missing', 'folder-1', null)
  props.visible = true
  assert.equal(h.gets.length, 1)
  props.report = identity('new', 'folder-1', 'run-2')
  assert.equal(h.gets.length, 2)
  h.gets[1].resolve(result('matched', { report_run_id: 'run-2' })); await flush()
  assert.equal(link.result.value.report_run_id, 'run-2')
  props.report = identity('third', 'folder-1', 'run-3')
  assert.equal(link.result.value, null)
  assert.equal(h.gets.length, 3)
  dispose.forEach(callback => callback())
  assert.equal(h.gets[2].signal.aborted, true)
})

test('a corrected product replaces the match and a late response cannot restore the previous route', async t => {
  const h = harness(t), props = reactive({ report: { ...identity(), product: 'p50_multi_flex' } }), dispose = [], scope = effectScope()
  const useLink = instantiateComposable({ computed, shallowRef, watch, store: h.store, emptyFailureReportLinkState, failureReportLinkKey, onBeforeUnmount: callback => dispose.push(callback) })
  const link = scope.run(() => useLink(() => props.report, () => true))
  t.after(() => { scope.stop(); dispose.forEach(callback => callback()) })
  const oldRequest = h.gets[0]
  props.report.product = 'p50_single_flex'
  assert.equal(oldRequest.signal.aborted, true)
  assert.equal(h.gets.length, 2)
  assert.equal(link.result.value, null)
  h.gets[1].resolve(result('not_found')); await flush()
  oldRequest.resolve(result('matched')); await flush()
  assert.equal(link.result.value.status, 'not_found')
})

test('changed report ID re-subscribes and future shared requests use the new ID', async t => {
  const h = harness(t), props = reactive({ report: identity() }), dispose = [], scope = effectScope()
  const useLink = instantiateComposable({ computed, shallowRef, watch, store: h.store, emptyFailureReportLinkState, failureReportLinkKey, onBeforeUnmount: callback => dispose.push(callback) })
  const link = scope.run(() => useLink(() => props.report, () => true))
  t.after(() => { scope.stop(); dispose.forEach(callback => callback()) })
  const other = h.subscribe(identity(), 'other')
  h.gets[0].resolve(result('running')); await flush()
  props.report.id = 'replacement'
  assert.equal(h.gets.length, 1, 'another active view preserves shared state without duplicate work')
  assert.equal(link.result.value.status, 'running')
  h.tick()
  assert.equal(h.gets[1].id, 'replacement', 'polling follows the updated report ID')
  h.gets[1].resolve(result()); await flush()
  other.refresh(true)
  assert.equal(h.posts[0].id, 'replacement', 'all subscribers refresh through the current report ID')
  h.posts[0].resolve(result()); await flush()
  other.unsubscribe()
  props.report.id = 'replacement-again'
  assert.equal(h.gets[2].id, 'replacement-again', 'the sole subscriber also reopens through its current ID')
})
