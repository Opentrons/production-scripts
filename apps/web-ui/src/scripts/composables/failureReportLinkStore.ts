import type { FailureReportLink } from '../api/testFailures'
import { failureReportLinkKey, type FailureReportLinkIdentity } from '../utils/failureReportLinks'

export interface FailureReportLinkState {
  result: FailureReportLink | null
  loading: boolean
  failed: boolean
}
export const emptyFailureReportLinkState = (): FailureReportLinkState => ({ result: null, loading: false, failed: false })
interface LinkClient {
  load: (id: string, signal: AbortSignal) => Promise<FailureReportLink>
  refresh: (id: string, signal: AbortSignal) => Promise<FailureReportLink>
}
interface Options {
  pollIntervalMs?: number
  maxConcurrent?: number
  setTimer?: (callback: () => void, delay: number) => unknown
  clearTimer?: (timer: unknown) => void
}
interface Entry {
  key: string
  identity: FailureReportLinkIdentity
  state: FailureReportLinkState
  listeners: Set<(state: FailureReportLinkState) => void>
  controller: AbortController | null
  timer: unknown
  queued: boolean
  force: boolean
}

/** Visible list rows and an open detail share matching requests and running polls. */
export function createFailureReportLinkStore(client: LinkClient, options: Options = {}) {
  const entries = new Map<string, Entry>(), queue: Entry[] = []
  const setTimer = options.setTimer ?? ((callback, delay) => setTimeout(callback, delay))
  const clearTimer = options.clearTimer ?? (timer => clearTimeout(timer as ReturnType<typeof setTimeout>))
  const maximum = Math.max(1, Math.floor(options.maxConcurrent ?? 3))
  let active = 0
  const alive = (entry: Entry) => entries.get(entry.key) === entry && entry.listeners.size > 0
  function update(entry: Entry, changes: Partial<FailureReportLinkState>): void {
    entry.state = { ...entry.state, ...changes }
    for (const listener of entry.listeners) listener(entry.state)
  }
  function clearPoll(entry: Entry): void {
    if (entry.timer !== undefined) clearTimer(entry.timer)
    entry.timer = undefined
  }
  async function run(entry: Entry): Promise<void> {
    const controller = new AbortController()
    entry.controller = controller
    const current = () => alive(entry) && entry.controller === controller && !controller.signal.aborted
    // Release the queue slot promptly even if a transport ignores cancellation.
    const aborted = new Promise<undefined>(resolve => controller.signal.addEventListener('abort', () => resolve(undefined), { once: true }))
    try {
      const result = await Promise.race([entry.force ? client.refresh(entry.identity.id, controller.signal) : client.load(entry.identity.id, controller.signal), aborted])
      if (result && current()) {
        if ((result.sn || '').trim() !== (entry.identity.sn || '').trim()
          || (result.report_run_id || '').trim() !== (entry.identity.report_run_id || '').trim()) {
          update(entry, { result: null, failed: true })
        } else update(entry, { result, failed: false })
      }
    } catch {
      if (current()) update(entry, { failed: true })
    } finally {
      if (current()) {
        entry.controller = null
        update(entry, { loading: false })
        if (!entry.state.failed && entry.state.result?.status === 'running') {
          entry.timer = setTimer(() => { entry.timer = undefined; request(entry, false) }, options.pollIntervalMs ?? 3000)
        }
      }
      active -= 1
      pump()
    }
  }
  function pump(): void {
    while (active < maximum && queue.length) {
      const entry = queue.shift()!
      entry.queued = false
      if (!alive(entry)) continue
      active += 1
      void run(entry)
    }
  }
  function request(entry: Entry, force: boolean): void {
    if (!alive(entry) || entry.controller || entry.queued) return
    clearPoll(entry)
    entry.force = force
    entry.queued = true
    update(entry, { loading: true, failed: false })
    queue.push(entry)
    pump()
  }
  return {
    subscribe(identity: FailureReportLinkIdentity, listener: (state: FailureReportLinkState) => void) {
      const key = failureReportLinkKey(identity)
      let entry = entries.get(key)
      const isNew = !entry
      if (!entry) {
        entry = { key, identity: { ...identity }, state: emptyFailureReportLinkState(), listeners: new Set(), controller: null, timer: undefined, queued: false, force: false }
        entries.set(key, entry)
      }
      // A scan can replace an evidence ID without changing its matching identity.
      // Keep shared results, but send the next request to the currently selected ID.
      entry.identity = { ...identity }
      const currentEntry = entry, notify = (state: FailureReportLinkState) => listener(state)
      entry.listeners.add(notify)
      listener(entry.state)
      if (isNew) request(entry, false)
      let subscribed = true
      return {
        refresh(force = false): void { if (subscribed) request(currentEntry, force) },
        unsubscribe(): void {
          if (!subscribed) return
          subscribed = false
          currentEntry.listeners.delete(notify)
          if (currentEntry.listeners.size) return
          entries.delete(key)
          clearPoll(currentEntry)
          currentEntry.controller?.abort()
          const index = queue.indexOf(currentEntry)
          if (index >= 0) queue.splice(index, 1)
          pump()
        },
      }
    },
  }
}
