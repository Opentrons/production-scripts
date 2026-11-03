import assert from 'node:assert/strict'
import { test } from 'node:test'
import { createFailureAnalysisStore, failureAnalysisCanGenerate } from '../src/scripts/composables/failureAnalysisStore.ts'

const flush = () => new Promise(resolve => setImmediate(resolve))
function deferred() {
  let resolve, reject
  const promise = new Promise((done, fail) => { resolve = done; reject = fail })
  return { promise, resolve, reject }
}
const response = (reportId = 'r1', revision = 'v1', status = 'idle') => ({
  report_id: reportId, report_revision: revision, status, generated_at: null,
  mode: 'rules_only', error: null, result: null,
})

function harness(t, options = {}) {
  const gets = [], posts = [], timers = new Map(), states = new Map(), subscriptions = []
  let timerId = 0, activeGets = 0, maximumGets = 0
  const store = createFailureAnalysisStore({
    load(reportId, signal) {
      const request = { ...deferred(), reportId, signal }
      gets.push(request)
      activeGets += 1; maximumGets = Math.max(maximumGets, activeGets)
      let finished = false
      const finish = () => { if (!finished) { finished = true; activeGets -= 1 } }
      signal.addEventListener('abort', finish, { once: true })
      request.promise.then(finish, finish)
      return request.promise
    },
    start(reportId, revision, signal, force) {
      const request = { ...deferred(), reportId, revision, signal, force }
      posts.push(request)
      return request.promise
    },
  }, {
    ...options,
    setTimer(callback) { timers.set(++timerId, callback); return timerId },
    clearTimer(id) { timers.delete(id) },
  })
  t.after(() => subscriptions.forEach(item => item.unsubscribe()))
  return {
    gets, posts, states, timers, maximumGets: () => maximumGets,
    subscribe(reportId = 'r1', revision = 'v1', label = reportId, evidenceVersion = '') {
      const subscription = store.subscribe(reportId, revision, state => states.set(label, state), evidenceVersion)
      subscriptions.push(subscription)
      return subscription
    },
    tick() { const callbacks = [...timers.values()]; timers.clear(); callbacks.forEach(callback => callback()) },
  }
}

test('list and detail share one GET, explicit POST, result and running poll', async t => {
  const h = harness(t)
  const list = h.subscribe('r1', 'v1', 'list')
  const detail = h.subscribe('r1', 'v1', 'detail')
  await flush()
  assert.equal(h.gets.length, 1)
  assert.equal(h.posts.length, 0)
  h.gets[0].resolve(response())
  await flush()
  assert.strictEqual(h.states.get('list').analysis, h.states.get('detail').analysis)
  assert.ok(failureAnalysisCanGenerate(h.states.get('list')))
  const first = list.startAnalysis(), second = detail.startAnalysis()
  assert.strictEqual(first, second)
  assert.strictEqual(detail.loadAnalysis(), first)
  await flush()
  assert.equal(h.posts.length, 1)
  h.posts[0].resolve(response('r1', 'v1', 'running'))
  await first
  assert.equal(h.timers.size, 1)
  list.unsubscribe()
  assert.equal(h.timers.size, 1)
  h.tick(); await flush()
  assert.equal(h.gets.length, 2)
  h.gets[1].resolve(response('r1', 'v1', 'complete'))
  await flush()
  assert.equal(h.states.get('detail').analysis.status, 'complete')
  assert.equal(h.timers.size, 0)
  detail.unsubscribe()
  h.subscribe('r1', 'v1', 'reopened')
  await flush()
  assert.equal(h.gets.length, 3, 'last unsubscribe must clear the cached entry')
})

test('GET concurrency is capped and a removed queued report is never requested', async t => {
  const h = harness(t)
  const subscriptions = Array.from({ length: 6 }, (_, index) => h.subscribe(`r${index}`, 'v1'))
  await flush()
  assert.deepEqual(h.gets.map(item => item.reportId), ['r0', 'r1', 'r2'])
  subscriptions[3].unsubscribe()
  h.gets[0].resolve(response('r0'))
  await flush()
  assert.deepEqual(h.gets.map(item => item.reportId), ['r0', 'r1', 'r2', 'r4'])
  assert.equal(h.maximumGets(), 3)
  subscriptions.forEach(item => item.unsubscribe())
  await flush()
  assert.ok(h.gets.slice(1).every(item => item.signal.aborted))
  assert.equal(h.gets.length, 4)
})

test('same-tick refreshes deduplicate and a recreated key ignores its disposed request', async t => {
  const h = harness(t, { maxConcurrentGets: 1 })
  const list = h.subscribe('r1', 'v1', 'list'), detail = h.subscribe('r1', 'v1', 'detail')
  await flush()
  h.gets[0].resolve(response())
  await flush()
  const first = list.loadAnalysis(), second = detail.loadAnalysis()
  assert.strictEqual(first, second)
  await flush()
  assert.equal(h.gets.length, 2)
  list.unsubscribe()
  detail.unsubscribe()
  h.subscribe('r1', 'v1', 'reopened')
  await first
  await flush()
  assert.equal(h.gets.length, 3, 'the new entry must not wait for an ignored abort')
  assert.equal(h.maximumGets(), 1)
  assert.ok(h.gets[1].signal.aborted)
  h.gets[1].resolve(response('r1', 'v1', 'running'))
  await flush()
  assert.equal(h.states.get('reopened').analysis, null)
  assert.equal(h.timers.size, 0)
  h.gets[2].resolve(response('r1', 'v1', 'complete'))
  await flush()
  assert.equal(h.states.get('reopened').analysis.status, 'complete')
  assert.equal(h.timers.size, 0)
})

test('revision changes abort the old subscription, reject mismatched results and release queue slots', async t => {
  const h = harness(t, { maxConcurrentGets: 1 })
  const old = h.subscribe('r1', 'old', 'old')
  await flush()
  old.unsubscribe()
  const current = h.subscribe('r1', 'new', 'current')
  await flush()
  assert.equal(h.gets.length, 2, 'an abort must not wait for the obsolete transport to settle')
  assert.ok(h.gets[0].signal.aborted)
  h.gets[0].resolve(response('r1', 'old', 'complete'))
  await flush()
  assert.equal(h.states.get('current').analysis, null)
  h.gets[1].resolve(response('r1', 'old', 'complete'))
  await flush()
  assert.equal(h.states.get('current').errorKey, 'testFailures.analysis.revisionChanged')
  assert.ok(h.states.get('current').revisionChanged)
  await current.startAnalysis()
  assert.equal(h.posts.length, 0)
  const retry = current.loadAnalysis()
  await flush()
  h.gets[2].resolve(response('r1', 'new', 'complete'))
  await retry
  assert.equal(h.states.get('current').analysis.report_revision, 'new')
  assert.equal(h.states.get('current').revisionChanged, false)
})

test('different reports never accept each other’s results', async t => {
  const h = harness(t)
  h.subscribe('first', 'v1')
  h.subscribe('second', 'v1')
  await flush()
  h.gets[0].resolve(response('first', 'v1', 'complete'))
  h.gets[1].resolve(response('first', 'v1', 'running'))
  await flush()
  assert.equal(h.states.get('first').analysis.status, 'complete')
  assert.equal(h.states.get('second').analysis, null)
  assert.equal(h.states.get('second').errorKey, 'testFailures.analysis.loadFailed')
  assert.equal(h.timers.size, 0)
})

test('409 and transport errors use shared i18n keys without automatic generation', async t => {
  const h = harness(t)
  const subscription = h.subscribe()
  await flush()
  h.gets[0].resolve(response())
  await flush()
  const start = subscription.startAnalysis()
  await flush()
  h.posts[0].reject({ response: { status: 409 } })
  await start
  assert.equal(h.states.get('r1').errorKey, 'testFailures.analysis.busy')
  assert.equal(h.states.get('r1').conflict, true)
  const refresh = subscription.loadAnalysis()
  await flush()
  h.gets[1].reject(new Error('offline'))
  await refresh
  assert.equal(h.states.get('r1').errorKey, 'testFailures.analysis.loadFailed')
  assert.equal(h.states.get('r1').conflict, false)
  assert.equal(h.posts.length, 1)
  assert.equal(h.timers.size, 0)
})

test('only running reports poll; the last unsubscribe stops timers and in-flight polls', async t => {
  const h = harness(t)
  const first = h.subscribe('r1', 'v1', 'first'), second = h.subscribe('r1', 'v1', 'second')
  await flush()
  h.gets[0].resolve(response('r1', 'v1', 'running'))
  await flush()
  first.unsubscribe()
  assert.equal(h.timers.size, 1)
  h.tick(); await flush()
  h.gets[1].reject(new Error('temporary failure'))
  await flush()
  assert.equal(h.timers.size, 1)
  h.tick(); await flush()
  second.unsubscribe()
  assert.ok(h.gets[2].signal.aborted)
  h.gets[2].resolve(response('r1', 'v1', 'running'))
  await flush()
  assert.equal(h.timers.size, 0)
  h.tick(); await flush()
  assert.equal(h.gets.length, 3)
})

test('a shared POST is aborted only after its final subscriber leaves', async t => {
  const h = harness(t)
  const first = h.subscribe(), second = h.subscribe('r1', 'v1', 'second')
  await flush()
  h.gets[0].resolve(response())
  await flush()
  const pending = first.startAnalysis()
  await flush()
  first.unsubscribe()
  assert.equal(h.posts[0].signal.aborted, false)
  second.unsubscribe()
  assert.equal(h.posts[0].signal.aborted, true)
  await pending
  h.posts[0].resolve(response('r1', 'v1', 'running'))
  await flush()
  assert.equal(h.timers.size, 0)
})

test('empty report keys never load or start analysis', async t => {
  const h = harness(t)
  const subscription = h.subscribe('', '')
  await subscription.loadAnalysis()
  await subscription.startAnalysis()
  await flush()
  assert.equal(h.gets.length, 0)
  assert.equal(h.posts.length, 0)
})

test('unchanged refresh succeeds with a check time while errors and cancellation cannot report success', async t => {
  const h = harness(t)
  const subscription = h.subscribe()
  await flush()
  h.gets[0].resolve(response('r1', 'v1', 'complete'))
  await flush()
  const refresh = subscription.loadAnalysis('user')
  await flush()
  assert.equal(h.states.get('r1').loading, true)
  assert.equal(h.states.get('r1').queued, false)
  assert.equal(h.states.get('r1').analysis.status, 'complete')
  h.gets[1].resolve(response('r1', 'v1', 'complete'))
  const success = await refresh
  assert.equal(success.status, 'success')
  assert.ok(Number.isFinite(Date.parse(success.checkedAt)))
  assert.equal(h.posts.length, 0)
  const failed = subscription.loadAnalysis('user')
  await flush()
  h.gets[2].reject(new Error('offline'))
  assert.deepEqual(await failed, { status: 'error' })
  const mismatch = subscription.loadAnalysis('user')
  await flush()
  h.gets[3].resolve(response('r1', 'other', 'complete'))
  assert.deepEqual(await mismatch, { status: 'error' })
  const cancelled = subscription.loadAnalysis('user')
  await flush()
  subscription.unsubscribe()
  assert.deepEqual(await cancelled, { status: 'cancelled' })
})

test('manual refresh promotes queued GETs ahead of background work without duplication or exceeding the limit', async t => {
  const h = harness(t)
  const subscriptions = Array.from({ length: 6 }, (_, index) => h.subscribe(`r${index}`))
  await flush()
  assert.equal(h.states.get('r5').queued, true)
  assert.equal(h.states.get('r0').queued, false)
  const detail = h.subscribe('r5', 'v1', 'detail')
  const manual = detail.loadAnalysis('user')
  assert.strictEqual(manual, subscriptions[5].loadAnalysis('user'))
  h.gets[0].resolve(response('r0'))
  await flush()
  assert.deepEqual(h.gets.map(item => item.reportId), ['r0', 'r1', 'r2', 'r5'])
  assert.equal(h.states.get('detail').queued, false)
  assert.equal(h.maximumGets(), 3)
  h.gets[3].resolve(response('r5'))
  assert.equal((await manual).status, 'success')
  await flush()
  assert.equal(h.gets[4].reportId, 'r3')
  assert.equal(h.gets.filter(item => item.reportId === 'r5').length, 1)
})

test('a cancelled priority request leaves remaining background requests runnable', async t => {
  const h = harness(t, { maxConcurrentGets: 1 })
  h.subscribe('r1')
  h.subscribe('r2')
  const priority = h.subscribe('r3')
  await flush()
  const refresh = priority.loadAnalysis('user')
  priority.unsubscribe()
  assert.deepEqual(await refresh, { status: 'cancelled' })
  h.gets[0].resolve(response('r1'))
  await flush()
  assert.deepEqual(h.gets.map(item => item.reportId), ['r1', 'r2'])
})

test('completed analysis reruns only with explicit force and shared running work still deduplicates', async t => {
  const h = harness(t)
  const list = h.subscribe(), detail = h.subscribe('r1', 'v1', 'detail')
  await flush()
  h.gets[0].resolve(response('r1', 'v1', 'complete'))
  await flush()
  assert.ok(failureAnalysisCanGenerate(h.states.get('r1')))
  assert.deepEqual(await list.startAnalysis(), { status: 'skipped' })
  assert.equal(h.posts.length, 0)
  const first = list.startAnalysis(true), second = detail.startAnalysis(true)
  assert.strictEqual(first, second)
  await flush()
  assert.equal(h.posts.length, 1)
  assert.equal(h.posts[0].force, true)
  h.posts[0].resolve(response('r1', 'v1', 'running'))
  assert.equal((await first).status, 'success')
  assert.deepEqual(await detail.startAnalysis(true), { status: 'skipped' })
  assert.equal(h.posts.length, 1)
  assert.equal(h.timers.size, 1)
})

test('generating idle analysis sends force false by default', async t => {
  const h = harness(t)
  const subscription = h.subscribe()
  await flush()
  h.gets[0].resolve(response())
  await flush()
  const start = subscription.startAnalysis()
  await flush()
  assert.equal(h.posts[0].force, false)
  h.posts[0].resolve(response('r1', 'v1', 'running'))
  await start
})

test('attachment versions share one fresh GET across list/detail without accepting an older late response', async t => {
  const h = harness(t)
  const old = h.subscribe('r1', 'v1', 'old', 'attachments-1')
  await flush()
  h.subscribe('r1', 'v1', 'list', 'attachments-2')
  h.subscribe('r1', 'v1', 'detail', 'attachments-2')
  await flush()
  assert.equal(h.gets.length, 2)
  h.gets[1].resolve(response('r1', 'v1', 'stale'))
  await flush()
  assert.strictEqual(h.states.get('list').analysis, h.states.get('detail').analysis)
  h.gets[0].resolve(response('r1', 'v1', 'complete'))
  await flush()
  assert.equal(h.states.get('list').analysis.status, 'stale')
  assert.equal(h.states.get('detail').analysis.status, 'stale')
  old.unsubscribe()
  h.subscribe('r1', 'v1', 'same-evidence-reopened', 'attachments-2')
  await flush()
  assert.equal(h.gets.length, 2, 'unchanged evidence uses the already shared status')
})
