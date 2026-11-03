import assert from 'node:assert/strict'
import fs from 'node:fs'
import { test } from 'node:test'
import ts from 'typescript'
import { computed, reactive, ref, watch, effectScope } from 'vue'
import { createFailureDraftStorage } from '../src/scripts/utils/failureDraftStorage.ts'
import { defaultFailureReportId } from '../src/scripts/utils/failureReportSelection.ts'

const source = fs.readFileSync(new URL('../src/views/production_modules/TestFailuresView.vue', import.meta.url), 'utf8')
  .match(/<script setup lang="ts">([\s\S]*?)<\/script>/)[1]
  .replace(/^import .*\n/gm, '')
const script = ts.transpileModule(source, { compilerOptions: { target: ts.ScriptTarget.ES2022 } }).outputText
const instantiate = new Function('dependencies', `
  const { computed, reactive, ref, watch, onMounted, onBeforeUnmount, useAppLocale, useAuthStore, testFailuresApi, axios, chineseCopy, englishCopy, createFailureDraftStorage, defaultFailureReportId } = dependencies;
  ${script}
  return { devices, drafts, editDraft, loadDevices, refresh, save, savedReportFolder, applied, selectedDevice, openReport };
`)

function row(id, folder, version = 'v1') {
  return {
    id, report_folder: folder, sn: 'SAME-SN', product: 'P50M', version,
    last_test_at: '2026-10-30T02:00:00Z', report_count: 1, unconfirmed_count: 1,
    failure_types: ['test_failure'], summary: [], confirmation: null,
    recent_confirmations: [], reports: [{ id: `${id}-main`, report_folder: folder, revision: version }],
  }
}
function memoryStorage() {
  const items = new Map()
  return { getItem: key => items.get(key) ?? null, setItem: (key, value) => items.set(key, value), removeItem: key => items.delete(key) }
}
function harness(t, { storage = memoryStorage(), userId = 'user-a', confirmGate, initialRows, failReloadAfterSave = false } = {}) {
  let rows = initialRows || [row('folder-a', '20261029/report'), row('folder-b', '20261030/report')]
  const confirmations = [], dispose = []
  const scope = effectScope()
  const auth = reactive({ user: { id: userId, role: 'editor' } })
  const draftStorage = createFailureDraftStorage(() => storage)
  const scan = { running: false, last_scan_at: '2026-10-30T02:00:00Z' }
  const view = scope.run(() => instantiate({
    computed, reactive, ref, watch, onMounted() {}, onBeforeUnmount(callback) { dispose.push(callback) },
    useAppLocale: () => ({ t: key => key, locale: ref('en-US') }),
    useAuthStore: () => auth,
    createFailureDraftStorage: () => draftStorage, defaultFailureReportId,
    chineseCopy: {}, englishCopy: {}, axios: { isAxiosError: () => false },
    testFailuresApi: {
      devices: async query => {
        if (failReloadAfterSave && confirmations.length) throw new Error('list unavailable')
        const filtered = rows.filter(item => query.confirmation === 'all' || (query.confirmation === 'confirmed' ? item.unconfirmed_count === 0 : item.unconfirmed_count > 0))
        return { data: { devices: filtered, total: filtered.length, scan } }
      },
      scan: async () => ({ data: scan }),
      confirm: async (id, text, version) => {
        confirmations.push({ id, text, version })
        if (confirmGate) await confirmGate
        const target = rows.find(item => item.id === id)
        assert.equal(version, target.version)
        const confirmation = { id: 'confirmation-a', text }
        rows = rows.map(item => item.id === id ? { ...item, confirmation, unconfirmed_count: 0 } : item)
        const updated = rows.find(item => item.id === id)
        return { data: { confirmation, device: { ...updated, matched_report_ids: updated.reports.map(report => report.id) } } }
      },
    },
  }))
  t.after(() => { scope.stop(); dispose.forEach(callback => callback()) })
  return { view, confirmations, storage, draftStorage, auth, update() { rows = rows.map(item => ({ ...item, version: 'v2' })) } }
}
const flush = () => new Promise(resolve => setImmediate(resolve))

test('ordinary refresh retains both independent draft versions and conflict markers', async t => {
  const { view, update } = harness(t)
  await view.loadDevices()
  assert.equal(view.devices.value.length, 2)
  for (const item of view.devices.value) view.editDraft(item, `Repair ${item.report_folder}`)
  view.drafts['folder-a'].conflict = true
  view.drafts['folder-a'].error = 'review required'
  update()
  view.refresh()
  await flush()
  assert.equal(view.drafts['folder-a'].version, 'v1')
  assert.equal(view.drafts['folder-b'].version, 'v1')
  assert.equal(view.drafts['folder-a'].conflict, true)
  assert.equal(view.drafts['folder-a'].error, 'review required')
  assert.equal(view.drafts['folder-b'].text, 'Repair 20261030/report')
})

test('rebasing and saving one folder preserves the same serial’s other row and draft', async t => {
  const { view, update, confirmations, draftStorage } = harness(t)
  await view.loadDevices()
  for (const item of view.devices.value) view.editDraft(item, `Repair ${item.report_folder}`)
  update()
  await view.loadDevices('folder-a')
  assert.equal(view.drafts['folder-a'].version, 'v2')
  assert.equal(view.drafts['folder-b'].version, 'v1')
  await view.save(view.devices.value.find(item => item.id === 'folder-a'))
  assert.deepEqual(confirmations, [{ id: 'folder-a', text: 'Repair 20261029/report', version: 'v2' }])
  assert.equal(view.drafts['folder-a'], undefined)
  assert.equal(view.drafts['folder-b'].text, 'Repair 20261030/report')
  assert.equal(view.drafts['folder-b'].version, 'v1')
  assert.deepEqual(view.devices.value.map(item => item.id), ['folder-b'])
  assert.equal(view.savedReportFolder.value, '20261029/report')
  assert.equal(draftStorage.read('user-a', 'folder-a'), null)
  assert.equal(draftStorage.read('user-a', 'folder-b').version, 'v1')
})

test('draft survives returning to the page with its original evidence version', async t => {
  const first = harness(t)
  await first.view.loadDevices()
  first.view.editDraft(first.view.devices.value[0], '保留维修原因与措施')
  const returned = harness(t, { storage: first.storage })
  returned.update()
  await returned.view.loadDevices()
  assert.equal(returned.view.drafts['folder-a'].text, '保留维修原因与措施')
  assert.equal(returned.view.drafts['folder-a'].version, 'v1')
  assert.equal(returned.view.drafts['folder-a'].restored, true)
  await returned.view.loadDevices('folder-a')
  assert.equal(returned.draftStorage.read('user-a', 'folder-a').version, 'v2')
})

test('different authenticated accounts cannot see each other’s in-memory or stored drafts', async t => {
  const { view, auth, storage } = harness(t)
  await view.loadDevices()
  view.editDraft(view.devices.value[0], 'user-a repair notes')
  auth.user = { id: 'user-b', role: 'editor' }
  assert.equal(view.drafts['folder-a'], undefined)
  view.editDraft(view.devices.value[0], 'user-b repair notes')
  const otherPage = harness(t, { storage, userId: 'user-a' })
  await otherPage.view.loadDevices()
  assert.equal(otherPage.view.drafts['folder-a'].text, 'user-a repair notes')
  assert.equal(view.drafts['folder-a'].text, 'user-b repair notes')
})

test('successful submission clears only the submitted draft snapshot', async t => {
  let finish
  const confirmGate = new Promise(resolve => { finish = resolve })
  const { view, draftStorage } = harness(t, { confirmGate })
  await view.loadDevices()
  const device = view.devices.value[0]
  view.editDraft(device, 'Submitted notes')
  const saving = view.save(device)
  view.editDraft(device, 'Newer notes retained')
  finish()
  await saving
  assert.equal(view.drafts[device.id].text, 'Newer notes retained')
  assert.equal(draftStorage.read('user-a', device.id).text, 'Newer notes retained')
})

test('unavailable browser storage leaves editing and saving operational', async t => {
  const unavailable = new Proxy({}, { get() { throw new Error('storage disabled') } })
  const { view } = harness(t, { storage: unavailable })
  await view.loadDevices()
  const device = view.devices.value[0]
  view.editDraft(device, '仍可保存')
  assert.equal(view.drafts[device.id].storageFailed, true)
  await view.save(device)
  assert.equal(view.drafts[device.id], undefined)
})

test('confirmation retains the filtered evidence selection when list reload fails', async t => {
  const folder = row('folder-a', '20261029/report')
  folder.reports.push({ id: 'folder-a-probe', report_folder: folder.report_folder, revision: 'v1' })
  folder.matched_report_ids = ['folder-a-probe']
  const { view } = harness(t, { initialRows: [folder], failReloadAfterSave: true })
  view.applied.confirmation = 'all'
  await view.loadDevices()
  const device = view.devices.value[0]
  view.openReport(device)
  view.editDraft(device, 'Verified probe repair')
  await view.save(device)
  assert.deepEqual(view.devices.value[0].matched_report_ids, ['folder-a-probe'])
  assert.equal(defaultFailureReportId(view.devices.value[0]), 'folder-a-probe')
  assert.deepEqual(view.selectedDevice.value.matched_report_ids, ['folder-a-probe'])
})
