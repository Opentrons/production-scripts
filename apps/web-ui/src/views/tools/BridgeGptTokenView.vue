<template>
  <main class="bridge-token-page">
    <header class="bridge-token-header">
      <a class="back-link" href="/">
        <ArrowLeft :size="17" aria-hidden="true" />
        <span>{{ t('bridgeTokens.back') }}</span>
      </a>
      <div class="header-actions">
        <LocaleSwitcher variant="surface" />
        <AuthUserMenu />
      </div>
    </header>

    <div class="bridge-token-content">
      <section class="page-heading" aria-labelledby="bridge-token-title">
        <div>
          <p class="eyebrow">{{ t('bridgeTokens.eyebrow') }}</p>
          <h1 id="bridge-token-title">{{ t('bridgeTokens.title') }}</h1>
          <div class="live-meta">
            <span class="live-state" :class="{ 'is-live': balance?.live }">
              <Wifi v-if="balance?.live" :size="14" aria-hidden="true" />
              <Database v-else :size="14" aria-hidden="true" />
              {{ balance?.live ? t('bridgeTokens.live') : t('bridgeTokens.cached') }}
            </span>
            <span>
              {{ balance?.refreshed_at
                ? t('bridgeTokens.updated', { time: formatDate(balance.refreshed_at) })
                : t('bridgeTokens.notUpdated') }}
            </span>
          </div>
        </div>
        <div class="heading-actions">
          <button
            v-if="canEditConfiguration"
            class="icon-button"
            type="button"
            :disabled="configurationLoading"
            :title="t('bridgeTokens.configuration.edit')"
            :aria-label="t('bridgeTokens.configuration.edit')"
            @click="openConfiguration"
          >
            <Pencil :size="18" aria-hidden="true" />
          </button>
          <button
            class="icon-button"
            type="button"
            :disabled="refreshing"
            :title="refreshing ? t('bridgeTokens.refreshing') : t('bridgeTokens.refresh')"
            :aria-label="refreshing ? t('bridgeTokens.refreshing') : t('bridgeTokens.refresh')"
            @click="refreshAll"
          >
            <RefreshCw :size="19" :class="{ 'is-spinning': refreshing }" aria-hidden="true" />
          </button>
        </div>
      </section>

      <div v-if="initialLoading" class="loading-shell" aria-live="polite">
        <span class="loading-line is-wide"></span>
        <span class="loading-line"></span>
        <span class="loading-line is-short"></span>
      </div>

      <section v-else-if="stateTitle" class="state-panel" role="status">
        <CircleAlert :size="24" aria-hidden="true" />
        <div>
          <h2>{{ stateTitle }}</h2>
          <p>{{ stateBody }}</p>
        </div>
      </section>

      <template v-else-if="balance">
        <p v-if="balance.error" class="inline-notice" role="status">
          <CircleAlert :size="16" aria-hidden="true" />
          {{ t('bridgeTokens.states.balanceFailed') }}
        </p>

        <section class="balance-panel" aria-labelledby="balance-heading">
          <div class="balance-primary">
            <span id="balance-heading">{{ t('bridgeTokens.balance') }}</span>
            <strong>{{ formatTokens(balance.total_remaining) }}</strong>
            <small>token</small>
          </div>
          <div class="balance-metrics">
            <div>
              <span>{{ t('bridgeTokens.quota') }}</span>
              <strong>{{ formatTokens(balance.total_quota) }}</strong>
            </div>
            <div>
              <span>{{ t('bridgeTokens.used') }}</span>
              <strong>{{ formatTokens(balance.total_used) }}</strong>
            </div>
            <div>
              <span>{{ t('bridgeTokens.utilization') }}</span>
              <strong>{{ utilization }}%</strong>
            </div>
          </div>
          <div class="utilization-track" aria-hidden="true">
            <span :style="{ width: `${utilization}%` }"></span>
          </div>
        </section>

        <nav class="bridge-token-tabs" :aria-label="t('bridgeTokens.sections')" role="tablist">
          <button
            id="balance-tab"
            type="button"
            role="tab"
            :aria-selected="activeTab === 'balance'"
            aria-controls="balance-tab-panel"
            :class="{ 'is-active': activeTab === 'balance' }"
            @click="activeTab = 'balance'"
          >
            {{ t('bridgeTokens.keyBalances') }}
          </button>
          <button
            id="records-tab"
            type="button"
            role="tab"
            :aria-selected="activeTab === 'records'"
            aria-controls="records-tab-panel"
            :class="{ 'is-active': activeTab === 'records' }"
            @click="activeTab = 'records'"
          >
            <span>{{ t('bridgeTokens.records') }}</span>
            <span class="tab-count">{{ t('bridgeTokens.recordCount', { count: recordPage.total }) }}</span>
          </button>
        </nav>

        <div
          v-if="activeTab === 'balance'"
          id="balance-tab-panel"
          class="tab-panel"
          role="tabpanel"
          aria-labelledby="balance-tab"
        >
          <section class="key-section" :aria-label="t('bridgeTokens.keyBalances')">
            <div class="key-table" role="table">
              <div class="key-table-head" role="row">
                <span role="columnheader">{{ t('bridgeTokens.key') }}</span>
                <span role="columnheader">{{ t('bridgeTokens.email') }}</span>
                <span role="columnheader">{{ t('bridgeTokens.status') }}</span>
                <span role="columnheader">{{ t('bridgeTokens.quota') }}</span>
                <span role="columnheader">{{ t('bridgeTokens.used') }}</span>
                <span role="columnheader">{{ t('bridgeTokens.remaining') }}</span>
              </div>
              <div v-for="key in balance.keys" :key="key.key_id" class="key-table-row" role="row">
                <strong role="cell">{{ key.key_name }}</strong>
                <span role="cell">{{ key.email_hint || '—' }}</span>
                <span role="cell">
                  <i class="status-pill" :class="statusClass(key.status)">
                    {{ statusLabel(key.status) }}
                  </i>
                </span>
                <span role="cell">{{ formatTokens(key.quota) }}</span>
                <span role="cell">{{ formatTokens(key.quota_used) }}</span>
                <strong class="remaining-cell" role="cell">{{ formatTokens(key.remaining) }}</strong>
              </div>
              <div class="table-footer" role="row">
                <span role="cell">{{ t('bridgeTokens.recordCount', { count: balance.keys.length }) }}</span>
              </div>
            </div>
          </section>
        </div>

        <div
          v-else
          id="records-tab-panel"
          class="tab-panel"
          role="tabpanel"
          aria-labelledby="records-tab"
        >
          <section class="records-section" :aria-label="t('bridgeTokens.records')">
            <div class="records-toolbar">
              <label class="action-filter">
                <span class="sr-only">{{ t('bridgeTokens.table.action') }}</span>
                <select v-model="selectedAction">
                  <option value="">{{ t('bridgeTokens.allActions') }}</option>
                  <option v-for="action in actionOptions" :key="action" :value="action">
                    {{ actionLabel(action) }}
                  </option>
                </select>
              </label>
            </div>

            <p v-if="recordsError" class="inline-notice is-error" role="alert">
              <CircleAlert :size="16" aria-hidden="true" />
              {{ t('bridgeTokens.states.recordsFailed') }}
            </p>

            <div v-if="recordsLoading" class="records-loading" aria-live="polite">
              <RefreshCw :size="18" class="is-spinning" aria-hidden="true" />
            </div>
            <div v-else-if="!recordPage.records.length" class="empty-records">
              <History :size="21" aria-hidden="true" />
              <span>{{ t('bridgeTokens.noRecords') }}</span>
            </div>
            <div v-else class="records-table-wrap">
              <table class="records-table">
                <thead>
                  <tr>
                    <th>{{ t('bridgeTokens.table.time') }}</th>
                    <th>{{ t('bridgeTokens.key') }}</th>
                    <th>{{ t('bridgeTokens.table.action') }}</th>
                    <th>{{ t('bridgeTokens.table.amount') }}</th>
                    <th>{{ t('bridgeTokens.table.quota') }}</th>
                    <th>{{ t('bridgeTokens.table.remaining') }}</th>
                    <th>{{ t('bridgeTokens.table.result') }}</th>
                  </tr>
                </thead>
                <tbody>
                  <tr v-for="record in recordPage.records" :key="record.id">
                    <td>{{ formatDate(record.created_at) }}</td>
                    <td><strong>{{ record.key_name }}</strong></td>
                    <td>{{ actionLabel(record.action) }}</td>
                    <td :class="amountClass(record.amount)">{{ formatAmount(record) }}</td>
                    <td>{{ formatTokens(record.quota_after) }}</td>
                    <td>{{ formatTokens(record.remaining_after) }}</td>
                    <td>
                      <span class="result-state" :class="record.success ? 'is-success' : 'is-failed'">
                        <CheckCircle v-if="record.success" :size="14" aria-hidden="true" />
                        <XCircle v-else :size="14" aria-hidden="true" />
                        {{ record.success ? t('bridgeTokens.success') : t('bridgeTokens.failed') }}
                      </span>
                    </td>
                  </tr>
                </tbody>
                <tfoot>
                  <tr>
                    <td colspan="7">{{ t('bridgeTokens.recordCount', { count: recordPage.total }) }}</td>
                  </tr>
                </tfoot>
              </table>
            </div>
            <div v-if="recordsLoading || !recordPage.records.length" class="records-table-footer">
              {{ t('bridgeTokens.recordCount', { count: recordPage.total }) }}
            </div>

            <nav v-if="pageCount > 1" class="pagination" :aria-label="t('bridgeTokens.records')">
              <button
                type="button"
                :disabled="recordPage.page <= 1 || recordsLoading"
                :title="t('bridgeTokens.previous')"
                :aria-label="t('bridgeTokens.previous')"
                @click="changePage(recordPage.page - 1)"
              >
                <ChevronLeft :size="17" aria-hidden="true" />
              </button>
              <span>{{ t('bridgeTokens.page', { page: recordPage.page, pages: pageCount }) }}</span>
              <button
                type="button"
                :disabled="recordPage.page >= pageCount || recordsLoading"
                :title="t('bridgeTokens.next')"
                :aria-label="t('bridgeTokens.next')"
                @click="changePage(recordPage.page + 1)"
              >
                <ChevronRight :size="17" aria-hidden="true" />
              </button>
            </nav>
          </section>
        </div>
      </template>
    </div>

    <div
      v-if="configurationOpen"
      class="configuration-backdrop"
      role="presentation"
      @mousedown.self="closeConfiguration"
    >
      <section
        class="configuration-dialog"
        role="dialog"
        aria-modal="true"
        aria-labelledby="bridge-configuration-title"
      >
        <header class="configuration-header">
          <div>
            <p class="eyebrow">MongoDB</p>
            <h2 id="bridge-configuration-title">{{ t('bridgeTokens.configuration.title') }}</h2>
          </div>
          <button
            class="dialog-close"
            type="button"
            :disabled="configurationSaving"
            :title="t('common.actions.close')"
            :aria-label="t('common.actions.close')"
            @click="closeConfiguration"
          >
            <X :size="19" aria-hidden="true" />
          </button>
        </header>

        <form class="configuration-form" @submit.prevent="saveConfiguration">
          <section class="configuration-section automation-setting">
            <div>
              <h3>{{ t('bridgeTokens.configuration.automation') }}</h3>
              <p>{{ t('bridgeTokens.configuration.automationSchedule') }}</p>
            </div>
            <el-switch v-model="configurationForm.automation_enabled" />
          </section>

          <p v-if="configurationForm.automation_enabled" class="configuration-warning">
            <CircleAlert :size="16" aria-hidden="true" />
            {{ t('bridgeTokens.configuration.enableWarning') }}
          </p>

          <section class="configuration-section">
            <h3>{{ t('bridgeTokens.configuration.connection') }}</h3>
            <div class="configuration-grid">
              <label class="configuration-field is-wide">
                <span>{{ t('bridgeTokens.configuration.baseUrl') }}</span>
                <input v-model.trim="configurationForm.base_url" type="url" required />
              </label>
              <label class="configuration-field">
                <span>{{ t('bridgeTokens.configuration.timezone') }}</span>
                <input v-model.trim="configurationForm.timezone" required />
              </label>
              <label class="configuration-field">
                <span>
                  {{ t('bridgeTokens.configuration.accessToken') }}
                  <i :class="configuration?.access_token_configured ? 'is-configured' : ''">
                    {{ secretStatus(configuration?.access_token_configured) }}
                  </i>
                </span>
                <input
                  v-model="configurationForm.access_token"
                  type="password"
                  autocomplete="new-password"
                  :placeholder="t('bridgeTokens.configuration.secretPlaceholder')"
                />
              </label>
              <label class="configuration-field">
                <span>
                  {{ t('bridgeTokens.configuration.refreshToken') }}
                  <i :class="configuration?.refresh_token_configured ? 'is-configured' : ''">
                    {{ secretStatus(configuration?.refresh_token_configured) }}
                  </i>
                </span>
                <input
                  v-model="configurationForm.refresh_token"
                  type="password"
                  autocomplete="new-password"
                  :placeholder="t('bridgeTokens.configuration.secretPlaceholder')"
                />
              </label>
            </div>
          </section>

          <section class="configuration-section">
            <h3>{{ t('bridgeTokens.configuration.quotaRules') }}</h3>
            <div class="configuration-grid is-numeric">
              <label class="configuration-field">
                <span>{{ t('bridgeTokens.configuration.quotaThreshold') }}</span>
                <input v-model.number="configurationForm.quota_threshold" type="number" min="0" step="0.01" required />
              </label>
              <label class="configuration-field">
                <span>{{ t('bridgeTokens.configuration.quotaIncrement') }}</span>
                <input v-model.number="configurationForm.quota_increment" type="number" min="0.01" step="0.01" required />
              </label>
              <label class="configuration-field">
                <span>{{ t('bridgeTokens.configuration.mainBalanceThreshold') }}</span>
                <input v-model.number="configurationForm.main_balance_alert_threshold" type="number" min="0" step="0.01" required />
              </label>
              <label class="configuration-field">
                <span>{{ t('bridgeTokens.configuration.weeklyBudget') }}</span>
                <input v-model.number="configurationForm.weekly_token_budget" type="number" min="0.01" step="0.01" required />
              </label>
              <label class="configuration-field">
                <span>{{ t('bridgeTokens.configuration.lookbackDays') }}</span>
                <input v-model.number="configurationForm.allocation_lookback_days" type="number" min="1" max="365" step="1" required />
              </label>
              <label class="configuration-field">
                <span>{{ t('bridgeTokens.configuration.minWeeklyAllocation') }}</span>
                <input v-model.number="configurationForm.min_weekly_allocation" type="number" min="0" step="0.01" required />
              </label>
              <label class="configuration-field">
                <span>{{ t('bridgeTokens.configuration.minRebalanceRemaining') }}</span>
                <input v-model.number="configurationForm.min_rebalance_remaining" type="number" min="0" step="0.01" required />
              </label>
            </div>
          </section>

          <section class="configuration-section">
            <h3>{{ t('bridgeTokens.configuration.email') }}</h3>
            <div class="configuration-grid">
              <label class="configuration-field">
                <span>{{ t('bridgeTokens.configuration.emailProvider') }}</span>
                <select v-model="configurationForm.email_provider">
                  <option value="gmail">Gmail</option>
                  <option value="smtp">SMTP</option>
                </select>
              </label>
              <label class="configuration-field">
                <span>{{ t('bridgeTokens.configuration.adminEmail') }}</span>
                <input v-model.trim="configurationForm.admin_email" type="email" />
              </label>
              <label class="configuration-field">
                <span>{{ t('bridgeTokens.configuration.emailFrom') }}</span>
                <input v-model.trim="configurationForm.email_from" type="email" />
              </label>
              <label class="configuration-field is-wide">
                <span>{{ t('bridgeTokens.configuration.reminderSubject') }}</span>
                <input v-model.trim="configurationForm.reminder_subject" maxlength="240" required />
              </label>

              <template v-if="configurationForm.email_provider === 'smtp'">
                <label class="configuration-field">
                  <span>{{ t('bridgeTokens.configuration.smtpHost') }}</span>
                  <input v-model.trim="configurationForm.smtp_host" required />
                </label>
                <label class="configuration-field">
                  <span>{{ t('bridgeTokens.configuration.smtpPort') }}</span>
                  <input v-model.number="configurationForm.smtp_port" type="number" min="1" max="65535" required />
                </label>
                <label class="configuration-field">
                  <span>{{ t('bridgeTokens.configuration.smtpUsername') }}</span>
                  <input v-model.trim="configurationForm.smtp_username" autocomplete="username" />
                </label>
                <label class="configuration-field">
                  <span>
                    {{ t('bridgeTokens.configuration.smtpPassword') }}
                    <i :class="configuration?.smtp_password_configured ? 'is-configured' : ''">
                      {{ secretStatus(configuration?.smtp_password_configured) }}
                    </i>
                  </span>
                  <input
                    v-model="configurationForm.smtp_password"
                    type="password"
                    autocomplete="new-password"
                    :placeholder="t('bridgeTokens.configuration.secretPlaceholder')"
                  />
                </label>
                <div class="configuration-switches is-wide">
                  <label>
                    <span>SSL</span>
                    <el-switch v-model="configurationForm.smtp_use_ssl" />
                  </label>
                  <label>
                    <span>STARTTLS</span>
                    <el-switch v-model="configurationForm.smtp_starttls" />
                  </label>
                </div>
              </template>
            </div>
          </section>

          <p v-if="configurationError" class="configuration-error" role="alert">
            {{ configurationError }}
          </p>

          <footer class="configuration-actions">
            <span v-if="configuration" class="configuration-updated">
              {{ t('bridgeTokens.configuration.updatedBy', {
                user: configuration.updated_by,
                time: formatDate(configuration.updated_at),
              }) }}
            </span>
            <button type="button" :disabled="configurationSaving" @click="closeConfiguration">
              {{ t('common.actions.cancel') }}
            </button>
            <button class="is-primary" type="submit" :disabled="configurationSaving">
              <Save :size="16" aria-hidden="true" />
              {{ configurationSaving
                ? t('bridgeTokens.configuration.saving')
                : t('common.actions.save') }}
            </button>
          </footer>
        </form>
      </section>
    </div>
  </main>
</template>

<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import {
  ArrowLeft,
  CheckCircle,
  ChevronLeft,
  ChevronRight,
  CircleAlert,
  Database,
  History,
  Pencil,
  RefreshCw,
  Save,
  Wifi,
  X,
  XCircle,
} from '@lucide/vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import AuthUserMenu from '@/components/AuthUserMenu.vue'
import LocaleSwitcher from '@/components/LocaleSwitcher.vue'
import { useAppLocale } from '@/i18n'
import { useAuthStore } from '@/scripts/stores/auth'
import {
  bridgeTokensApi,
  type BridgeTokenAction,
  type BridgeTokenConfiguration,
  type BridgeTokenConfigurationUpdate,
  type BridgeTokenRecord,
  type BridgeTokenRecordPage,
  type CurrentUserBridgeTokens,
} from '@/scripts/api/bridgeTokens'


const { locale, t } = useAppLocale()
const authStore = useAuthStore()
const balance = ref<CurrentUserBridgeTokens | null>(null)
const initialLoading = ref(true)
const refreshing = ref(false)
const recordsLoading = ref(false)
const recordsError = ref(false)
const selectedAction = ref<BridgeTokenAction | ''>('')
type ActiveTab = 'balance' | 'records'
const activeTab = ref<ActiveTab>('balance')
const configurationOpen = ref(false)
const configurationLoading = ref(false)
const configurationSaving = ref(false)
const configurationError = ref('')
const configuration = ref<BridgeTokenConfiguration | null>(null)
const configurationForm = ref<BridgeTokenConfigurationUpdate>(emptyConfigurationForm())
const pageSize = 20
const recordPage = ref<BridgeTokenRecordPage>({
  records: [],
  total: 0,
  page: 1,
  page_size: pageSize,
})
const actionOptions: BridgeTokenAction[] = [
  'weekly_allocation',
  'low_balance_topup',
  'weekly_rebalance',
  'weekly_reminder',
]

const canEditConfiguration = computed(() => authStore.user?.role === 'admin')

function emptyConfigurationForm(): BridgeTokenConfigurationUpdate {
  return {
    automation_enabled: false,
    base_url: 'https://api.bridgefloods.com/api/v1',
    timezone: 'Asia/Shanghai',
    quota_threshold: 50,
    quota_increment: 100,
    main_balance_alert_threshold: 50,
    weekly_token_budget: 2000,
    allocation_lookback_days: 14,
    min_weekly_allocation: 50,
    min_rebalance_remaining: 20,
    reminder_subject: t('bridgeTokens.configuration.defaultReminderSubject'),
    admin_email: '',
    email_provider: 'gmail',
    email_from: '',
    smtp_host: '',
    smtp_port: 587,
    smtp_username: '',
    smtp_use_ssl: false,
    smtp_starttls: true,
    access_token: '',
    refresh_token: '',
    smtp_password: '',
  }
}

function configurationToForm(
  value: BridgeTokenConfiguration,
): BridgeTokenConfigurationUpdate {
  return {
    automation_enabled: value.automation_enabled,
    base_url: value.base_url,
    timezone: value.timezone,
    quota_threshold: value.quota_threshold,
    quota_increment: value.quota_increment,
    main_balance_alert_threshold: value.main_balance_alert_threshold,
    weekly_token_budget: value.weekly_token_budget,
    allocation_lookback_days: value.allocation_lookback_days,
    min_weekly_allocation: value.min_weekly_allocation,
    min_rebalance_remaining: value.min_rebalance_remaining,
    reminder_subject: value.reminder_subject,
    admin_email: value.admin_email,
    email_provider: value.email_provider,
    email_from: value.email_from,
    smtp_host: value.smtp_host,
    smtp_port: value.smtp_port,
    smtp_username: value.smtp_username,
    smtp_use_ssl: value.smtp_use_ssl,
    smtp_starttls: value.smtp_starttls,
    access_token: '',
    refresh_token: '',
    smtp_password: '',
  }
}

const utilization = computed(() => {
  const quota = balance.value?.total_quota || 0
  if (quota <= 0) return 0
  return Math.min(100, Math.max(0, Math.round(((balance.value?.total_used || 0) / quota) * 100)))
})

const pageCount = computed(() => Math.max(1, Math.ceil(recordPage.value.total / pageSize)))

const stateTitle = computed(() => {
  if (!balance.value) return t('bridgeTokens.states.noBalanceTitle')
  if (!balance.value.configured) return t('bridgeTokens.states.notConfiguredTitle')
  if (!balance.value.linked) return t('bridgeTokens.states.noEnabledKeysTitle')
  if (!balance.value.keys.length) return t('bridgeTokens.states.noBalanceTitle')
  return ''
})

const stateBody = computed(() => {
  if (!balance.value) return t('bridgeTokens.states.noBalanceBody')
  if (!balance.value.configured) return t('bridgeTokens.states.notConfiguredBody')
  if (!balance.value.linked) return t('bridgeTokens.states.noEnabledKeysBody')
  return t('bridgeTokens.states.noBalanceBody')
})

function formatTokens(value: number): string {
  return new Intl.NumberFormat(locale.value, {
    minimumFractionDigits: 0,
    maximumFractionDigits: 2,
  }).format(Number.isFinite(value) ? value : 0)
}

function formatDate(value: string): string {
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return '—'
  return new Intl.DateTimeFormat(locale.value, {
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
    second: '2-digit',
  }).format(date)
}

function statusLabel(status: string): string {
  if (status === 'active') return t('bridgeTokens.active')
  if (status === 'quota_exhausted') return t('bridgeTokens.exhausted')
  return t('bridgeTokens.unknown')
}

function statusClass(status: string): string {
  if (status === 'active') return 'is-active'
  if (status === 'quota_exhausted') return 'is-exhausted'
  return 'is-unknown'
}

function actionLabel(action: BridgeTokenAction): string {
  return t(`bridgeTokens.actions.${action}`)
}

function formatAmount(record: BridgeTokenRecord): string {
  if (record.action === 'weekly_reminder') return '—'
  const prefix = record.amount > 0 ? '+' : ''
  return `${prefix}${formatTokens(record.amount)}`
}

function amountClass(amount: number): string {
  if (amount > 0) return 'amount-positive'
  if (amount < 0) return 'amount-negative'
  return ''
}

function secretStatus(configured: boolean | undefined): string {
  return configured
    ? t('bridgeTokens.configuration.configured')
    : t('bridgeTokens.configuration.notConfigured')
}

function apiError(error: unknown, fallback: string): string {
  const detail = (error as { response?: { data?: { detail?: unknown } } })
    ?.response?.data?.detail
  return typeof detail === 'string' && detail.trim() ? detail : fallback
}

async function openConfiguration(): Promise<void> {
  if (!canEditConfiguration.value || configurationLoading.value) return
  configurationLoading.value = true
  configurationError.value = ''
  try {
    const response = await bridgeTokensApi.getConfiguration()
    configuration.value = response.data
    configurationForm.value = configurationToForm(response.data)
    configurationOpen.value = true
  } catch (error) {
    ElMessage.error(apiError(error, t('bridgeTokens.configuration.loadFailed')))
  } finally {
    configurationLoading.value = false
  }
}

function closeConfiguration(): void {
  if (configurationSaving.value) return
  configurationOpen.value = false
  configurationError.value = ''
}

async function saveConfiguration(): Promise<void> {
  if (configurationSaving.value) return
  if (
    configurationForm.value.automation_enabled
    && !configuration.value?.automation_enabled
  ) {
    try {
      await ElMessageBox.confirm(
        t('bridgeTokens.configuration.enableConfirmation'),
        t('bridgeTokens.configuration.enableConfirmationTitle'),
        {
          confirmButtonText: t('bridgeTokens.configuration.confirmEnable'),
          cancelButtonText: t('common.actions.cancel'),
          type: 'warning',
        },
      )
    } catch {
      return
    }
  }
  configurationSaving.value = true
  configurationError.value = ''
  try {
    const response = await bridgeTokensApi.updateConfiguration({
      ...configurationForm.value,
      access_token: configurationForm.value.access_token || undefined,
      refresh_token: configurationForm.value.refresh_token || undefined,
      smtp_password: configurationForm.value.smtp_password || undefined,
    })
    configuration.value = response.data
    configurationForm.value = configurationToForm(response.data)
    configurationOpen.value = false
    ElMessage.success(t('bridgeTokens.configuration.saved'))
    await refreshAll()
  } catch (error) {
    configurationError.value = apiError(
      error,
      t('bridgeTokens.configuration.saveFailed'),
    )
  } finally {
    configurationSaving.value = false
  }
}

async function loadBalance(refresh: boolean): Promise<void> {
  if (refreshing.value) return
  refreshing.value = true
  try {
    const response = await bridgeTokensApi.getMine(refresh)
    balance.value = response.data
  } catch {
    if (balance.value) balance.value = { ...balance.value, live: false, error: 'live_refresh_failed' }
  } finally {
    refreshing.value = false
    initialLoading.value = false
  }
}

async function loadRecords(page = recordPage.value.page): Promise<void> {
  if (recordsLoading.value) return
  recordsLoading.value = true
  recordsError.value = false
  try {
    const response = await bridgeTokensApi.getMyRecords({
      action: selectedAction.value || undefined,
      page,
      page_size: pageSize,
    })
    recordPage.value = response.data
  } catch {
    recordsError.value = true
  } finally {
    recordsLoading.value = false
  }
}

async function refreshAll(): Promise<void> {
  await Promise.all([loadBalance(true), loadRecords(1)])
}

function changePage(page: number): void {
  if (page < 1 || page > pageCount.value) return
  void loadRecords(page)
}

watch(selectedAction, () => {
  void loadRecords(1)
})

let refreshInterval: ReturnType<typeof setInterval> | undefined

function handleConfigurationKeydown(event: KeyboardEvent): void {
  if (event.key === 'Escape' && configurationOpen.value) closeConfiguration()
}

onMounted(() => {
  void loadBalance(true)
  void loadRecords(1)
  window.addEventListener('keydown', handleConfigurationKeydown)
  refreshInterval = setInterval(() => {
    void loadBalance(true)
    void loadRecords(recordPage.value.page)
  }, 30_000)
})

onBeforeUnmount(() => {
  if (refreshInterval) clearInterval(refreshInterval)
  window.removeEventListener('keydown', handleConfigurationKeydown)
})
</script>

<style scoped>
.bridge-token-page {
  min-width: 320px;
  min-height: 100vh;
  color: #1d282d;
  background: #f3f6f4;
  font-family: Inter, ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
}

.bridge-token-header {
  display: flex;
  min-height: 64px;
  align-items: center;
  justify-content: space-between;
  gap: 20px;
  padding: 0 32px;
  border-bottom: 1px solid #dce3df;
  background: rgba(255, 255, 255, 0.94);
}

.back-link,
.header-actions,
.live-meta,
.live-state,
.inline-notice,
.result-state,
.pagination {
  display: flex;
  align-items: center;
}

.back-link {
  min-width: 0;
  gap: 8px;
  color: #34464c;
  font-size: 13px;
  font-weight: 700;
  text-decoration: none;
}

.back-link:hover {
  color: #087b72;
}

.header-actions {
  gap: 12px;
}

.bridge-token-content {
  width: min(1180px, calc(100% - 48px));
  margin: 0 auto;
  padding: 44px 0 64px;
}

.page-heading {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 24px;
  margin-bottom: 28px;
}

.eyebrow {
  margin: 0 0 7px;
  color: #3d6f6b;
  font-size: 11px;
  font-weight: 800;
  letter-spacing: 0;
  text-transform: uppercase;
}

.page-heading h1 {
  margin: 0;
  color: #172126;
  font-size: 32px;
  font-weight: 760;
  line-height: 1.18;
  letter-spacing: 0;
}

.heading-actions {
  display: flex;
  align-items: center;
  gap: 8px;
}

.live-meta {
  flex-wrap: wrap;
  gap: 8px 13px;
  margin-top: 12px;
  color: #738087;
  font-size: 12px;
}

.live-state {
  gap: 5px;
  color: #6d787e;
  font-weight: 700;
}

.live-state.is-live {
  color: #16735e;
}

.icon-button,
.pagination button {
  display: grid;
  width: 38px;
  height: 38px;
  flex: 0 0 38px;
  place-items: center;
  border: 1px solid #cfd9d5;
  border-radius: 6px;
  background: #fff;
  color: #2f5554;
  cursor: pointer;
}

.configuration-backdrop {
  position: fixed;
  z-index: 1500;
  inset: 0;
  display: grid;
  place-items: center;
  padding: 24px;
  background: rgba(20, 31, 33, 0.46);
}

.configuration-dialog {
  display: flex;
  width: min(900px, 100%);
  max-height: calc(100vh - 48px);
  flex-direction: column;
  overflow: hidden;
  border: 1px solid #d3ddda;
  border-radius: 8px;
  background: #fff;
  box-shadow: 0 24px 70px rgba(21, 35, 37, 0.24);
}

.configuration-header {
  display: flex;
  flex: 0 0 auto;
  align-items: flex-start;
  justify-content: space-between;
  gap: 20px;
  padding: 22px 24px 18px;
  border-bottom: 1px solid #dfe6e3;
}

.configuration-header .eyebrow {
  margin-bottom: 4px;
}

.configuration-header h2 {
  margin: 0;
  color: #1c292e;
  font-size: 20px;
  letter-spacing: 0;
}

.dialog-close {
  display: grid;
  width: 34px;
  height: 34px;
  flex: 0 0 34px;
  place-items: center;
  border: 1px solid #d5dfdb;
  border-radius: 6px;
  background: #fff;
  color: #59676c;
  cursor: pointer;
}

.dialog-close:hover:not(:disabled) {
  border-color: #8aacaa;
  color: #176d65;
  background: #f1f7f5;
}

.dialog-close:disabled {
  opacity: 0.5;
  cursor: wait;
}

.configuration-form {
  min-height: 0;
  overflow-y: auto;
}

.configuration-section {
  padding: 22px 24px;
  border-bottom: 1px solid #e5eae8;
}

.configuration-section h3 {
  margin: 0 0 15px;
  color: #26353a;
  font-size: 13px;
  letter-spacing: 0;
}

.automation-setting {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 24px;
}

.automation-setting h3 {
  margin-bottom: 4px;
}

.automation-setting p {
  margin: 0;
  color: #748087;
  font-size: 11px;
}

.configuration-warning,
.configuration-error {
  display: flex;
  align-items: flex-start;
  gap: 8px;
  margin: 0;
  padding: 11px 24px;
  border-bottom: 1px solid #f0dfbc;
  background: #fff8e8;
  color: #80591d;
  font-size: 12px;
}

.configuration-warning svg {
  flex: 0 0 auto;
  margin-top: 1px;
}

.configuration-error {
  border-bottom-color: #efd2d0;
  background: #fff1f0;
  color: #9d3d3d;
}

.configuration-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 15px 18px;
}

.configuration-grid.is-numeric {
  grid-template-columns: repeat(3, minmax(0, 1fr));
}

.configuration-field {
  display: grid;
  min-width: 0;
  gap: 6px;
}

.configuration-field.is-wide,
.configuration-switches.is-wide {
  grid-column: 1 / -1;
}

.configuration-field > span {
  display: flex;
  min-width: 0;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
  color: #5c696f;
  font-size: 11px;
  font-weight: 700;
}

.configuration-field i {
  flex: 0 0 auto;
  color: #9b5656;
  font-size: 9px;
  font-style: normal;
  font-weight: 700;
}

.configuration-field i.is-configured {
  color: #1b755f;
}

.configuration-field input,
.configuration-field select {
  width: 100%;
  height: 38px;
  min-width: 0;
  padding: 0 10px;
  border: 1px solid #cdd8d4;
  border-radius: 6px;
  outline: none;
  background: #fff;
  color: #2e3d42;
  font: inherit;
  font-size: 12px;
  letter-spacing: 0;
}

.configuration-field input:focus,
.configuration-field select:focus {
  border-color: #4c968e;
  box-shadow: 0 0 0 2px rgba(30, 133, 120, 0.12);
}

.configuration-switches {
  display: flex;
  align-items: center;
  gap: 28px;
  padding-top: 3px;
}

.configuration-switches label {
  display: flex;
  align-items: center;
  gap: 9px;
  color: #59686d;
  font-size: 11px;
  font-weight: 700;
}

.configuration-actions {
  position: sticky;
  bottom: 0;
  display: flex;
  align-items: center;
  justify-content: flex-end;
  gap: 9px;
  min-height: 66px;
  padding: 13px 24px;
  border-top: 1px solid #dfe6e3;
  background: #fbfcfb;
}

.configuration-updated {
  min-width: 0;
  margin-right: auto;
  overflow: hidden;
  color: #7c878c;
  font-size: 10px;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.configuration-actions button {
  display: inline-flex;
  min-width: 82px;
  height: 36px;
  align-items: center;
  justify-content: center;
  gap: 7px;
  padding: 0 14px;
  border: 1px solid #ccd7d3;
  border-radius: 6px;
  background: #fff;
  color: #435157;
  font: inherit;
  font-size: 12px;
  font-weight: 700;
  cursor: pointer;
}

.configuration-actions button.is-primary {
  border-color: #176f65;
  background: #176f65;
  color: #fff;
}

.configuration-actions button:hover:not(:disabled) {
  border-color: #6a9893;
}

.configuration-actions button.is-primary:hover:not(:disabled) {
  background: #115e56;
}

.configuration-actions button:disabled {
  opacity: 0.55;
  cursor: wait;
}

.icon-button:hover:not(:disabled),
.pagination button:hover:not(:disabled) {
  border-color: #7ca9a4;
  background: #edf6f3;
}

.icon-button:disabled,
.pagination button:disabled {
  opacity: 0.45;
  cursor: not-allowed;
}

.loading-shell,
.state-panel,
.balance-panel {
  border: 1px solid #d9e1dd;
  border-radius: 8px;
  background: #fff;
}

.loading-shell {
  display: grid;
  gap: 15px;
  padding: 42px;
}

.loading-line {
  width: 54%;
  height: 16px;
  border-radius: 4px;
  background: #e7ece9;
  animation: pulse 1.2s ease-in-out infinite alternate;
}

.loading-line.is-wide { width: 84%; height: 28px; }
.loading-line.is-short { width: 32%; }

.state-panel {
  display: flex;
  min-height: 170px;
  align-items: center;
  justify-content: center;
  gap: 16px;
  padding: 32px;
  color: #845b24;
}

.state-panel h2 {
  margin: 0 0 5px;
  color: #2c373b;
  font-size: 17px;
  letter-spacing: 0;
}

.state-panel p {
  margin: 0;
  color: #68757a;
  font-size: 13px;
}

.inline-notice {
  gap: 8px;
  margin: 0 0 16px;
  padding: 10px 12px;
  border-left: 3px solid #d79a3d;
  background: #fff8e9;
  color: #79551f;
  font-size: 12px;
}

.inline-notice.is-error {
  border-left-color: #c45555;
  background: #fff3f2;
  color: #943a3a;
}

.bridge-token-tabs {
  display: flex;
  gap: 28px;
  margin: 24px 0 0;
  border-bottom: 1px solid #d9e1dd;
}

.bridge-token-tabs button {
  display: inline-flex;
  min-height: 44px;
  align-items: center;
  gap: 8px;
  margin-bottom: -1px;
  padding: 0 2px 11px;
  border: 0;
  border-bottom: 2px solid transparent;
  background: transparent;
  color: #718087;
  font: inherit;
  font-size: 13px;
  font-weight: 750;
  white-space: nowrap;
  cursor: pointer;
}

.bridge-token-tabs button:hover {
  color: #216f69;
}

.bridge-token-tabs button.is-active {
  border-bottom-color: #168577;
  color: #1b625d;
}

.bridge-token-tabs button:focus-visible {
  outline: 2px solid #168577;
  outline-offset: 3px;
}

.tab-count {
  color: #8a969a;
  font-size: 11px;
  font-weight: 600;
}

.bridge-token-tabs button.is-active .tab-count {
  color: #4a7772;
}

.tab-panel {
  min-width: 0;
}

.balance-panel {
  display: grid;
  grid-template-columns: minmax(220px, 0.8fr) minmax(420px, 1.4fr);
  overflow: hidden;
}

.balance-primary {
  display: grid;
  grid-row: 1 / span 2;
  align-content: center;
  padding: 32px;
  border-right: 1px solid #e1e7e4;
  background: #213a3a;
  color: #fff;
}

.balance-primary > span {
  color: #b9ceca;
  font-size: 12px;
  font-weight: 700;
}

.balance-primary strong {
  margin-top: 5px;
  font-size: 38px;
  font-variant-numeric: tabular-nums;
  line-height: 1.08;
  letter-spacing: 0;
}

.balance-primary small {
  margin-top: 3px;
  color: #a9c4c0;
  font-size: 11px;
}

.balance-metrics {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  align-items: center;
  padding: 20px 8px;
}

.balance-metrics > div {
  display: grid;
  gap: 7px;
  min-width: 0;
  padding: 12px 24px;
  border-right: 1px solid #e5eae7;
}

.balance-metrics > div:last-child { border-right: 0; }
.balance-metrics span { color: #748087; font-size: 11px; font-weight: 700; }
.balance-metrics strong { font-size: 22px; font-variant-numeric: tabular-nums; letter-spacing: 0; }

.utilization-track {
  grid-column: 2;
  height: 4px;
  margin: -12px 32px 24px;
  overflow: hidden;
  border-radius: 2px;
  background: #e7ece9;
}

.utilization-track span {
  display: block;
  height: 100%;
  border-radius: inherit;
  background: #2b8a78;
  transition: width 240ms ease;
}

.key-section,
.records-section {
  margin-top: 30px;
}

.records-toolbar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
}

.key-table {
  margin-top: 0;
  overflow: hidden;
  border: 1px solid #dbe2df;
  border-radius: 8px;
  background: #fff;
}

.key-table-head,
.key-table-row {
  display: grid;
  grid-template-columns: minmax(130px, 1.2fr) minmax(160px, 1.2fr) 110px repeat(3, minmax(90px, 0.8fr));
  gap: 14px;
  align-items: center;
  min-width: 820px;
  padding: 12px 18px;
}

.key-table-head {
  border-bottom: 1px solid #e2e8e5;
  background: #f7f9f8;
  color: #758086;
  font-size: 10px;
  font-weight: 800;
  text-transform: uppercase;
}

.key-table-row {
  color: #536067;
  font-size: 12px;
}

.key-table-row + .key-table-row { border-top: 1px solid #edf0ee; }
.key-table-row strong { color: #263338; }
.remaining-cell { font-variant-numeric: tabular-nums; }

.table-footer,
.records-table-footer {
  display: flex;
  min-height: 38px;
  align-items: center;
  justify-content: flex-end;
  padding: 0 18px;
  border-top: 1px solid #e2e8e5;
  background: #fbfcfb;
  color: #7a858a;
  font-size: 11px;
  font-weight: 600;
}

.status-pill {
  display: inline-flex;
  align-items: center;
  min-height: 24px;
  padding: 0 8px;
  border-radius: 999px;
  font-size: 10px;
  font-style: normal;
  font-weight: 750;
}

.status-pill.is-active { color: #176b55; background: #e8f5ef; }
.status-pill.is-exhausted { color: #a84040; background: #fdeceb; }
.status-pill.is-unknown { color: #6b7478; background: #edf0ef; }

.records-toolbar {
  align-items: flex-end;
  margin-bottom: 12px;
}

.action-filter select {
  width: 190px;
  height: 36px;
  padding: 0 32px 0 10px;
  border: 1px solid #ced8d4;
  border-radius: 6px;
  background: #fff;
  color: #344248;
  font: inherit;
  font-size: 12px;
}

.records-table-wrap {
  overflow-x: auto;
  border: 1px solid #dbe2df;
  border-radius: 8px;
  background: #fff;
}

.records-table {
  width: 100%;
  min-width: 880px;
  border-collapse: collapse;
  table-layout: fixed;
  font-size: 12px;
}

.records-table th,
.records-table td {
  padding: 12px 14px;
  border-bottom: 1px solid #e8ecea;
  text-align: left;
  vertical-align: middle;
}

.records-table tfoot td {
  border-bottom: 0;
  background: #fbfcfb;
  color: #7a858a;
  font-size: 11px;
  font-weight: 600;
  text-align: right;
}

.records-table th {
  background: #f7f9f8;
  color: #748087;
  font-size: 10px;
  font-weight: 800;
  text-transform: uppercase;
}

.records-table th:first-child { width: 170px; }
.records-table th:nth-child(2) { width: 120px; }
.records-table th:nth-child(3) { width: 160px; }
.records-table tbody tr:last-child td { border-bottom: 0; }
.records-table tbody tr:hover { background: #fafcfb; }
.amount-positive { color: #15715b; font-weight: 750; }
.amount-negative { color: #a64848; font-weight: 750; }

.result-state {
  width: fit-content;
  gap: 5px;
  font-size: 11px;
  font-weight: 700;
}

.result-state.is-success { color: #176b55; }
.result-state.is-failed { color: #a53c3c; }

.records-loading,
.empty-records {
  display: flex;
  min-height: 110px;
  align-items: center;
  justify-content: center;
  gap: 8px;
  border: 1px solid #dbe2df;
  border-radius: 8px;
  background: #fff;
  color: #7b868b;
  font-size: 12px;
}

.records-loading,
.empty-records {
  border-radius: 8px 8px 0 0;
}

.records-table-footer {
  margin-top: -1px;
  border: 1px solid #dbe2df;
  border-top: 0;
  border-radius: 0 0 8px 8px;
}

.pagination {
  justify-content: flex-end;
  gap: 12px;
  margin-top: 14px;
  color: #68757a;
  font-size: 11px;
}

.pagination button {
  width: 32px;
  height: 32px;
  flex-basis: 32px;
}

.sr-only {
  position: absolute;
  width: 1px;
  height: 1px;
  overflow: hidden;
  clip: rect(0, 0, 0, 0);
  white-space: nowrap;
}

.is-spinning { animation: spin 0.9s linear infinite; }

@keyframes spin { to { transform: rotate(360deg); } }
@keyframes pulse { to { opacity: 0.48; } }

@media (max-width: 820px) {
  .bridge-token-header { padding: 0 18px; }
  .bridge-token-content { width: min(100% - 32px, 1180px); padding-top: 32px; }
  .balance-panel { grid-template-columns: 1fr; }
  .balance-primary { grid-row: auto; border-right: 0; }
  .utilization-track { grid-column: 1; margin-top: -10px; }
  .key-table { overflow-x: auto; }
  .configuration-grid.is-numeric { grid-template-columns: repeat(2, minmax(0, 1fr)); }
}

@media (max-width: 560px) {
  .bridge-token-header { min-height: 58px; }
  .header-actions > :first-child { display: none; }
  .back-link span { display: none; }
  .bridge-token-content { width: min(100% - 24px, 1180px); padding: 28px 0 44px; }
  .page-heading { margin-bottom: 22px; }
  .page-heading h1 { font-size: 27px; }
  .balance-primary { padding: 24px; }
  .balance-primary strong { font-size: 32px; }
  .balance-metrics { grid-template-columns: 1fr; padding: 8px 20px 16px; }
  .balance-metrics > div { grid-template-columns: 1fr auto; align-items: center; padding: 12px 4px; border-right: 0; border-bottom: 1px solid #e8ecea; }
  .balance-metrics > div:last-child { border-bottom: 0; }
  .balance-metrics strong { font-size: 18px; }
  .utilization-track { margin: -8px 24px 22px; }
  .bridge-token-tabs { gap: 20px; overflow-x: auto; }
  .bridge-token-tabs button { flex: 0 0 auto; }
  .records-toolbar { align-items: stretch; flex-direction: column; }
  .action-filter select { width: 100%; }
  .configuration-backdrop { padding: 8px; }
  .configuration-dialog { max-height: calc(100vh - 16px); }
  .configuration-header,
  .configuration-section { padding-right: 16px; padding-left: 16px; }
  .configuration-grid,
  .configuration-grid.is-numeric { grid-template-columns: 1fr; }
  .configuration-actions { flex-wrap: wrap; padding: 12px 16px; }
  .configuration-updated { width: 100%; margin-right: 0; }
}
</style>
