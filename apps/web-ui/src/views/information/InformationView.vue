<template>
  <main class="information-page" :aria-labelledby="`${props.kind}-information-title`">
    <div class="information-shell">
      <RouterLink class="back-link" to="/">
        <ArrowLeft :size="16" aria-hidden="true" />
        <span>{{ t('information.backHome') }}</span>
      </RouterLink>

      <header class="information-heading">
        <div class="heading-copy">
          <p class="eyebrow">{{ t('information.eyebrow') }}</p>
          <h1 :id="`${props.kind}-information-title`">{{ pageTitle }}</h1>
          <p>{{ pageIntroduction }}</p>
        </div>
        <div class="information-actions">
          <a class="secondary-action" :href="sourceUrl" target="_blank" rel="noopener noreferrer">
            <FolderOpen :size="17" aria-hidden="true" />
            <span>{{ t('information.openFolder') }}</span>
          </a>
          <button class="refresh-button" type="button" :disabled="isLoading || isRefreshing" @click="loadFiles(true)">
            <RefreshCw :size="17" :class="{ 'is-spinning': isLoading || isRefreshing }" aria-hidden="true" />
            <span>{{ t('information.refresh') }}</span>
          </button>
        </div>
      </header>

      <section class="records-section" :aria-labelledby="`${props.kind}-records-title`">
        <header class="records-heading">
          <div>
            <h2 :id="`${props.kind}-records-title`">{{ t('information.listTitle', { year }) }}</h2>
            <p>{{ t('information.listDescription') }}</p>
          </div>
          <span class="record-count">{{ t('information.recordCount', { count: files.length }) }}</span>
        </header>

        <div v-if="(isLoading || isRefreshing) && !files.length" class="information-state">
          <RefreshCw class="is-spinning" :size="24" aria-hidden="true" />
          <span>{{ t('information.loading') }}</span>
        </div>
        <div v-else-if="loadError" class="information-state is-error" role="alert">
          <CircleAlert :size="24" aria-hidden="true" />
          <strong>{{ t('information.loadFailed') }}</strong>
          <span>{{ loadError }}</span>
          <button type="button" @click="loadFiles(true)">{{ t('information.retry') }}</button>
        </div>
        <div v-else-if="!files.length" class="information-state">
          <FileText :size="28" aria-hidden="true" />
          <strong>{{ t('information.emptyTitle') }}</strong>
          <span>{{ t('information.emptyDescription') }}</span>
        </div>
        <div v-else class="records-table" role="table" :aria-label="pageTitle">
          <div class="records-table-header" :class="{ 'has-product-model': props.kind === 'ecn' }" role="row">
            <span role="columnheader">{{ t('information.columns.number') }}</span>
            <span role="columnheader">{{ t('information.columns.subject') }}</span>
            <span v-if="props.kind === 'ecn'" role="columnheader">{{ t('information.columns.productModel') }}</span>
            <span role="columnheader">{{ dateColumnLabel }}</span>
            <span aria-hidden="true"></span>
          </div>
          <a
            v-for="file in files"
            :key="file.id"
            class="record-row"
            :class="{ 'has-product-model': props.kind === 'ecn' }"
            :href="file.web_view_link"
            target="_blank"
            rel="noopener noreferrer"
            role="row"
            :aria-label="t('information.openRecord', { number: file.number })"
          >
            <span class="record-number" role="cell">
              <span class="mobile-label">{{ t('information.columns.number') }}</span>
              <code>{{ file.number }}</code>
            </span>
            <span class="record-subject" role="cell">
              <span class="mobile-label">{{ t('information.columns.subject') }}</span>
              <strong>{{ file.subject }}</strong>
            </span>
            <span v-if="props.kind === 'ecn'" class="record-product-model" role="cell">
              <span class="mobile-label">{{ t('information.columns.productModel') }}</span>
              <strong>{{ file.product_model || t('information.notAvailable') }}</strong>
            </span>
            <span class="record-date" role="cell">
              <span class="mobile-label">{{ dateColumnLabel }}</span>
              {{ formatDate(file.effective_date) }}
            </span>
            <span class="record-open" aria-hidden="true"><ExternalLink :size="17" /></span>
          </a>
        </div>
      </section>
    </div>
  </main>
</template>

<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import {
  ArrowLeft,
  CircleAlert,
  ExternalLink,
  FileText,
  FolderOpen,
  RefreshCw,
} from '@lucide/vue'
import { useI18n } from 'vue-i18n'
import { useAppLocale } from '@/i18n'
import { informationApi } from '@/scripts/api'
import type { InformationFile, InformationKind } from '@/scripts/types'

const props = defineProps<{ kind: InformationKind }>()
const { t } = useI18n()
const { locale } = useAppLocale()

const files = ref<InformationFile[]>([])
const sourceUrl = ref('')
const year = ref(new Date().getFullYear())
const isLoading = ref(false)
const isRefreshing = ref(false)
const loadError = ref('')
let refreshPollTimer: ReturnType<typeof setTimeout> | undefined
const defaultSourceUrls: Record<InformationKind, string> = {
  ecn: 'https://drive.google.com/drive/folders/1cAlMjAWMnk47cvvxSPEtG4_xn6O3xmMB',
  contact: 'https://drive.google.com/drive/folders/1rC0Q2FtayNKkO3gY4_39CuaQdYA_wVtF',
}
sourceUrl.value = defaultSourceUrls[props.kind]

const pageTitle = computed(() => t(props.kind === 'ecn' ? 'information.ecn.title' : 'information.contact.title'))
const pageIntroduction = computed(() => t(props.kind === 'ecn' ? 'information.ecn.introduction' : 'information.contact.introduction'))
const dateColumnLabel = computed(() => t(props.kind === 'ecn' ? 'information.columns.issuedAt' : 'information.columns.effectiveDate'))

function formatDate(value?: string | null): string {
  if (!value) return t('information.notAvailable')
  const isoDate = /^(\d{4})-(\d{2})-(\d{2})$/.exec(value)
  if (!isoDate) return value
  const date = new Date(Date.UTC(Number(isoDate[1]), Number(isoDate[2]) - 1, Number(isoDate[3])))
  return new Intl.DateTimeFormat(locale.value, {
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
    timeZone: 'UTC',
  }).format(date)
}

function errorMessage(error: unknown): string {
  const response = (error as { response?: { data?: { detail?: string; message?: string } } })?.response
  return response?.data?.detail || response?.data?.message || (error instanceof Error ? error.message : t('information.loadFailed'))
}

function clearRefreshPoll(): void {
  if (refreshPollTimer !== undefined) {
    clearTimeout(refreshPollTimer)
    refreshPollTimer = undefined
  }
}

function scheduleRefreshPoll(): void {
  clearRefreshPoll()
  refreshPollTimer = setTimeout(() => {
    refreshPollTimer = undefined
    void loadFiles(false)
  }, 2000)
}

async function loadFiles(refresh = false): Promise<void> {
  if (isLoading.value) return
  isLoading.value = true
  loadError.value = ''
  try {
    const response = await informationApi.getFiles(props.kind, refresh)
    files.value = Array.isArray(response.data.files) ? response.data.files : []
    year.value = response.data.year || year.value
    sourceUrl.value = response.data.source_url || defaultSourceUrls[props.kind]
    isRefreshing.value = response.data.refreshing === true
    if (isRefreshing.value) {
      scheduleRefreshPoll()
    } else {
      clearRefreshPoll()
      if (!files.value.length && response.data.error) loadError.value = response.data.error
    }
  } catch (error) {
    isRefreshing.value = false
    clearRefreshPoll()
    loadError.value = errorMessage(error)
  } finally {
    isLoading.value = false
  }
}

watch(() => props.kind, () => {
  clearRefreshPoll()
  files.value = []
  isRefreshing.value = false
  sourceUrl.value = defaultSourceUrls[props.kind]
  void loadFiles(false)
})

onMounted(() => {
  void loadFiles(false)
})

onBeforeUnmount(clearRefreshPoll)
</script>

<style scoped>
.information-page {
  min-height: 100%;
  padding: 32px 42px 56px;
  color: #20252b;
  background: #f5f7fa;
}

.information-shell {
  width: min(1120px, 100%);
  margin: 0 auto;
}

.back-link {
  display: inline-flex;
  align-items: center;
  gap: 7px;
  min-height: 34px;
  color: #526168;
  font-size: 14px;
  font-weight: 650;
}

.back-link:hover,
.back-link:focus-visible {
  color: #12685c;
  outline: none;
}

.information-heading {
  display: flex;
  align-items: flex-end;
  justify-content: space-between;
  gap: 30px;
  padding: 24px 0 28px;
  border-bottom: 1px solid #d9e0e4;
}

.heading-copy {
  min-width: 0;
}

.eyebrow {
  margin: 0 0 8px;
  color: #137064;
  font-size: 12px;
  font-weight: 800;
  letter-spacing: 0;
}

.information-heading h1 {
  margin: 0;
  color: #18232d;
  font-size: 32px;
  line-height: 1.2;
  letter-spacing: 0;
}

.information-heading p:last-child {
  max-width: 680px;
  margin: 10px 0 0;
  color: #5c686f;
  font-size: 15px;
  line-height: 1.55;
}

.information-actions {
  display: flex;
  align-items: center;
  flex: 0 0 auto;
  gap: 9px;
}

.secondary-action,
.refresh-button {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  gap: 8px;
  min-height: 38px;
  padding: 0 14px;
  border: 1px solid #c9d5d2;
  border-radius: 6px;
  color: #28534e;
  background: #ffffff;
  font: inherit;
  font-size: 13px;
  font-weight: 700;
  cursor: pointer;
}

.secondary-action:hover,
.secondary-action:focus-visible,
.refresh-button:hover:not(:disabled),
.refresh-button:focus-visible {
  border-color: #80aaa3;
  color: #0f655a;
  background: #eef7f4;
  outline: none;
}

.refresh-button:disabled {
  cursor: wait;
  opacity: 0.65;
}

.records-section {
  padding-top: 30px;
}

.records-heading {
  display: flex;
  align-items: end;
  justify-content: space-between;
  gap: 24px;
  margin-bottom: 14px;
}

.records-heading h2 {
  margin: 0;
  color: #1f2a33;
  font-size: 19px;
  line-height: 1.35;
  letter-spacing: 0;
}

.records-heading p {
  margin: 5px 0 0;
  color: #6b777d;
  font-size: 13px;
}

.record-count {
  flex: 0 0 auto;
  color: #5c696f;
  font-size: 13px;
  font-weight: 700;
}

.records-table {
  overflow: hidden;
  border: 1px solid #d7dfe2;
  border-radius: 6px;
  background: #ffffff;
}

.records-table-header,
.record-row {
  display: grid;
  grid-template-columns: minmax(145px, 0.85fr) minmax(280px, 3fr) minmax(140px, 0.85fr) 24px;
  align-items: center;
  gap: 18px;
}

.records-table-header.has-product-model,
.record-row.has-product-model {
  grid-template-columns:
    minmax(120px, 0.8fr)
    minmax(260px, 2.5fr)
    minmax(150px, 1.15fr)
    minmax(125px, 0.8fr)
    24px;
}

.records-table-header {
  min-height: 42px;
  padding: 0 20px;
  color: #657178;
  background: #eef2f3;
  border-bottom: 1px solid #d7dfe2;
  font-size: 12px;
  font-weight: 800;
}

.record-row {
  min-height: 70px;
  padding: 13px 20px;
  border-bottom: 1px solid #e6ebed;
  transition: color 130ms ease, background-color 130ms ease;
}

.record-row:last-child {
  border-bottom: 0;
}

.record-row:hover,
.record-row:focus-visible {
  color: #0f655a;
  background: #f1f8f6;
  outline: none;
}

.record-number code {
  color: #1c5d56;
  font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace;
  font-size: 13px;
  font-weight: 800;
  letter-spacing: 0;
}

.record-subject {
  min-width: 0;
}

.record-subject strong {
  display: block;
  overflow-wrap: anywhere;
  color: #263139;
  font-size: 14px;
  font-weight: 650;
  line-height: 1.55;
}

.record-date {
  color: #526168;
  font-size: 13px;
  font-variant-numeric: tabular-nums;
}

.record-product-model {
  min-width: 0;
  color: #34484d;
  font-size: 13px;
  line-height: 1.45;
}

.record-product-model strong {
  overflow-wrap: anywhere;
  font-weight: 700;
}

.record-open {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  color: #849096;
}

.record-row:hover .record-open,
.record-row:focus-visible .record-open {
  color: #0f655a;
}

.mobile-label {
  display: none;
}

.information-state {
  display: flex;
  min-height: 220px;
  align-items: center;
  justify-content: center;
  flex-direction: column;
  gap: 9px;
  padding: 28px;
  border: 1px solid #d7dfe2;
  border-radius: 6px;
  color: #627077;
  background: #ffffff;
  text-align: center;
}

.information-state.is-error {
  color: #8b3535;
  border-color: #e4c8c8;
  background: #fffafa;
}

.information-state button {
  min-height: 34px;
  margin-top: 4px;
  padding: 0 14px;
  border: 1px solid currentColor;
  border-radius: 6px;
  color: inherit;
  background: transparent;
  font: inherit;
  font-size: 13px;
  font-weight: 700;
  cursor: pointer;
}

.is-spinning {
  animation: spin 900ms linear infinite;
}

@keyframes spin {
  to { transform: rotate(360deg); }
}

@media (max-width: 900px) {
  .information-page {
    padding: 26px 24px 46px;
  }

  .information-heading {
    align-items: flex-start;
    flex-direction: column;
  }
}

@media (max-width: 680px) {
  .information-page {
    padding: 20px 16px 36px;
  }

  .information-actions {
    width: 100%;
  }

  .secondary-action,
  .refresh-button {
    flex: 1 1 0;
  }

  .records-heading {
    align-items: flex-start;
    flex-direction: column;
    gap: 8px;
  }

  .records-table-header {
    display: none;
  }

  .record-row {
    grid-template-columns: 1fr 24px;
    gap: 12px 16px;
    padding: 16px;
  }

  .record-number,
  .record-subject,
  .record-product-model,
  .record-date {
    display: grid;
    grid-column: 1;
    grid-template-columns: 78px minmax(0, 1fr);
    gap: 10px;
  }

  .record-open {
    grid-column: 2;
    grid-row: 1 / span 3;
  }

  .record-row.has-product-model .record-open {
    grid-row: 1 / span 4;
  }

  .mobile-label {
    display: inline;
    color: #7a858a;
    font-size: 12px;
    font-weight: 700;
  }
}
</style>
