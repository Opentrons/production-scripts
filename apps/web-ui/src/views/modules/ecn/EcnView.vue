<template>
  <main class="ecn-page">
    <div class="ecn-shell">
      <header class="page-heading">
        <div>
          <div class="ecn-title-row"><img src="/ecn-favicon.svg" alt="" aria-hidden="true" /><h1>{{ t('ecn.title') }}</h1></div>
          <p class="introduction">{{ t('ecn.introduction') }}</p>
        </div>
        <div v-if="activeView !== 'monitor'" class="heading-actions">
          <a class="secondary-button" :href="sourceUrl" target="_blank" rel="noopener noreferrer">
            <ExternalLink :size="17" aria-hidden="true" />
            {{ t('ecn.openMaster') }}
          </a>
          <button class="secondary-button" type="button" :disabled="checkingSync" @click="checkSync">
            <RefreshCw :size="17" :class="{ spinning: checkingSync }" aria-hidden="true" />
            {{ t('ecn.checkSync') }}
          </button>
          <button class="primary-button" type="button" :disabled="activeTable === 'ipqc' || !nextEcnNumber" @click="openCreateDialog">
            <Plus :size="18" aria-hidden="true" />
            {{ t('ecn.create.action') }}
          </button>
        </div>
      </header>

      <p v-if="notice" class="notice" :class="`is-${notice.type}`" role="status">{{ notice.message }}</p>

      <nav class="ecn-tabs" role="tablist" :aria-label="t('ecn.tabs.label')">
        <button type="button" role="tab" :aria-selected="activeView === 'monitor'" :class="{ 'is-active': activeView === 'monitor' }" @click="switchView('monitor')">{{ t('ecn.tabs.monitor') }}</button>
        <button type="button" role="tab" :aria-selected="activeView === 'records' && activeTable === 'eng'" :class="{ 'is-active': activeView === 'records' && activeTable === 'eng' }" @click="switchTable('eng')">ENG</button>
        <button type="button" role="tab" :aria-selected="activeView === 'records' && activeTable === 'ipqc'" :class="{ 'is-active': activeView === 'records' && activeTable === 'ipqc' }" @click="switchTable('ipqc')">IPQC</button>
      </nav>

      <section v-if="activeView !== 'monitor' && syncStatus" class="sync-panel" :class="{ 'is-synced': syncStatus.in_sync }">
        <div>
          <strong>{{ syncStatus.in_sync ? t('ecn.sync.syncedTitle') : t('ecn.sync.unsyncedTitle') }}</strong>
          <p>{{ t('ecn.sync.counts', { google: syncStatus.google_total, mongo: syncStatus.mongodb_total }) }}</p>
        </div>
        <div v-if="!syncStatus.in_sync" class="difference-counts">
          <span>{{ t('ecn.sync.missing', { count: syncStatus.missing_count }) }}</span>
          <span>{{ t('ecn.sync.extra', { count: syncStatus.extra_count }) }}</span>
          <span>{{ t('ecn.sync.changed', { count: syncStatus.changed_count }) }}</span>
          <button class="primary-button sync-now-button" type="button" :disabled="syncing" @click="syncMongo">
            <RefreshCw :size="15" :class="{ spinning: syncing }" aria-hidden="true" />
            {{ syncing ? t('ecn.syncing') : t('ecn.syncNow') }}
          </button>
        </div>
      </section>

      <section v-if="activeView !== 'monitor'" class="records-card" aria-labelledby="ecn-records-title">
        <header class="records-toolbar">
          <div><h2 id="ecn-records-title">{{ t('ecn.table.title') }}</h2><p>{{ t('ecn.table.description') }}</p></div>
          <form class="search-form" @submit.prevent="applySearch">
            <Search :size="17" aria-hidden="true" />
            <input v-model="searchDraft" type="search" :placeholder="t('ecn.searchPlaceholder')" />
            <button type="submit">{{ t('common.actions.search') }}</button>
          </form>
        </header>

        <div v-if="loading" class="state-box"><RefreshCw class="spinning" :size="24" /><span>{{ t('ecn.loading') }}</span></div>
        <div v-else-if="loadError" class="state-box is-error" role="alert">
          <TriangleAlert :size="24" /><strong>{{ t('ecn.loadFailed') }}</strong><span>{{ loadError }}</span>
          <button type="button" @click="loadRecords">{{ t('common.actions.retry') }}</button>
        </div>
        <div v-else-if="!records.length" class="state-box"><FileSpreadsheet :size="28" /><strong>{{ t('ecn.empty') }}</strong></div>
        <div v-else-if="activeTable === 'eng'" class="table-scroll">
          <table>
            <thead><tr>
              <th><button class="sort-button" type="button" :aria-label="sortAriaLabel" @click="toggleSortOrder">
                {{ t('ecn.table.numberTitle') }}
                <ArrowUp v-if="sortOrder === 'asc'" :size="15" aria-hidden="true" />
                <ArrowDown v-else :size="15" aria-hidden="true" />
              </button></th><th>{{ t('ecn.table.product') }}</th>
              <th>{{ t('ecn.table.changeItem') }}</th><th>{{ t('ecn.table.revision') }}</th>
              <th>{{ t('ecn.table.changeDate') }}</th><th>{{ t('ecn.table.changedBy') }}</th>
              <th>{{ t('ecn.table.actions') }}</th>
            </tr></thead>
            <tbody>
              <tr v-for="record in records" :key="record.id">
                <td class="record-identity">
                  <strong>{{ record.ecn_number || record.form_number || '—' }}</strong>
                  <span>{{ record.ecn_title || record.change_item || '—' }}</span>
                  <small v-if="record.origin === 'created'">{{ t('ecn.createdLocally') }}</small>
                </td>
                <td>{{ record.product_name || '—' }}</td>
                <td class="wide-cell">{{ record.change_item || '—' }}</td>
                <td><span class="revision">{{ record.before_change || '—' }}</span><ArrowRight :size="14" /><span class="revision">{{ record.after_change || '—' }}</span></td>
                <td>{{ record.change_date || '—' }}</td><td>{{ record.changed_by || '—' }}</td>
                <td><button class="record-menu-trigger" type="button" :aria-label="t('ecn.table.more')" :title="t('ecn.table.more')" :aria-expanded="menuRecord?.id === record.id" @click="toggleMenu(record, $event)" @mouseenter="cancelMenuClose" @mouseleave="scheduleMenuClose"><Ellipsis :size="20" aria-hidden="true" /></button></td>
              </tr>
            </tbody>
          </table>
        </div>
        <div v-else class="table-scroll">
          <table class="ipqc-table">
            <thead><tr><th v-for="column in ipqcColumns" :key="column.key"><span v-if="column.key !== 'status'">{{ t(column.label) }}</span><span v-else class="status-header"><span>{{ t(column.label) }}</span><select v-model="statusFilter" :aria-label="t('ecn.table.statusFilter')" @change="applyStatusFilter"><option value="">{{ t('ecn.table.allStatuses') }}</option><option v-for="option in statusOptions" :key="option" :value="option">{{ option }}</option></select></span></th><th>{{ t('ecn.table.actions') }}</th></tr></thead>
            <tbody><tr v-for="record in records" :key="record.id">
              <td v-for="column in ipqcColumns" :key="column.key">{{ ipqcValue(record, column.key) || '—' }}</td>
              <td><button class="record-menu-trigger" type="button" :aria-label="t('ecn.table.more')" @click="toggleMenu(record, $event)"><Ellipsis :size="20" aria-hidden="true" /></button></td>
            </tr></tbody>
          </table>
        </div>

        <footer class="pagination">
          <span>{{ t('ecn.pagination.total', { count: total }) }}</span>
          <div>
            <button type="button" :disabled="page <= 1 || loading" @click="changePage(page - 1)">{{ t('ecn.pagination.previous') }}</button>
            <span>{{ t('ecn.pagination.page', { page, pages: totalPages }) }}</span>
            <button type="button" :disabled="page >= totalPages || loading" @click="changePage(page + 1)">{{ t('ecn.pagination.next') }}</button>
            <form class="page-jump" @submit.prevent="jumpToPage">
              <label for="ecn-page-input">{{ t('ecn.pagination.jumpTo') }}</label>
              <input id="ecn-page-input" v-model="pageInput" type="number" min="1" :max="totalPages" inputmode="numeric" :aria-label="t('ecn.pagination.jumpTo')" />
              <button type="submit" :disabled="loading">{{ t('ecn.pagination.jump') }}</button>
            </form>
          </div>
        </footer>
      </section>

      <section v-else class="monitor-panel" aria-labelledby="ecn-monitor-title">
        <header class="records-toolbar monitor-toolbar">
          <div><h2 id="ecn-monitor-title">{{ t('ecn.monitor.title') }}</h2><p>{{ t('ecn.monitor.description') }}</p></div>
          <div class="heading-actions">
            <button class="secondary-button" type="button" @click="monitorSettingsOpen = true">{{ t('ecn.monitor.settings') }}</button>
            <button class="primary-button" type="button" :disabled="monitorRunning" @click="runMonitorScan">
              <RefreshCw :size="17" :class="{ spinning: monitorRunning }" />
              {{ monitorRunning ? t('ecn.monitor.scanning') : t('ecn.monitor.run') }}
            </button>
          </div>
        </header>
        <div v-if="monitorRunning" class="monitor-progress" role="status"><RefreshCw class="spinning" :size="17" /><span v-for="line in monitorProgress" :key="line">{{ line }}</span></div>
        <div v-if="monitorError" class="notice is-error" role="alert">{{ monitorError }}</div>
        <div v-if="!monitorResults.length && !monitorLoading" class="state-box"><FileSpreadsheet :size="28" /><strong>{{ t('ecn.monitor.empty') }}</strong></div>
        <div v-else-if="monitorLoading" class="state-box"><RefreshCw class="spinning" :size="24" /><span>{{ t('ecn.monitor.loading') }}</span></div>
        <div v-for="result in monitorResults" :key="result.id" class="monitor-day">
          <button class="monitor-day-header" type="button" @click="toggleMonitorDay(result.id)">
            <span><strong>{{ result.scan_date }}</strong><small>{{ result.trigger === 'scheduled' ? t('ecn.monitor.scheduled') : t('ecn.monitor.manual') }} · {{ formatMonitorDate(result.scanned_at) }}</small></span>
            <span class="monitor-summary"><b :class="{ 'has-alerts': result.total_alerts > 0 }">{{ result.total_alerts }}</b>{{ t('ecn.monitor.alerts') }}<span>{{ monitorOpen[result.id] ? t('ecn.monitor.collapse') : t('ecn.monitor.expand') }}</span></span>
          </button>
          <div v-if="monitorOpen[result.id]" class="monitor-day-body">
            <details class="monitor-process"><summary>{{ t('ecn.monitor.process', { count: monitorLogs(result).length }) }}</summary><div class="monitor-checklist"><div v-for="item in monitorChecklist(result)" :key="item.key" class="monitor-check-item" :class="`is-${item.status}`"><CircleCheck v-if="item.status === 'success'" :size="18" /><X v-else-if="item.status === 'warning' || item.status === 'error'" :size="18" /><span v-else class="monitor-check-dash">—</span><div><strong>{{ t(item.labelKey) }}</strong><small>{{ item.message }}</small></div></div></div><div class="monitor-log-list"><article v-for="(log, index) in monitorLogs(result)" :key="`${log.at}-${index}`" class="monitor-log" :class="`is-${log.status}`"><header><span class="monitor-log-status">{{ t(`ecn.monitor.status.${log.status}`) }}</span><strong>{{ log.title }}</strong><time>{{ formatMonitorDate(log.at) }}</time></header><p>{{ log.message }}</p><small v-if="log.checked_count !== null && log.checked_count !== undefined">{{ t('ecn.monitor.checkedCount', { count: log.checked_count }) }}</small><details v-if="monitorLogIssues(log).length" class="monitor-log-details"><summary>{{ t('ecn.monitor.problemDetails', { count: monitorLogIssues(log).length }) }}</summary><ul class="monitor-log-issues"><li v-for="(issue, issueIndex) in monitorLogIssues(log)" :key="`${issue.message}-${issueIndex}`">{{ issue.message }}</li></ul></details><details v-if="log.details?.missing_records?.length" class="monitor-log-details"><summary>{{ t('ecn.monitor.syncMissing') }}</summary><div class="monitor-log-data">{{ monitorRecordNumbers(log.details.missing_records) }}</div></details><details v-if="log.details?.extra_records?.length" class="monitor-log-details"><summary>{{ t('ecn.monitor.syncExtra') }}</summary><div class="monitor-log-data">{{ monitorRecordNumbers(log.details.extra_records) }}</div></details><details v-if="log.details?.changed_records?.length" class="monitor-log-details"><summary>{{ t('ecn.monitor.syncChanged') }}</summary><div class="monitor-log-data">{{ monitorRecordNumbers(log.details.changed_records) }}</div></details></article></div></details>
            <div v-if="!result.categories.length" class="monitor-ok"><CircleCheck :size="17" />{{ t('ecn.monitor.noAlerts') }}</div>
            <details v-for="group in monitorAlertGroups(result)" :key="group.category" class="monitor-alert-group" :class="{ 'is-safe': group.count === 0, 'is-alert': group.count > 0 }"><summary><CircleCheck v-if="group.count === 0" :size="17" /><X v-else :size="17" /><span>{{ monitorCategoryLabels[group.category] ? t(monitorCategoryLabels[group.category]) : group.category }}</span><b>{{ group.count }}</b></summary><div v-for="item in group.details" :key="`${item.message}-${item.ecn_number || ''}`" class="monitor-alert-row"><strong>{{ item.ecn_number || t('ecn.monitor.dataset') }}</strong><span>{{ item.message }}</span></div></details>
          </div>
        </div>
      </section>
    </div>

    <div v-if="createDialogOpen || editRecord" class="dialog-backdrop" @mousedown.self="closeFormDialog">
      <section class="dialog create-dialog" role="dialog" aria-modal="true" :aria-labelledby="createResult ? 'ecn-create-success' : 'ecn-form-title'">
        <button class="dialog-close" type="button" :aria-label="t('common.actions.close')" :disabled="creating || saving || editingLoading" @click="closeFormDialog"><X :size="20" /></button>
        <template v-if="createResult">
          <div class="success-icon"><CircleCheck :size="28" /></div>
          <h2 id="ecn-create-success">{{ t('ecn.create.successTitle') }}</h2>
          <p>{{ createResult.record.ecn_number }} {{ createResult.record.ecn_title }}</p>
          <div class="result-links">
            <a :href="createResult.folder_url" target="_blank" rel="noopener noreferrer">{{ t('ecn.create.openFolder') }} <ExternalLink :size="15" /></a>
            <a :href="createResult.spreadsheet_url" target="_blank" rel="noopener noreferrer">{{ t('ecn.create.openSheet') }} <ExternalLink :size="15" /></a>
          </div>
          <button class="primary-button full-width" type="button" @click="closeFormDialog">{{ t('common.actions.close') }}</button>
        </template>
        <div v-else-if="editingLoading" class="state-box"><RefreshCw class="spinning" :size="24" /><span>{{ t('ecn.edit.loading') }}</span></div>
        <form v-else @submit.prevent="submitForm">
          <p class="eyebrow">{{ editRecord ? t('ecn.edit.title') : t('ecn.create.eyebrow') }}</p><h2 id="ecn-form-title">{{ editRecord ? t('ecn.edit.title') : t('ecn.create.title') }}</h2>
          <p class="dialog-description">{{ editRecord ? t('ecn.edit.description') : t('ecn.create.description') }}</p>
          <label><span>{{ t('ecn.create.number') }}</span><input v-model.trim="createForm.ecn_number" required readonly maxlength="32" placeholder="ECN-0577" autocomplete="off" /><small v-if="!editRecord">{{ t('ecn.create.numberExample') }}</small></label>
          <label><span>{{ t('ecn.create.productModel') }}</span><input v-model.trim="createForm.product_model" :required="!editRecord" list="ecn-product-model-options" maxlength="120" :placeholder="t('ecn.create.productModelPlaceholder')" autocomplete="off" /><small>{{ t('ecn.create.productModelHint') }}</small></label>
          <datalist id="ecn-product-model-options"><option v-for="model in productModelOptions" :key="model" :value="model" /></datalist>
          <label><span>{{ t('ecn.create.ecnTitle') }}</span><input v-model.trim="createForm.ecn_title" required maxlength="180" placeholder="913-00061 Drawing Update" autocomplete="off" /><small>{{ t('ecn.create.titleExample') }}</small></label>
          <label><span>{{ t('ecn.create.changeItem') }}</span><input v-model.trim="createForm.change_item" :required="!editRecord" maxlength="500" :placeholder="t('ecn.create.changeItemPlaceholder')" autocomplete="off" /></label>
          <label><span>{{ t('ecn.create.beforeChange') }}</span><input v-model.trim="createForm.before_change" maxlength="500" :placeholder="t('ecn.create.beforeChangePlaceholder')" autocomplete="off" /></label>
          <label><span>{{ t('ecn.create.afterChange') }}</span><input v-model.trim="createForm.after_change" maxlength="500" :placeholder="t('ecn.create.afterChangePlaceholder')" autocomplete="off" /></label>
          <label><span>{{ t('ecn.create.changeDate') }}</span><input v-model="createForm.change_date" :required="!editRecord" type="date" /></label>
          <label><span>{{ t('ecn.create.changedBy') }}</span><input v-model.trim="createForm.changed_by" :required="!editRecord" list="ecn-changed-by-options" maxlength="120" :placeholder="t('ecn.create.changedByPlaceholder')" autocomplete="off" /></label>
          <datalist id="ecn-changed-by-options"><option v-for="person in changedByOptions" :key="person" :value="person" /></datalist>
          <details class="create-options"><summary>{{ t('ecn.create.changeCategory') }}</summary><div class="option-group" role="radiogroup" :aria-label="t('ecn.create.changeCategory')"><label v-for="option in changeCategoryOptions" :key="option"><input v-model="createForm.change_category" type="radio" name="ecn-change-category" :value="option" /><span>{{ t(`ecn.create.categories.${option}`) }}</span></label></div><button v-if="createForm.change_category" class="clear-selection" type="button" @click="createForm.change_category = null">{{ t('ecn.create.clearSelection') }}</button></details>
          <details class="create-options"><summary>{{ t('ecn.create.affectedDocument') }}</summary><div class="option-group" role="radiogroup" :aria-label="t('ecn.create.affectedDocument')"><label v-for="option in affectedDocumentOptions" :key="option"><input v-model="createForm.affected_document" type="radio" name="ecn-affected-document" :value="option" /><span>{{ t(`ecn.create.affectedDocuments.${option}`) }}</span></label></div><button v-if="createForm.affected_document" class="clear-selection" type="button" @click="createForm.affected_document = null">{{ t('ecn.create.clearSelection') }}</button></details>
          <details v-if="editRecord" class="create-options"><summary>{{ t('ecn.edit.additionalFields') }}</summary><label v-for="field in additionalEditFields" :key="field" :for="`ecn-edit-${field}`"><span>{{ t(`ecn.edit.fields.${field}`) }}</span><input :id="`ecn-edit-${field}`" v-model.trim="editForm[field]" :maxlength="field === 'approved_by' || field === 'duro_number' ? 120 : 500" /></label></details>
          <p v-if="createError || actionError" class="form-error" role="alert">{{ createError || actionError }}</p>
          <p v-if="creating" class="processing-status" role="status"><RefreshCw class="spinning" :size="16" />{{ createProgress }}</p>
          <div class="dialog-actions">
            <button class="secondary-button" type="button" :disabled="creating || saving" @click="closeFormDialog">{{ t('common.actions.cancel') }}</button>
            <button class="primary-button" type="submit" :disabled="creating || saving || !canSubmitForm">
              <RefreshCw v-if="creating || saving" class="spinning" :size="17" /><Plus v-else-if="!editRecord" :size="17" />
              {{ editRecord ? t('ecn.edit.save') : (creating ? t('ecn.create.creating') : t('ecn.create.submit')) }}
            </button>
          </div>
        </form>
      </section>
    </div>

    <Teleport to="body">
      <div v-if="menuRecord" ref="menuPanel" class="record-menu-panel" :style="menuStyle" role="menu" @mouseenter="cancelMenuClose" @mouseleave="scheduleMenuClose">
        <a v-if="menuRecord.record_url" :href="menuRecord.record_url" target="_blank" rel="noopener noreferrer" role="menuitem" @click="closeMenu">{{ t('ecn.table.open') }}</a>
        <button type="button" role="menuitem" @click="openEditDialog(menuRecord); closeMenu()">{{ t('ecn.table.edit') }}</button>
        <button type="button" role="menuitem" class="danger-action" :disabled="!isLatest(menuRecord)" :title="!isLatest(menuRecord) ? t('ecn.table.lastOnly') : ''" @click="openDeleteDialog(menuRecord); closeMenu()">{{ t('ecn.table.delete') }}</button>
      </div>
    </Teleport>

    <div v-if="deleteRecord" class="dialog-backdrop" @mousedown.self="closeDeleteDialog">
      <section class="dialog" role="dialog" aria-modal="true" aria-labelledby="ecn-delete-title">
        <h2 id="ecn-delete-title">{{ t('ecn.delete.title') }}</h2>
        <p>{{ t('ecn.delete.description', { number: deleteRecord.ecn_number }) }}</p>
        <p v-if="actionError" class="form-error" role="alert">{{ actionError }}</p>
        <p v-if="saving" class="processing-status" role="status"><RefreshCw class="spinning" :size="16" />{{ deleteProgress }}</p>
        <div class="dialog-actions"><button class="secondary-button" type="button" :disabled="saving" @click="closeDeleteDialog">{{ t('common.actions.cancel') }}</button><button class="primary-button danger-button" type="button" :disabled="saving" @click="deleteEcn">{{ t('ecn.table.delete') }}</button></div>
      </section>
    </div>

    <div v-if="monitorSettingsOpen" class="dialog-backdrop" @mousedown.self="monitorSettingsOpen = false">
      <section class="dialog monitor-settings-dialog" role="dialog" aria-modal="true" aria-labelledby="ecn-monitor-settings-title">
        <button class="dialog-close" type="button" :aria-label="t('common.actions.close')" @click="monitorSettingsOpen = false"><X :size="20" /></button>
        <h2 id="ecn-monitor-settings-title">{{ t('ecn.monitor.settingsTitle') }}</h2>
        <p class="dialog-description">{{ t('ecn.monitor.settingsDescription') }}</p>
        <label><span>{{ t('ecn.monitor.frequency') }}</span><input v-model.number="monitorSettings.interval_minutes" type="number" min="5" max="10080" /></label>
        <label class="monitor-checkbox"><input v-model="monitorSettings.enabled" type="checkbox" /><span>{{ t('ecn.monitor.enable') }}</span></label>
        <fieldset class="monitor-scan-items"><legend>{{ t('ecn.monitor.scanItems') }}</legend><label v-for="item in monitorScanItems" :key="item.key" class="monitor-checkbox"><input v-model="monitorSettings.scan_items" type="checkbox" :value="item.key" /><span>{{ t(item.labelKey) }}</span></label></fieldset>
        <p v-if="monitorSettingsError" class="form-error" role="alert">{{ monitorSettingsError }}</p>
        <div class="dialog-actions"><button class="secondary-button" type="button" @click="monitorSettingsOpen = false">{{ t('common.actions.cancel') }}</button><button class="primary-button" type="button" :disabled="monitorSettingsSaving" @click="saveMonitorSettings">{{ monitorSettingsSaving ? t('common.actions.saving') : t('common.actions.save') }}</button></div>
      </section>
    </div>
  </main>
</template>

<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, reactive, ref } from 'vue'
import { ArrowDown, ArrowRight, ArrowUp, CircleCheck, Ellipsis, ExternalLink, FileSpreadsheet, Plus, RefreshCw, Search, TriangleAlert, X } from '@lucide/vue'
import { useI18n } from 'vue-i18n'
import { ecnApi } from '@/scripts/api'
import type { EcnCreatePayload, EcnCreateResponse, EcnMonitorSettings, EcnRecord, EcnRiskScanLog, EcnRiskScanResult, EcnSyncCheckResponse, EcnUpdatePayload } from '@/scripts/types'

const { t } = useI18n()
const activeTable = ref<'eng' | 'ipqc'>('eng')
const activeView = ref<'records' | 'monitor'>('monitor')
const ipqcColumns = [
  { key: 'ecn_number', label: 'ecn.ipqc.columns.number' }, { key: 'product_name', label: 'ecn.ipqc.columns.product' },
  { key: 'issuer', label: 'ecn.ipqc.columns.issuer' }, { key: 'change_date', label: 'ecn.ipqc.columns.date' },
  { key: 'category', label: 'ecn.ipqc.columns.category' }, { key: 'purpose', label: 'ecn.ipqc.columns.purpose' },
  { key: 'handling', label: 'ecn.ipqc.columns.handling' }, { key: 'before_change', label: 'ecn.ipqc.columns.before' },
  { key: 'after_change', label: 'ecn.ipqc.columns.after' }, { key: 'actual_date', label: 'ecn.ipqc.columns.actualDate' },
  { key: 'verify_date', label: 'ecn.ipqc.columns.verifyDate' }, { key: 'status', label: 'ecn.ipqc.columns.status' },
  { key: 'notes', label: 'ecn.ipqc.columns.notes' },
]
const records = ref<EcnRecord[]>([])
const total = ref(0)
const page = ref(1)
const pageInput = ref('1')
const pageSize = 50
const searchDraft = ref('')
const activeSearch = ref('')
const statusFilter = ref('')
const statusOptions = ref<string[]>([])
const sortOrder = ref<'asc' | 'desc'>('desc')
const sourceUrl = ref('https://docs.google.com/spreadsheets/d/1dIRCFaHSGF_15vgGRQMUHLtOZxzcOQFxoTqtlG70RM4/edit?gid=1267645756#gid=1267645756')
const loading = ref(false)
const checkingSync = ref(false)
const syncing = ref(false)
const loadError = ref('')
const syncStatus = ref<EcnSyncCheckResponse | null>(null)
const notice = ref<{ type: 'success' | 'info' | 'error'; message: string } | null>(null)
const createDialogOpen = ref(false)
const creating = ref(false)
const createProgress = ref('')
let createProgressTimer: ReturnType<typeof setInterval> | null = null
const createError = ref('')
const createResult = ref<EcnCreateResponse | null>(null)
const createForm = reactive<EcnCreatePayload>({ ecn_number: '', ecn_title: '', product_model: '', change_item: '', before_change: '', after_change: '', change_date: '', changed_by: '', change_category: null, affected_document: null })
const changeCategoryOptions = ['software', 'material', 'drawing', 'process', 'other'] as const
const affectedDocumentOptions = ['drawing', 'bom', 'sop', 'sip', 'other'] as const
const nextEcnNumber = ref('')
const changedByOptions = ref<string[]>([])
const editRecord = ref<EcnRecord | null>(null)
const editingLoading = ref(false)
const deleteRecord = ref<EcnRecord | null>(null)
const saving = ref(false)
const deleteProgress = ref('')
let deleteProgressTimer: ReturnType<typeof setInterval> | null = null
const actionError = ref('')
const menuRecord = ref<EcnRecord | null>(null)
const menuPanel = ref<HTMLElement | null>(null)
const menuStyle = reactive({ top: '0px', left: '0px' })
let menuTrigger: HTMLElement | null = null
let menuCloseTimer: ReturnType<typeof setTimeout> | null = null
const additionalEditFields = ['before_change', 'after_change', 'approved_by', 'duro_number'] as const
const editForm = reactive<Pick<EcnUpdatePayload, typeof additionalEditFields[number]>>({ before_change: '', after_change: '', approved_by: '', duro_number: '' })

const monitorResults = ref<EcnRiskScanResult[]>([])
const monitorLoading = ref(false)
const monitorRunning = ref(false)
const monitorError = ref('')
const monitorSettingsOpen = ref(false)
const monitorSettingsSaving = ref(false)
const monitorSettingsError = ref('')
const monitorOpen = reactive<Record<string, boolean>>({})
const monitorProgress = ref<string[]>([])
const monitorSettings = reactive<EcnMonitorSettings>({ enabled: false, interval_minutes: 1440, scan_items: [] })
const monitorScanItems = [
  { key: 'sync', labelKey: 'ecn.monitor.scan.sync' },
  { key: 'count', labelKey: 'ecn.monitor.scan.count' },
  { key: 'sequence', labelKey: 'ecn.monitor.scan.sequence' },
  { key: 'missing_ipqc', labelKey: 'ecn.monitor.scan.missingIpqc' },
  { key: 'master_links', labelKey: 'ecn.monitor.scan.masterLinks' },
  { key: 'linked_number', labelKey: 'ecn.monitor.scan.linkedNumber' },
  { key: 'single_choice', labelKey: 'ecn.monitor.scan.singleChoice' },
]
const monitorCategoryLabels: Record<string, string> = {
  sync: 'ecn.monitor.category.sync', count: 'ecn.monitor.category.count', sequence: 'ecn.monitor.category.sequence', missing_ipqc: 'ecn.monitor.category.missingIpqc',
  master_links: 'ecn.monitor.category.masterLinks', linked_number: 'ecn.monitor.category.linkedNumber', single_choice: 'ecn.monitor.category.singleChoice',
}

const totalPages = computed(() => Math.max(1, Math.ceil(total.value / pageSize)))
const normalizedCreateEcnNumber = computed(() => normalizeEcnNumber(createForm.ecn_number))
const productModelOptions = computed(() => [...new Set(records.value.map(record => record.product_name.trim()).filter(Boolean))].sort())
const canSubmitForm = computed(() => Boolean(createForm.ecn_title.trim()) && (editRecord.value !== null || (Boolean(normalizedCreateEcnNumber.value) && Boolean(createForm.product_model.trim()) && Boolean(createForm.change_item.trim()) && Boolean(createForm.change_date) && Boolean(createForm.changed_by.trim()))))
function ipqcValue(record: EcnRecord, key: string): string {
  if (key === 'ecn_number') return record.ecn_number
  if (key === 'product_name') return record.product_name
  if (key === 'before_change') return record.before_change
  if (key === 'after_change') return record.after_change
  if (key === 'change_date') return record.change_date
  return record.extra_fields?.[key] || ''
}
const sortAriaLabel = computed(() => sortOrder.value === 'asc' ? t('ecn.table.sortDescending') : t('ecn.table.sortAscending'))

function errorMessage(error: unknown): string {
  const response = (error as { response?: { data?: { detail?: string; message?: string } } })?.response
  return response?.data?.detail || response?.data?.message || (error instanceof Error ? error.message : t('ecn.loadFailed'))
}
function normalizeEcnNumber(value: string): string {
  const match = value.trim().match(/^ECN[\s_-]*(\d{4,})$/i)
  return match ? `ECN-${match[1]}` : ''
}
function normalizeCreateEcnNumber(): void {
  if (normalizedCreateEcnNumber.value) createForm.ecn_number = normalizedCreateEcnNumber.value
}
function isLatest(record: EcnRecord): boolean {
  const next = Number.parseInt(nextEcnNumber.value.match(/\d+/)?.[0] || '', 10)
  const current = Number.parseInt(record.ecn_number.match(/\d+/)?.[0] || '', 10)
  return Number.isFinite(next) && Number.isFinite(current) && current === next - 1
}
function cancelMenuClose(): void {
  if (menuCloseTimer) clearTimeout(menuCloseTimer)
  menuCloseTimer = null
}
function closeMenu(): void {
  cancelMenuClose()
  menuRecord.value = null
  menuTrigger = null
}
function scheduleMenuClose(): void {
  cancelMenuClose()
  menuCloseTimer = setTimeout(closeMenu, 180)
}
function toggleMenu(record: EcnRecord, event: MouseEvent): void {
  if (menuRecord.value?.id === record.id) { closeMenu(); return }
  cancelMenuClose()
  menuTrigger = event.currentTarget as HTMLElement
  const rect = menuTrigger.getBoundingClientRect()
  const panelWidth = 150
  const panelHeight = 128
  menuStyle.left = `${Math.max(8, Math.min(rect.right - panelWidth, window.innerWidth - panelWidth - 8))}px`
  menuStyle.top = `${rect.bottom + panelHeight + 8 <= window.innerHeight ? rect.bottom + 4 : Math.max(8, rect.top - panelHeight - 4)}px`
  menuRecord.value = record
}
function handleMenuPointerDown(event: PointerEvent): void {
  const target = event.target as Node
  if (menuRecord.value && !menuTrigger?.contains(target) && !menuPanel.value?.contains(target)) closeMenu()
}
function handleMenuFocusIn(event: FocusEvent): void {
  const target = event.target as Node
  if (menuRecord.value && !menuTrigger?.contains(target) && !menuPanel.value?.contains(target)) closeMenu()
}
function handleMenuKeyDown(event: KeyboardEvent): void { if (event.key === 'Escape') closeMenu() }
async function openEditDialog(record: EcnRecord): Promise<void> {
  editRecord.value = record; actionError.value = ''; createError.value = ''; createResult.value = null
  editingLoading.value = true
  try {
    const response = await ecnApi.get(record.id)
    if (editRecord.value?.id !== record.id) return
    record = response.data
    editRecord.value = record
  } catch (error) {
    actionError.value = errorMessage(error)
  } finally {
    editingLoading.value = false
  }
  Object.assign(createForm, {
    ecn_number: record.ecn_number, ecn_title: record.ecn_title, product_model: record.product_name,
    change_item: record.change_item, change_date: dateForInput(record.change_date), changed_by: record.changed_by,
    change_category: record.change_category, affected_document: record.affected_document,
  })
  for (const field of additionalEditFields) editForm[field] = record[field]
}
function dateForInput(value: string): string {
  const yearFirst = /^(\d{4})[./-](\d{1,2})[./-](\d{1,2})$/.exec(value.trim())
  const monthFirst = /^(\d{1,2})\/(\d{1,2})\/(\d{4})$/.exec(value.trim())
  const parts = yearFirst ? [yearFirst[1], yearFirst[2], yearFirst[3]] : monthFirst ? [monthFirst[3], monthFirst[1], monthFirst[2]] : null
  return parts ? `${parts[0]}-${parts[1].padStart(2, '0')}-${parts[2].padStart(2, '0')}` : ''
}
function closeFormDialog(): void { if (!saving.value && !creating.value && !editingLoading.value) { editRecord.value = null; createDialogOpen.value = false } }
function submitForm(): void { if (editRecord.value) void saveEdit(); else void createEcn() }
async function saveEdit(): Promise<void> {
  if (!editRecord.value) return
  saving.value = true; actionError.value = ''
  try {
    const number = editRecord.value.ecn_number
    await ecnApi.update(editRecord.value.id, {
      ecn_title: createForm.ecn_title, product_name: createForm.product_model,
      change_item: createForm.change_item, change_date: createForm.change_date.replaceAll('-', '/'),
      changed_by: createForm.changed_by, change_category: createForm.change_category,
      affected_document: createForm.affected_document, ...editForm,
    })
    editRecord.value = null; notice.value = { type: 'success', message: t('ecn.edit.saved', { number }) }
    await loadRecords()
  } catch (error) { actionError.value = errorMessage(error) } finally { saving.value = false }
}
function openDeleteDialog(record: EcnRecord): void { if (isLatest(record)) { deleteRecord.value = record; actionError.value = '' } }
function closeDeleteDialog(): void { if (!saving.value) deleteRecord.value = null }
async function deleteEcn(): Promise<void> {
  if (!deleteRecord.value) return
  saving.value = true; actionError.value = ''
  const progressSteps = [t('ecn.delete.processing.prepare'), t('ecn.delete.processing.sheet'), t('ecn.delete.processing.folder'), t('ecn.delete.processing.mongodb'), t('ecn.delete.processing.master')]
  let progressIndex = 0
  deleteProgress.value = progressSteps[0]
  deleteProgressTimer = setInterval(() => { progressIndex = (progressIndex + 1) % progressSteps.length; deleteProgress.value = progressSteps[progressIndex] }, 3500)
  try {
    const number = deleteRecord.value.ecn_number
    await ecnApi.remove(deleteRecord.value.id)
    deleteRecord.value = null; notice.value = { type: 'success', message: t('ecn.delete.deleted', { number }) }
    if (page.value > 1 && records.value.length === 1) page.value--
    await loadRecords()
  } catch (error) { actionError.value = errorMessage(error) } finally {
    saving.value = false
    if (deleteProgressTimer) clearInterval(deleteProgressTimer)
    deleteProgressTimer = null
    deleteProgress.value = ''
  }
}
async function loadRecords(): Promise<void> {
  closeMenu(); loading.value = true; loadError.value = ''
  try {
    const response = await ecnApi.list({ table: activeTable.value, search: activeSearch.value || undefined, status: activeTable.value === 'ipqc' ? (statusFilter.value || undefined) : undefined, page: page.value, page_size: pageSize, sort_order: sortOrder.value })
    records.value = response.data.records; total.value = response.data.total; sourceUrl.value = response.data.source_url; nextEcnNumber.value = response.data.next_ecn_number; changedByOptions.value = response.data.changed_by_options; statusOptions.value = response.data.status_options || []
    if (response.data.bootstrapped) notice.value = { type: 'success', message: t('ecn.bootstrapComplete') }
  } catch (error) { loadError.value = errorMessage(error) } finally { loading.value = false }
}
function switchView(view: 'records' | 'monitor'): void {
  if (activeView.value === view) return
  activeView.value = view
  closeMenu()
  if (view === 'monitor') void loadMonitor()
}
function switchTable(table: 'eng' | 'ipqc'): void {
  const wasRecords = activeView.value === 'records'
  activeView.value = 'records'
  if (activeTable.value === table) {
    if (!wasRecords) void loadRecords()
    return
  }
  activeTable.value = table; page.value = 1; pageInput.value = '1'; searchDraft.value = ''; activeSearch.value = ''; statusFilter.value = ''; statusOptions.value = []; syncStatus.value = null; void loadRecords()
}
function applySearch(): void { activeSearch.value = searchDraft.value.trim(); page.value = 1; void loadRecords() }
function applyStatusFilter(): void { page.value = 1; pageInput.value = '1'; void loadRecords() }
function changePage(nextPage: number): void {
  page.value = Math.min(Math.max(1, nextPage), totalPages.value)
  pageInput.value = String(page.value)
  void loadRecords()
}
function jumpToPage(): void {
  const requestedPage = Number.parseInt(pageInput.value, 10)
  if (!Number.isFinite(requestedPage)) { pageInput.value = String(page.value); return }
  changePage(requestedPage)
}
function toggleSortOrder(): void { sortOrder.value = sortOrder.value === 'asc' ? 'desc' : 'asc'; page.value = 1; void loadRecords() }
async function checkSync(): Promise<void> {
  checkingSync.value = true; notice.value = null
  try { syncStatus.value = (await ecnApi.checkSync(activeTable.value)).data }
  catch (error) { notice.value = { type: 'error', message: errorMessage(error) } }
  finally { checkingSync.value = false }
}
async function syncMongo(): Promise<void> {
  syncing.value = true; notice.value = null
  try {
    syncStatus.value = (await ecnApi.sync(activeTable.value)).data
    notice.value = { type: 'success', message: t('ecn.syncComplete') }
    await loadRecords()
  } catch (error) { notice.value = { type: 'error', message: errorMessage(error) } }
  finally { syncing.value = false }
}
function todayInShanghai(): string {
  const parts = new Intl.DateTimeFormat('en-US', { timeZone: 'Asia/Shanghai', year: 'numeric', month: '2-digit', day: '2-digit' }).formatToParts(new Date())
  const value = (type: string) => parts.find(part => part.type === type)?.value || ''
  return `${value('year')}-${value('month')}-${value('day')}`
}
function openCreateDialog(): void { createForm.ecn_number = nextEcnNumber.value; createForm.product_model = ''; createForm.ecn_title = ''; createForm.change_item = ''; createForm.before_change = ''; createForm.after_change = ''; createForm.change_date = todayInShanghai(); createForm.changed_by = ''; createForm.change_category = null; createForm.affected_document = null; createError.value = ''; createResult.value = null; createDialogOpen.value = true }
async function createEcn(): Promise<void> {
  if (!canSubmitForm.value) return
  normalizeCreateEcnNumber()
  creating.value = true; createError.value = ''; createProgress.value = t('ecn.create.processing.prepare')
  const progressSteps = [t('ecn.create.processing.prepare'), t('ecn.create.processing.folder'), t('ecn.create.processing.sheet'), t('ecn.create.processing.master'), t('ecn.create.processing.save')]
  let progressIndex = 0
  createProgressTimer = setInterval(() => {
    progressIndex = (progressIndex + 1) % progressSteps.length
    createProgress.value = progressSteps[progressIndex]
  }, 4000)
  try {
    const response = await ecnApi.create({ ...createForm }, activeTable.value); createResult.value = response.data
    notice.value = { type: 'success', message: t('ecn.create.createdNotice', { number: response.data.record.ecn_number }) }
    searchDraft.value = ''; activeSearch.value = ''; sortOrder.value = 'desc'; page.value = 1; pageInput.value = '1'; await loadRecords()
  } catch (error) { createError.value = errorMessage(error) } finally {
    creating.value = false
    if (createProgressTimer) clearInterval(createProgressTimer)
    createProgressTimer = null
    createProgress.value = ''
  }
}
function formatMonitorDate(value: string): string {
  return new Date(value).toLocaleString('zh-CN', { hour12: false })
}
function monitorLogs(result: EcnRiskScanResult): EcnRiskScanLog[] {
  if (result.process_logs?.length) {
    // Older persisted results marked the initial event as running forever.
    // A stored scan is already finished, so normalize that stale state.
    return result.process_logs.map(log => log.status === 'running' ? { ...log, status: 'success', message: `${t('ecn.monitor.completed')}：${log.title}` } : log)
  }
  return result.process.map((message, index) => ({ at: result.scanned_at, step: `legacy-${index}`, title: t('ecn.monitor.legacyLog'), status: 'info', message, issues: [], details: {} }))
}
function monitorChecklist(result: EcnRiskScanResult): Array<{ key: string; labelKey: string; status: string; message: string }> {
  const logs = monitorLogs(result)
  return monitorScanItems.map(item => {
    if (!result.selected_items.includes(item.key)) {
      return { ...item, status: 'info', message: t('ecn.monitor.notSelected') }
    }
    const matches = logs.filter(log => log.step === item.key)
    const alert = matches.find(log => log.status === 'warning' || log.status === 'error')
    const completed = matches.find(log => log.status === 'success')
    return {
      ...item,
      status: alert?.status || (completed ? 'success' : 'info'),
      message: alert?.message || completed?.message || t('ecn.monitor.notExecuted'),
    }
  })
}
function monitorAlertGroups(result: EcnRiskScanResult): Array<{ category: string; count: number; details: Record<string, any>[] }> {
  const source = new Map(result.categories.map(group => [group.category, group]))
  const syncLogs = monitorLogs(result).filter(log => log.step === 'sync' && (log.status === 'warning' || log.status === 'error'))
  const syncCount = result.sync_records.reduce((total, item) => total + Number(item.missing || 0) + Number(item.extra || 0) + Number(item.changed || 0), 0)
  const groups = Object.keys(monitorCategoryLabels).map(category => {
    if (category === 'sync') {
      return { category, count: syncCount || (syncLogs.length ? 1 : 0), details: syncLogs.map(log => ({ message: log.message })) }
    }
    const group = source.get(category)
    return { category, count: group?.count || 0, details: group?.details || [] }
  })
  for (const group of result.categories) {
    if (!monitorCategoryLabels[group.category]) groups.push(group)
  }
  return groups
}
function monitorLogIssues(log: NonNullable<EcnRiskScanResult['process_logs']>[number]): Record<string, any>[] {
  return log.issues || []
}
function monitorRecordNumbers(records?: Record<string, any>[]): string {
  return (records || []).map(record => record.ecn_number || record.form_number || `row ${record.source_row || '?'}`).join(', ')
}
function toggleMonitorDay(id: string): void { monitorOpen[id] = !monitorOpen[id] }
async function loadMonitor(): Promise<void> {
  monitorLoading.value = true
  monitorError.value = ''
  try {
    const [results, settings] = await Promise.all([ecnApi.getMonitorResults(), ecnApi.getMonitorSettings()])
    monitorResults.value = results.data
    Object.assign(monitorSettings, settings.data)
    if (!monitorSettings.scan_items.length) monitorSettings.scan_items = monitorScanItems.map(item => item.key)
    monitorResults.value.forEach(result => { monitorOpen[result.id] = false })
  } catch (error) { monitorError.value = errorMessage(error) } finally { monitorLoading.value = false }
}
async function runMonitorScan(): Promise<void> {
  monitorRunning.value = true
  monitorError.value = ''
  monitorProgress.value = [t('ecn.monitor.checkingSync'), t('ecn.monitor.runningChecks')]
  try {
    const result = (await ecnApi.runMonitorScan(monitorSettings.scan_items)).data
    monitorResults.value = [result, ...monitorResults.value]
    monitorOpen[result.id] = false
  } catch (error) { monitorError.value = errorMessage(error) } finally { monitorRunning.value = false }
}
async function saveMonitorSettings(): Promise<void> {
  monitorSettingsSaving.value = true
  monitorSettingsError.value = ''
  try {
    Object.assign(monitorSettings, (await ecnApi.saveMonitorSettings(monitorSettings)).data)
    monitorSettingsOpen.value = false
  } catch (error) { monitorSettingsError.value = errorMessage(error) } finally { monitorSettingsSaving.value = false }
}
onMounted(() => {
  document.addEventListener('pointerdown', handleMenuPointerDown)
  document.addEventListener('focusin', handleMenuFocusIn)
  document.addEventListener('keydown', handleMenuKeyDown)
  window.addEventListener('scroll', closeMenu, true)
  void loadMonitor()
})
onBeforeUnmount(() => {
  if (createProgressTimer) clearInterval(createProgressTimer)
  createProgressTimer = null
  if (deleteProgressTimer) clearInterval(deleteProgressTimer)
  deleteProgressTimer = null
  closeMenu()
  document.removeEventListener('pointerdown', handleMenuPointerDown)
  document.removeEventListener('focusin', handleMenuFocusIn)
  document.removeEventListener('keydown', handleMenuKeyDown)
  window.removeEventListener('scroll', closeMenu, true)
})
</script>

<style scoped>
.record-menu-trigger{display:grid;width:34px;height:34px;place-items:center;cursor:pointer;border:1px solid #ced7de;border-radius:7px;background:#fff;color:#405365}.record-menu-trigger svg{transform:rotate(90deg)}.record-menu-panel{position:fixed;z-index:900;display:flex;width:150px;flex-direction:column;padding:5px;border:1px solid #dce3e9;border-radius:9px;background:#fff;box-shadow:0 10px 24px rgba(25,39,52,.15)}.record-menu-panel a,.record-menu-panel button{display:block;width:100%;padding:9px 10px;border:0;border-radius:6px;background:transparent;color:#344454;text-align:left;text-decoration:none;cursor:pointer}.record-menu-panel a:hover,.record-menu-panel button:hover{background:#f1f5f8}.record-menu-panel .danger-action{color:#b42318}.record-menu-panel button:disabled{color:#9aa5af;cursor:not-allowed}.create-options{margin-top:18px;border:1px solid #dce3e9;border-radius:9px;padding:10px 12px}.create-options summary{cursor:pointer;color:#334453;font-size:13px;font-weight:800}.option-group{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:8px;margin-top:12px}.dialog .option-group label{display:flex;align-items:center;gap:8px;margin:0;padding:8px;border:1px solid #e4e9ed;border-radius:7px;cursor:pointer}.dialog .option-group input{width:16px;height:16px;flex:none;margin:0}.dialog .option-group label>span{display:inline;margin:0;font-weight:500}.clear-selection{margin-top:10px;padding:5px 0;border:0;background:transparent;color:#52606d;cursor:pointer}.create-dialog{box-sizing:border-box;max-height:min(800px,calc(100dvh - 40px));overflow-y:auto;overscroll-behavior:contain}.edit-dialog{max-height:min(86vh,850px);overflow-y:auto}.danger-button{border-color:#b42318;background:#b42318}
.ecn-page{min-height:100%;padding:32px 42px 56px;color:#1f2933;background:#f4f6f8}.ecn-shell{width:min(1540px,100%);margin:0 auto}.back-link{display:inline-flex;align-items:center;gap:7px;margin-bottom:24px;color:#52606d;font-size:14px;text-decoration:none}.back-link:hover{color:#111827}.page-heading{display:flex;align-items:flex-end;justify-content:space-between;gap:28px;margin-bottom:24px}.eyebrow{margin:0 0 7px;color:#52606d;font-size:12px;font-weight:800;letter-spacing:.12em;text-transform:uppercase}h1{margin:0;color:#111827;font-size:clamp(30px,4vw,44px);letter-spacing:-.04em}.introduction{max-width:720px;margin:10px 0 0;color:#66788a;line-height:1.6}.heading-actions,.dialog-actions,.result-links{display:flex;align-items:center;gap:10px}button,a{font:inherit}.primary-button,.secondary-button{display:inline-flex;min-height:40px;align-items:center;justify-content:center;gap:8px;padding:0 15px;border-radius:9px;font-weight:700;text-decoration:none;cursor:pointer}.primary-button{border:1px solid #111827;color:#fff;background:#111827}.secondary-button{border:1px solid #cbd5df;color:#344454;background:#fff}button:disabled{cursor:not-allowed;opacity:.55}.summary-grid{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:14px;margin-bottom:18px}.summary-card{display:flex;align-items:center;gap:13px;min-height:86px;padding:18px 20px;border:1px solid #dce3e9;border-radius:12px;background:#fff}.summary-card>svg{color:#647586}.summary-card div{display:flex;flex-direction:column;gap:3px}.summary-card strong{color:#17212b;font-size:21px}.summary-card span{color:#738190;font-size:13px}.summary-card.is-success{border-color:#a8d9bf;background:#f2fbf6}.summary-card.is-success>svg{color:#16834d}.summary-card.is-warning{border-color:#f0cc83;background:#fffaf0}.summary-card.is-warning>svg{color:#b87400}.notice{margin:0 0 16px;padding:11px 14px;border-radius:9px;font-size:14px}.notice.is-success{color:#12633b;background:#eaf8f0}.notice.is-error{color:#a02323;background:#fff0f0}.notice.is-info{color:#315a77;background:#edf6fb}.sync-panel{display:flex;align-items:center;justify-content:space-between;gap:20px;margin-bottom:18px;padding:15px 18px;border:1px solid #efc66e;border-radius:11px;background:#fffbef}.sync-panel.is-synced{border-color:#9dd5b7;background:#f0faf5}.sync-panel p{margin:4px 0 0;color:#66788a;font-size:13px}.difference-counts{display:flex;gap:8px;flex-wrap:wrap}.difference-counts span{padding:5px 9px;border-radius:999px;color:#855400;background:#fff1c9;font-size:12px;font-weight:700}.records-card{overflow:hidden;border:1px solid #dce3e9;border-radius:13px;background:#fff;box-shadow:0 10px 30px rgba(25,39,52,.04)}.records-toolbar{display:flex;align-items:center;justify-content:space-between;gap:20px;padding:20px 22px;border-bottom:1px solid #e6ebef}.records-toolbar h2{margin:0;font-size:20px}.records-toolbar p{margin:5px 0 0;color:#788694;font-size:13px}.search-form{display:flex;align-items:center;width:min(420px,100%);padding-left:12px;border:1px solid #ccd6de;border-radius:9px;background:#fff}.search-form svg{color:#7b8996}.search-form input{min-width:0;flex:1;height:39px;padding:0 10px;border:0;outline:0}.search-form button{align-self:stretch;padding:0 14px;border:0;border-left:1px solid #d8e0e6;color:#33475b;background:#f7f9fa;cursor:pointer}.table-scroll{max-width:100%;max-height:min(70vh,760px);overflow:auto;overscroll-behavior:contain}table{width:max-content;min-width:100%;border-collapse:collapse}th{position:sticky;top:0;z-index:1;padding:11px 14px;color:#62717f;background:#f7f9fa;font-size:12px;font-weight:800;text-align:left;text-transform:uppercase;white-space:nowrap}td{padding:14px;border-top:1px solid #edf0f3;color:#354556;font-size:13px;vertical-align:middle;white-space:normal;overflow-wrap:anywhere;word-break:break-word}tbody tr:hover{background:#fafcfd}.record-identity{min-width:230px}.record-identity strong,.record-identity span,td .subtext{display:block}.record-identity strong{color:#14212d;font-family:ui-monospace,SFMono-Regular,Menlo,monospace}.record-identity span{margin-top:4px;color:#687887}.record-identity small{display:inline-block;margin-top:6px;padding:2px 6px;border-radius:5px;color:#305f83;background:#eaf4fb}.wide-cell{min-width:210px;white-space:normal}.revision{display:inline-block;max-width:100px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;vertical-align:middle}td .subtext{margin-top:4px;color:#7b8996}.open-record{display:inline-flex;width:34px;height:34px;align-items:center;justify-content:center;border-radius:8px;color:#2d647f;background:#edf6fa}.state-box{display:flex;min-height:260px;flex-direction:column;align-items:center;justify-content:center;gap:10px;color:#748391}.state-box.is-error{color:#a23838}.state-box button{padding:7px 12px;border:1px solid currentColor;border-radius:7px;color:inherit;background:transparent;cursor:pointer}.pagination{display:flex;align-items:center;justify-content:space-between;gap:16px;padding:15px 20px;border-top:1px solid #e6ebef;color:#687887;font-size:13px}.pagination>div{display:flex;align-items:center;gap:12px}.pagination button{padding:6px 10px;border:1px solid #ced7de;border-radius:7px;color:#405365;background:#fff;cursor:pointer}.page-jump{display:flex;align-items:center;gap:6px;margin-left:4px}.page-jump input{box-sizing:border-box;width:64px;height:31px;padding:0 7px;border:1px solid #ced7de;border-radius:7px;color:#405365;background:#fff}.dialog-backdrop{position:fixed;z-index:1000;inset:0;display:grid;place-items:center;padding:20px;background:rgba(15,23,31,.48);backdrop-filter:blur(3px)}.dialog{position:relative;width:min(520px,100%);padding:28px;border-radius:16px;background:#fff;box-shadow:0 24px 70px rgba(0,0,0,.24)}.dialog h2{margin:0;color:#15212c;font-size:25px}.dialog-description,.dialog>p{margin:9px 0 22px;color:#6b7b89;line-height:1.55}.dialog-close{position:absolute;top:17px;right:17px;display:grid;width:34px;height:34px;place-items:center;border:0;border-radius:8px;color:#677785;background:#f1f4f6;cursor:pointer}.dialog label{display:block;margin-top:18px}.dialog label>span{display:block;margin-bottom:7px;color:#334453;font-size:13px;font-weight:800}.dialog input{box-sizing:border-box;width:100%;height:44px;padding:0 12px;border:1px solid #cbd6df;border-radius:9px;outline:none}.dialog input:focus{border-color:#527b96;box-shadow:0 0 0 3px rgba(82,123,150,.12)}.dialog label small{display:block;margin-top:6px;color:#8995a0}.dialog-actions{justify-content:flex-end;margin-top:24px}.form-error{margin:16px 0 0;padding:10px 12px;border-radius:8px;color:#a32d2d;background:#fff0f0}.success-icon{display:grid;width:54px;height:54px;place-items:center;margin-bottom:16px;border-radius:50%;color:#13824a;background:#e7f7ee}.result-links{margin:20px 0}.result-links a{display:inline-flex;align-items:center;gap:5px;color:#285f7b}.full-width{width:100%}.spinning{animation:spin .8s linear infinite}.sr-only{position:absolute;width:1px;height:1px;padding:0;margin:-1px;overflow:hidden;clip:rect(0,0,0,0);white-space:nowrap;border:0}@keyframes spin{to{transform:rotate(360deg)}}@media(max-width:980px){.page-heading,.records-toolbar{align-items:stretch;flex-direction:column}.heading-actions{flex-wrap:wrap}.summary-grid{grid-template-columns:1fr}.search-form{width:100%}.pagination>div{flex-wrap:wrap}}@media(max-width:640px){.ecn-page{padding:22px 16px 40px}.heading-actions>*{flex:1 1 100%}.pagination{align-items:flex-start;flex-direction:column}.dialog{padding:24px 20px}.result-links{align-items:flex-start;flex-direction:column}}
.sort-button{display:inline-flex;align-items:center;gap:6px;padding:0;border:0;color:inherit;background:transparent;font:inherit;text-transform:inherit;cursor:pointer}.sort-button:hover{color:#182b3b}
.processing-status{display:flex;align-items:center;gap:8px;margin:16px 0 0;padding:10px 12px;border-radius:8px;color:#315a77;background:#edf6fb}
.ecn-tabs{display:flex;gap:4px;margin:0 0 18px;padding:4px;border:1px solid #dce3e9;border-radius:10px;background:#fff;width:max-content}.ecn-tabs button{min-width:100px;padding:9px 18px;border:0;border-radius:7px;color:#62717f;background:transparent;font-weight:800;cursor:pointer}.ecn-tabs button.is-active{color:#fff;background:#111827}
.monitor-panel{overflow:hidden;border:1px solid #dce3e9;border-radius:13px;background:#fff;box-shadow:0 10px 30px rgba(25,39,52,.04)}.monitor-toolbar{border-bottom:1px solid #e6ebef}.monitor-progress{display:flex;align-items:center;gap:12px;margin:16px 20px;padding:11px 13px;border-radius:9px;color:#315a77;background:#edf6fb}.monitor-progress span+span{padding-left:12px;border-left:1px solid #cbdde8}.monitor-day{border-top:1px solid #e6ebef}.monitor-day-header{display:flex;width:100%;align-items:center;justify-content:space-between;gap:16px;padding:17px 22px;border:0;color:#1f2933;background:#fff;text-align:left;cursor:pointer}.monitor-day-header:hover{background:#fafcfd}.monitor-day-header strong,.monitor-day-header small{display:block}.monitor-day-header small{margin-top:5px;color:#788694;font-size:13px}.monitor-summary{display:flex;align-items:center;gap:9px;color:#687887;font-size:13px}.monitor-summary b{color:#16834d;font-size:21px}.monitor-summary b.has-alerts{color:#b42318}.monitor-day-body{padding:0 22px 20px}.monitor-process{margin-bottom:12px;padding:11px 13px;border-radius:9px;background:#f7f9fa}.monitor-process summary{color:#52606d;font-size:13px;font-weight:700;cursor:pointer}.monitor-process p{margin:7px 0 0;color:#788694;font-size:13px}.monitor-ok{display:flex;align-items:center;gap:8px;padding:13px 0;color:#16834d;font-size:14px}.monitor-alert-group{border-top:1px solid #edf0f3;padding:13px 0}.monitor-alert-group summary{display:flex;align-items:center;justify-content:space-between;color:#344454;font-weight:800;cursor:pointer}.monitor-alert-group summary b{color:#b42318}.monitor-alert-row{display:grid;grid-template-columns:minmax(110px,180px) 1fr;gap:16px;padding:10px 8px;color:#52606d;font-size:13px}.monitor-alert-row strong{color:#1f2933;overflow-wrap:anywhere}.monitor-settings-dialog{max-height:min(800px,calc(100dvh - 40px));overflow-y:auto}.monitor-settings-dialog fieldset{margin-top:18px;border:1px solid #dce3e9;border-radius:9px;padding:12px}.monitor-settings-dialog legend{padding:0 5px;color:#334453;font-size:13px;font-weight:800}.monitor-scan-items{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:9px}.monitor-checkbox{display:flex!important;align-items:center;gap:8px;margin:0!important;padding:8px;border:1px solid #e4e9ed;border-radius:7px;cursor:pointer}.monitor-checkbox input{width:16px!important;height:16px!important;flex:none}.monitor-checkbox span{display:inline!important;margin:0!important;font-weight:500!important}
.monitor-log-list{display:grid;gap:8px;margin-top:12px}.monitor-log{padding:11px 12px;border-left:3px solid #9aa8b4;border-radius:7px;background:#fff}.monitor-log.is-running{border-color:#527b96;background:#f2f7fa}.monitor-log.is-success{border-color:#16834d;background:#f2fbf6}.monitor-log.is-warning{border-color:#b87400;background:#fffaf0}.monitor-log.is-error{border-color:#b42318;background:#fff4f4}.monitor-log header{display:flex;align-items:center;gap:9px}.monitor-log header strong{color:#243442;font-size:13px}.monitor-log header time{margin-left:auto;color:#8995a0;font-size:11px}.monitor-log-status{padding:2px 6px;border-radius:999px;color:#52606d;background:#edf0f3;font-size:11px;font-weight:800}.monitor-log.is-success .monitor-log-status{color:#16834d;background:#dff4e8}.monitor-log.is-warning .monitor-log-status{color:#855400;background:#ffedbb}.monitor-log.is-error .monitor-log-status{color:#a02323;background:#ffe0e0}.monitor-log p{margin:6px 0 0;color:#52606d;font-size:13px;line-height:1.5}.monitor-log>small{display:block;margin-top:6px;color:#8995a0}.monitor-log-issues{margin:7px 0 0;padding-left:20px;color:#8d2f2f;font-size:12px;line-height:1.55}.monitor-log-data{margin-top:7px;color:#52606d;font-size:12px;overflow-wrap:anywhere}.monitor-log-data b{margin-right:6px;color:#344454}
.monitor-alert-group summary>svg{flex:none}.monitor-alert-group.is-safe summary>svg{color:#16834d}.monitor-alert-group.is-alert summary>svg{color:#b42318}.monitor-alert-group.is-safe summary b{color:#16834d}.monitor-alert-group.is-alert summary b{color:#b42318}
.monitor-checklist{display:grid;gap:7px;margin-top:12px}.monitor-check-item{display:flex;align-items:flex-start;gap:9px;padding:9px 10px;border:1px solid #dce3e9;border-radius:8px;background:#fff}.monitor-check-item>svg{flex:none;margin-top:1px;color:#8995a0}.monitor-check-item.is-success{border-color:#a8d9bf;background:#f2fbf6}.monitor-check-item.is-success>svg{color:#16834d}.monitor-check-item.is-warning,.monitor-check-item.is-error{border-color:#efc3c3;background:#fff5f5}.monitor-check-item.is-warning>svg,.monitor-check-item.is-error>svg{color:#b42318}.monitor-check-dash{width:18px;flex:none;color:#8995a0;font-weight:800;text-align:center}.monitor-check-item strong,.monitor-check-item small{display:block}.monitor-check-item strong{color:#344454;font-size:13px}.monitor-check-item small{margin-top:3px;color:#687887;font-size:12px;line-height:1.45}.monitor-log-details{margin-top:8px;border-top:1px solid #edf0f3;padding-top:7px}.monitor-log-details summary{color:#52606d;font-size:12px;font-weight:700;cursor:pointer}.monitor-log-details .monitor-log-issues{margin-top:6px}.monitor-log-details .monitor-log-data{margin-top:6px}
.monitor-alert-group summary{justify-content:flex-start;gap:8px;font-size:13px;font-weight:500}.monitor-alert-group summary b{margin-left:auto;font-size:13px;font-weight:600}.monitor-check-item strong{font-size:13px;font-weight:500}.monitor-check-item small{font-size:12px}.monitor-alert-row{font-size:11px}.monitor-alert-row strong{font-size:11px}.monitor-log-data{font-size:11px}

/* Keep column widths stable while allowing the table to scroll as one unit. */
table {
  width: max-content;
  min-width: 100%;
  table-layout: fixed;
}
table th,
table td {
  box-sizing: border-box;
  min-width: 0;
  overflow-wrap: anywhere;
  word-break: break-word;
  white-space: normal;
}
.ipqc-table th:nth-child(1), .ipqc-table td:nth-child(1) { width: 120px; }
.ipqc-table th:nth-child(2), .ipqc-table td:nth-child(2) { width: 150px; }
.ipqc-table th:nth-child(3), .ipqc-table td:nth-child(3) { width: 120px; }
.ipqc-table th:nth-child(4), .ipqc-table td:nth-child(4) { width: 110px; }
.ipqc-table th:nth-child(5), .ipqc-table td:nth-child(5) { width: 120px; }
.ipqc-table th:nth-child(6), .ipqc-table td:nth-child(6) { width: 180px; }
.ipqc-table th:nth-child(7), .ipqc-table td:nth-child(7) { width: 180px; }
.ipqc-table th:nth-child(8), .ipqc-table td:nth-child(8) { width: 260px; }
.ipqc-table th:nth-child(9), .ipqc-table td:nth-child(9) { width: 260px; }
.ipqc-table th:nth-child(10), .ipqc-table td:nth-child(10) { width: 110px; }
.ipqc-table th:nth-child(11), .ipqc-table td:nth-child(11) { width: 110px; }
.ipqc-table th:nth-child(12), .ipqc-table td:nth-child(12) { width: 100px; }
.ipqc-table th:nth-child(13), .ipqc-table td:nth-child(13) { width: 180px; }
.ipqc-table th:nth-child(14), .ipqc-table td:nth-child(14) { width: 70px; }
table:not(.ipqc-table) th:nth-child(1), table:not(.ipqc-table) td:nth-child(1) { width: 230px; }
table:not(.ipqc-table) th:nth-child(2), table:not(.ipqc-table) td:nth-child(2) { width: 150px; }
table:not(.ipqc-table) th:nth-child(3), table:not(.ipqc-table) td:nth-child(3) { width: 240px; }
table:not(.ipqc-table) th:nth-child(4), table:not(.ipqc-table) td:nth-child(4) { width: 260px; }
table:not(.ipqc-table) th:nth-child(5), table:not(.ipqc-table) td:nth-child(5) { width: 120px; }
table:not(.ipqc-table) th:nth-child(6), table:not(.ipqc-table) td:nth-child(6) { width: 140px; }
table:not(.ipqc-table) th:nth-child(7), table:not(.ipqc-table) td:nth-child(7) { width: 80px; }

.ecn-title-row { display: flex; align-items: center; gap: 12px; }
.ecn-title-row img { width: 42px; height: 42px; border-radius: 11px; }
.ecn-title-row h1 { font-weight: 650; letter-spacing: -.03em; }

.status-header { display: inline-flex; align-items: center; gap: 6px; }
.status-header select { max-width: 120px; padding: 3px 5px; border: 1px solid #cbd5df; border-radius: 5px; color: #405365; background: #fff; font-size: 11px; font-weight: 600; text-transform: none; }
.sync-now-button { min-height: 32px; padding: 0 11px; border-radius: 7px; font-size: 12px; }
</style>
