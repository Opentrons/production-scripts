import type { FailureAnalysis } from '../api/testFailures'

export interface FailureAnalysisState {
  analysis: FailureAnalysis | null
  loading: boolean
  queued: boolean
  starting: boolean
  errorKey: string
  revisionChanged: boolean
  conflict: boolean
}

export const emptyFailureAnalysisState = (): FailureAnalysisState => ({
  analysis: null, loading: false, queued: false, starting: false, errorKey: '', revisionChanged: false, conflict: false,
})

export function failureAnalysisCanGenerate(state: FailureAnalysisState): boolean {
  return !state.revisionChanged && Boolean(state.analysis && ['idle', 'failed', 'stale', 'complete'].includes(state.analysis.status))
}

export type AnalysisRequestResult = { status: 'success'; checkedAt: string } | { status: 'error' | 'cancelled' | 'skipped' }
export type AnalysisLoadPriority = 'background' | 'user'

interface AnalysisClient {
  load: (reportId: string, signal: AbortSignal) => Promise<FailureAnalysis>
  start: (reportId: string, revision: string, signal: AbortSignal, force?: boolean) => Promise<FailureAnalysis>
}
interface StoreOptions {
  maxConcurrentGets?: number
  pollIntervalMs?: number
  setTimer?: (callback: () => void, delay: number) => unknown
  clearTimer?: (timer: unknown) => void
}
interface Operation {
  kind: 'get' | 'post'
  controller: AbortController
  promise: Promise<AnalysisRequestResult>
  resolve: (result: AnalysisRequestResult) => void
  started: boolean
  priority: AnalysisLoadPriority
  force: boolean
}
interface Entry {
  key: string
  reportId: string
  revision: string
  state: FailureAnalysisState
  listeners: Set<(state: FailureAnalysisState) => void>
  operation: Operation | null
  timer: unknown
}
export interface FailureAnalysisSubscription {
  loadAnalysis: (priority?: AnalysisLoadPriority) => Promise<AnalysisRequestResult>
  startAnalysis: (force?: boolean) => Promise<AnalysisRequestResult>
  unsubscribe: () => void
}

function statusCode(cause: unknown): number | undefined {
  return (cause as { response?: { status?: number } } | null)?.response?.status
}

/** Abort settles the local operation even when a transport ignores cancellation. */
function abortable<T>(work: () => Promise<T>, signal: AbortSignal): Promise<T | undefined> {
  if (signal.aborted) return Promise.resolve(undefined)
  return new Promise((resolve, reject) => {
    const cancel = () => { signal.removeEventListener('abort', cancel); resolve(undefined) }
    signal.addEventListener('abort', cancel, { once: true })
    Promise.resolve().then(() => signal.aborted ? undefined : work()).then(
      value => { signal.removeEventListener('abort', cancel); resolve(value) },
      cause => { signal.removeEventListener('abort', cancel); reject(cause) },
    )
  })
}

/** Shared lifecycle and bounded GET queue; importing this module never sends a request. */
export function createFailureAnalysisStore(client: AnalysisClient, options: StoreOptions = {}) {
  const entries = new Map<string, Entry>()
  const queue: { entry: Entry; operation: Operation }[] = []
  const maximum = Math.max(1, Math.floor(options.maxConcurrentGets ?? 3))
  const setTimer = options.setTimer ?? ((callback, delay) => setTimeout(callback, delay))
  const clearTimer = options.clearTimer ?? (timer => clearTimeout(timer as ReturnType<typeof setTimeout>))
  let activeGets = 0

  const alive = (entry: Entry) => entries.get(entry.key) === entry && entry.listeners.size > 0
  const current = (entry: Entry, operation: Operation) => alive(entry) && entry.operation === operation && !operation.controller.signal.aborted
  function update(entry: Entry, changes: Partial<FailureAnalysisState>): void {
    entry.state = { ...entry.state, ...changes }
    for (const listener of entry.listeners) listener(entry.state)
  }
  function clearPoll(entry: Entry): void {
    if (entry.timer !== undefined) clearTimer(entry.timer)
    entry.timer = undefined
  }
  function schedulePoll(entry: Entry): void {
    clearPoll(entry)
    if (alive(entry) && entry.state.analysis?.status === 'running') {
      entry.timer = setTimer(() => { entry.timer = undefined; void load(entry) }, options.pollIntervalMs ?? 3000)
    }
  }
  function accept(entry: Entry, data: FailureAnalysis): boolean {
    if (data.report_id !== entry.reportId) {
      update(entry, { analysis: null, errorKey: 'testFailures.analysis.loadFailed' })
    } else if (data.report_revision !== entry.revision) {
      update(entry, { analysis: null, revisionChanged: true, errorKey: 'testFailures.analysis.revisionChanged' })
    } else {
      update(entry, { analysis: data, revisionChanged: false, conflict: false, errorKey: '' })
      return true
    }
    return false
  }
  async function run(entry: Entry, operation: Operation): Promise<void> {
    operation.started = true
    if (operation.kind === 'get') update(entry, { queued: false })
    let outcome: AnalysisRequestResult = { status: 'cancelled' }
    try {
      const data = await abortable(() => operation.kind === 'get'
        ? client.load(entry.reportId, operation.controller.signal)
        : client.start(entry.reportId, entry.revision, operation.controller.signal, operation.force), operation.controller.signal)
      if (data && current(entry, operation)) {
        outcome = accept(entry, data) ? { status: 'success', checkedAt: new Date().toISOString() } : { status: 'error' }
      }
    } catch (cause) {
      if (current(entry, operation)) {
        outcome = { status: 'error' }
        const conflict = operation.kind === 'post' && statusCode(cause) === 409
        update(entry, { conflict, errorKey: conflict ? 'testFailures.analysis.busy'
          : operation.kind === 'post' ? 'testFailures.analysis.startFailed' : 'testFailures.analysis.loadFailed' })
      }
    } finally {
      if (current(entry, operation)) {
        entry.operation = null
        update(entry, { loading: false, queued: false, starting: false })
        schedulePoll(entry)
      }
      operation.resolve(outcome)
    }
  }
  function pump(): void {
    while (activeGets < maximum && queue.length) {
      const { entry, operation } = queue.shift()!
      if (!current(entry, operation)) { operation.resolve({ status: 'cancelled' }); continue }
      activeGets += 1
      void run(entry, operation).finally(() => { activeGets -= 1; pump() })
    }
  }
  function enqueue(entry: Entry, operation: Operation): void {
    const firstBackground = operation.priority === 'user' ? queue.findIndex(item => item.operation.priority === 'background') : -1
    if (firstBackground < 0) queue.push({ entry, operation })
    else queue.splice(firstBackground, 0, { entry, operation })
  }
  function begin(entry: Entry, kind: Operation['kind'], priority: AnalysisLoadPriority = 'background', force = false): Promise<AnalysisRequestResult> {
    if (!alive(entry)) return Promise.resolve({ status: 'cancelled' })
    if (entry.operation) {
      const operation = entry.operation
      if (kind === 'get' && operation.kind === 'get' && !operation.started && priority === 'user' && operation.priority !== 'user') {
        const index = queue.findIndex(item => item.operation === operation)
        if (index >= 0) queue.splice(index, 1)
        operation.priority = 'user'
        enqueue(entry, operation)
        pump()
      }
      return operation.promise
    }
    clearPoll(entry)
    let resolve!: (result: AnalysisRequestResult) => void
    const operation: Operation = { kind, controller: new AbortController(), promise: new Promise(done => { resolve = done }), resolve: result => resolve(result), started: false, priority, force }
    entry.operation = operation
    update(entry, { loading: kind === 'get', queued: kind === 'get', starting: kind === 'post', errorKey: '', conflict: false })
    if (kind === 'get') { enqueue(entry, operation); pump() }
    else void run(entry, operation)
    return operation.promise
  }
  function load(entry: Entry, priority: AnalysisLoadPriority = 'background'): Promise<AnalysisRequestResult> { return begin(entry, 'get', priority) }
  function start(entry: Entry, force = false): Promise<AnalysisRequestResult> {
    if (entry.operation) return entry.operation.promise
    return failureAnalysisCanGenerate(entry.state) && (entry.state.analysis?.status !== 'complete' || force)
      ? begin(entry, 'post', 'user', force) : Promise.resolve({ status: 'skipped' })
  }

  return {
    subscribe(reportId: string, revision: string, listener: (state: FailureAnalysisState) => void, evidenceVersion = ''): FailureAnalysisSubscription {
      if (!reportId || !revision) {
        listener(emptyFailureAnalysisState())
        return { loadAnalysis: () => Promise.resolve({ status: 'skipped' }), startAnalysis: () => Promise.resolve({ status: 'skipped' }), unsubscribe: () => {} }
      }
      // Attachments can change without changing the failure/confirmation revision.
      // Keep those evidence snapshots separate so a late GET cannot restore old results.
      const key = JSON.stringify([reportId, revision, evidenceVersion])
      let entry = entries.get(key)
      const isNew = !entry
      if (!entry) {
        entry = { key, reportId, revision, state: emptyFailureAnalysisState(), listeners: new Set(), operation: null, timer: undefined }
        entries.set(key, entry)
      }
      const subscribedEntry = entry
      const notify = (state: FailureAnalysisState) => listener(state)
      entry.listeners.add(notify)
      listener(entry.state)
      if (isNew) void load(entry)
      let subscribed = true
      return {
        loadAnalysis: priority => subscribed ? load(subscribedEntry, priority) : Promise.resolve({ status: 'cancelled' }),
        startAnalysis: force => subscribed ? start(subscribedEntry, force) : Promise.resolve({ status: 'cancelled' }),
        unsubscribe: () => {
          if (!subscribed) return
          subscribed = false
          subscribedEntry.listeners.delete(notify)
          if (subscribedEntry.listeners.size) return
          entries.delete(key)
          clearPoll(subscribedEntry)
          const operation = subscribedEntry.operation
          operation?.controller.abort()
          if (operation && !operation.started) {
            const index = queue.findIndex(item => item.operation === operation)
            if (index >= 0) queue.splice(index, 1)
            operation.resolve({ status: 'cancelled' })
          }
          subscribedEntry.operation = null
          pump()
        },
      }
    },
  }
}
